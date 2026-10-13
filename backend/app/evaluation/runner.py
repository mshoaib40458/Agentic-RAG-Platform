"""Evaluation runner (SRS FR-051/FR-052, 8.1).

Runs a retrieval (and optionally answer) evaluation over a JSONL dataset and
persists aggregate metrics on the ``EvaluationRun`` row. The pure helper
:func:`evaluate_dataset` is reused by the sweep script so CLI and API stay in
sync.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import EvaluationStatus
from app.core.exceptions import AppError
from app.db.models.document import Document
from app.db.models.evaluation import EvaluationRun
from app.evaluation.dataset import EvalItem, load_dataset
from app.evaluation.metrics import (
    MetricAccumulator,
    hit_rate_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    token_f1,
)
from app.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)


async def _all_document_ids(session: AsyncSession) -> list[str]:
    result = await session.execute(select(Document.id))
    return [str(row) for row in result.scalars().all()]


async def evaluate_dataset(
    session: AsyncSession,
    items: list[EvalItem],
    *,
    mode: str = "hybrid_rerank",
    top_k: int = 5,
    candidate_k: int | None = None,
    include_answer_metrics: bool = False,
) -> dict[str, Any]:
    retriever = HybridRetriever(session)
    accumulator = MetricAccumulator()
    per_item: list[dict[str, Any]] = []

    all_document_ids: list[str] = []
    if include_answer_metrics:
        all_document_ids = await _all_document_ids(session)

    for item in items:
        if not item.has_labels:
            continue
        chunks = await retriever.retrieve(
            item.question,
            document_ids=None,
            top_k=top_k,
            candidate_k=int(candidate_k) if candidate_k else None,
            mode=mode,  # type: ignore[arg-type]
        )
        use_chunks = bool(item.relevant_chunk_ids)
        relevant = set(item.relevant_chunk_ids or item.relevant_document_ids)
        retrieved_ids = [chunk.id if use_chunks else chunk.document_id for chunk in chunks]

        answer_f1: float | None = None
        generated_answer: str | None = None
        if include_answer_metrics and item.expected_answer:
            from app.agent.runner import AgentRunner
            from app.llm.groq_client import get_chat_model

            runner = AgentRunner(
                retriever=HybridRetriever(session),
                chat_model=get_chat_model(),
            )
            result = await runner.run(
                question=item.question,
                user_id="evaluation",
                role="evaluator",
                accessible_document_ids=all_document_ids,
                retrieval_mode=mode,
                top_k=top_k,
            )
            generated_answer = result.answer
            answer_f1 = token_f1(result.answer, item.expected_answer)

        accumulator.add(
            recall=recall_at_k(retrieved_ids, relevant, top_k),
            precision=precision_at_k(retrieved_ids, relevant, top_k),
            mrr=reciprocal_rank(retrieved_ids, relevant),
            ndcg=ndcg_at_k(retrieved_ids, relevant, top_k),
            hit_rate=hit_rate_at_k(retrieved_ids, relevant, top_k),
            answer_f1=answer_f1,
        )
        per_item.append(
            {
                "question": item.question,
                "retrieved_ids": retrieved_ids,
                "relevant_ids": sorted(relevant),
                "expected_answer": item.expected_answer,
                "generated_answer": generated_answer,
                "answer_f1": answer_f1,
            }
        )

    metrics = accumulator.mean()
    return {
        "mode": mode,
        "top_k": top_k,
        "candidate_k": candidate_k,
        "evaluated_items": len(per_item),
        "metrics": metrics,
        "per_item": per_item,
    }


class EvaluationRunner:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self, run: EvaluationRun) -> EvaluationRun:
        run.status = EvaluationStatus.RUNNING.value
        run.started_at = datetime.now(UTC)
        await self.session.commit()

        try:
            metrics = await self._evaluate(run)
        except AppError as exc:
            run.status = EvaluationStatus.FAILED.value
            run.error_message = exc.message
        except Exception:  # noqa: BLE001
            logger.exception("evaluation_failed", extra={"run_id": run.id})
            run.status = EvaluationStatus.FAILED.value
            run.error_message = "Unexpected error during evaluation."
        else:
            run.status = EvaluationStatus.COMPLETED.value
            run.metrics = metrics
            run.error_message = None
        finally:
            run.completed_at = datetime.now(UTC)
            await self.session.commit()
        return run

    async def _evaluate(self, run: EvaluationRun) -> dict[str, Any]:
        items = load_dataset(Path(run.dataset_path))
        config: dict[str, Any] = run.config or {}
        result = await evaluate_dataset(
            self.session,
            items,
            mode=str(config.get("mode", "hybrid_rerank")),
            top_k=int(config.get("top_k", 5)),
            candidate_k=config.get("candidate_k"),
            include_answer_metrics=bool(config.get("include_answer_metrics", False)),
        )
        thresholds = config.get("thresholds") or {}
        if thresholds:
            failures = {
                key: {"actual": result["metrics"].get(key), "minimum": float(minimum)}
                for key, minimum in thresholds.items()
                if result["metrics"].get(key, 0.0) < float(minimum)
            }
            result["passed"] = not failures
            result["threshold_failures"] = failures
        return result
