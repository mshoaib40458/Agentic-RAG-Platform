"""Evaluation runner: computes retrieval metrics for a stored run."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import EvaluationStatus
from app.core.exceptions import AppError
from app.db.models.evaluation import EvaluationRun
from app.evaluation.dataset import load_dataset
from app.evaluation.metrics import MetricAccumulator, precision_at_k, recall_at_k, reciprocal_rank
from app.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)


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

    async def _evaluate(self, run: EvaluationRun) -> dict:
        items = load_dataset(Path(run.dataset_path))
        mode = str(run.config.get("mode", "hybrid_rerank"))
        top_k = int(run.config.get("top_k", 5))
        candidate_k = run.config.get("candidate_k")

        retriever = HybridRetriever(self.session)
        accumulator = MetricAccumulator()
        per_item: list[dict] = []

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

            recall = recall_at_k(retrieved_ids, relevant, top_k)
            precision = precision_at_k(retrieved_ids, relevant, top_k)
            rr = reciprocal_rank(retrieved_ids, relevant)
            accumulator.add(recall=recall, precision=precision, mrr=rr)
            per_item.append(
                {
                    "question": item.question,
                    "retrieved": retrieved_ids,
                    "recall_at_k": round(recall, 4),
                    "precision_at_k": round(precision, 4),
                    "reciprocal_rank": round(rr, 4),
                }
            )

        summary = accumulator.mean()
        return {
            "mode": mode,
            "top_k": top_k,
            "candidate_k": candidate_k,
            "num_items": accumulator.count,
            **summary,
            "per_item": per_item,
        }
