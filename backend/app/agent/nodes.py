"""LangGraph node implementations for the agentic RAG workflow.

Each node is a pure-ish coroutine that takes :class:`AgentState` and returns a
*partial* state update. All external calls (LLM, retrieval) are isolated here so
the graph wiring in :mod:`app.agent.graph` stays declarative.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from app.agent import prompts
from app.agent.state import AgentState
from app.core.config import Settings, get_settings
from app.core.constants import QueryIntent, VerificationStatus
from app.core.exceptions import ProviderError
from app.llm.base import ChatModel
from app.retrieval.hybrid import HybridRetriever
from app.retrieval.types import RetrievedChunk

logger = logging.getLogger(__name__)

_CITATION_RE = re.compile(r"\[S(\d+)\]")
_VALID_INTENTS = {intent.value for intent in QueryIntent}


class AgentNodes:
    def __init__(
        self,
        *,
        retriever: HybridRetriever,
        chat_model: ChatModel,
        settings: Settings | None = None,
    ) -> None:
        self.retriever = retriever
        self.chat_model = chat_model
        self.settings = settings or get_settings()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _to_evidence(chunk: RetrievedChunk, ref: str) -> dict[str, Any]:
        return {
            "id": chunk.id,
            "ref": ref,
            "text": chunk.text,
            "score": chunk.score,
            "dense_score": chunk.quality_score,
            "document_id": chunk.document_id,
            "document_name": chunk.document_name,
            "page": chunk.page,
            "chunk_index": chunk.chunk_index,
            "source": chunk.source,
        }

    @staticmethod
    def _citation(item: dict[str, Any]) -> dict[str, Any]:
        text = " ".join(str(item.get("text", "")).split())
        snippet = text if len(text) <= 320 else text[:319].rstrip() + "\u2026"
        return {
            "document_id": item.get("document_id", ""),
            "document_name": item.get("document_name", ""),
            "chunk_id": item.get("id", ""),
            "page": item.get("page"),
            "snippet": snippet,
            "score": float(item.get("score", 0.0)),
        }

    @staticmethod
    def _dedup(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        best: dict[str, dict[str, Any]] = {}
        for item in evidence:
            current = best.get(item["id"])
            if current is None or item.get("score", 0.0) > current.get("score", 0.0):
                best[item["id"]] = item
        return sorted(best.values(), key=lambda i: i.get("score", 0.0), reverse=True)

    async def _chat_json(
        self, messages: list[dict[str, str]], *, fallback: dict[str, Any] | None
    ) -> tuple[dict[str, Any] | None, dict[str, int]]:
        try:
            result = await self.chat_model.chat(messages, json_mode=True)
        except ProviderError:
            logger.warning("agent_llm_json_call_failed")
            return fallback, {"prompt_tokens": 0, "completion_tokens": 0}
        usage = {
            "prompt_tokens": result.prompt_tokens or 0,
            "completion_tokens": result.completion_tokens or 0,
        }
        try:
            parsed = json.loads(result.content)
        except (json.JSONDecodeError, TypeError):
            return fallback, usage
        return parsed if isinstance(parsed, dict) else fallback, usage

    @staticmethod
    def _merge_usage(state: AgentState, delta: dict[str, int]) -> dict[str, int]:
        current = state.get("usage", {})
        return {
            "prompt_tokens": current.get("prompt_tokens", 0) + delta.get("prompt_tokens", 0),
            "completion_tokens": current.get("completion_tokens", 0)
            + delta.get("completion_tokens", 0),
        }

    # ------------------------------------------------------------------ #
    # Nodes
    # ------------------------------------------------------------------ #
    async def plan(self, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        question = state["question"]
        allow_decomposition = self.settings.agent_enable_query_decomposition

        parsed, usage = await self._chat_json(
            prompts.router_messages(question, allow_decomposition=allow_decomposition),
            fallback=None,
        )
        if parsed is None or parsed.get("intent") not in _VALID_INTENTS:
            # Conservative fallback: treat as a single retrieval pass.
            intent = QueryIntent.DIRECT.value
            sub_queries = [question]
        else:
            intent = str(parsed["intent"])
            raw_sub = parsed.get("sub_queries") or []
            sub_queries = [str(q) for q in raw_sub if str(q).strip()][:4]

        single_pass = intent == QueryIntent.DIRECT.value or (
            intent == QueryIntent.MULTI_STEP.value and not sub_queries
        )
        if single_pass:
            sub_queries = [question]

        if intent == QueryIntent.CLARIFY.value:
            clarification = parsed.get("clarification") if parsed else None
            answer = clarification or (
                "Could you clarify your question? Please add specifics such as the "
                "policy name, code, or date range you are interested in."
            )
            return {
                "intent": intent,
                "sub_queries": [],
                "final_answer": answer,
                "citations": [],
                "used_evidence": [],
                "stage_timings": {"plan": time.perf_counter() - started},
                "usage": self._merge_usage(state, usage),
                "iterations": state["iterations"] + 1,
            }

        return {
            "intent": intent,
            "sub_queries": sub_queries,
            "current_query_index": 0,
            "stage_timings": {"plan": time.perf_counter() - started},
            "usage": self._merge_usage(state, usage),
            "iterations": state["iterations"] + 1,
        }

    async def retrieve(self, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        index = state["current_query_index"]
        sub_queries = state["sub_queries"] or [state["question"]]
        query = sub_queries[index] if index < len(sub_queries) else state["question"]

        filters = state.get("filters", {})
        accessible = state.get("accessible_document_ids", [])
        requested = filters.get("document_ids")
        if requested:
            allowed = [doc_id for doc_id in requested if doc_id in set(accessible)]
        else:
            allowed = accessible

        extra_filters = {
            key: filters[key]
            for key in ("category", "collection")
            if filters.get(key)
        }

        chunks = await self.retriever.retrieve(
            query,
            document_ids=allowed,
            extra_filters=extra_filters or None,
            top_k=state.get("top_k", self.settings.retrieval_top_k),
            mode=state.get("retrieval_mode", "hybrid_rerank"),  # type: ignore[arg-type]
        )

        base = len(state.get("evidence", []))
        new_evidence = [
            self._to_evidence(chunk, ref=f"S{base + offset + 1}")
            for offset, chunk in enumerate(chunks)
        ]
        return {
            "evidence": new_evidence,
            "retrievals": state.get("retrievals", 0) + 1,
            "current_query_index": index + 1,
            "iterations": state["iterations"] + 1,
            "stage_timings": {"retrieve": time.perf_counter() - started},
        }

    async def grade(self, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        evidence = self._dedup(state.get("evidence", []))
        if not evidence:
            return {
                "evidence_sufficient": False,
                "grade_reason": "no_evidence",
                "stage_timings": {"grade": time.perf_counter() - started},
                "iterations": state["iterations"] + 1,
            }

        dense_scores = [
            float(item["dense_score"]) for item in evidence if item.get("dense_score") is not None
        ]
        if dense_scores:
            # Dense cosine is calibrated on [0, 1], so the numeric gate applies.
            top_score = max(dense_scores)
            threshold_ok = top_score >= self.settings.min_relevance_score
            gate = f"dense_threshold(top_score={top_score:.3f})"
        else:
            # No calibrated signal (e.g. bm25-only). The LLM grade is the gate.
            top_score = max((float(item.get("score", 0.0)) for item in evidence), default=0.0)
            threshold_ok = True
            gate = "no_dense_signal"

        parsed, usage = await self._chat_json(
            prompts.grade_messages(state["question"], evidence), fallback=None
        )
        if parsed is None:
            sufficient = threshold_ok
            reason = gate
        else:
            # A positive LLM judgment cannot override a failed dense relevance gate.
            sufficient = bool(parsed.get("sufficient")) and threshold_ok
            reason = str(parsed.get("reason", ""))

        return {
            "evidence_sufficient": sufficient,
            "grade_reason": reason,
            "stage_timings": {"grade": time.perf_counter() - started},
            "usage": self._merge_usage(state, usage),
            "iterations": state["iterations"] + 1,
        }

    async def generate(self, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        evidence = self._dedup(state.get("evidence", []))
        strict = state.get("generation_attempts", 0) > 0
        try:
            result = await self.chat_model.chat(
                prompts.generate_messages(state["question"], evidence, strict=strict)
            )
        except ProviderError:
            logger.warning("agent_generation_unavailable")
            message = (
                "The language model is temporarily unavailable, so an answer could "
                "not be generated. Please retry shortly."
            )
            return {
                "error": "generation_unavailable",
                "draft_answer": message,
                "final_answer": message,
                "citations": [],
                "used_evidence": [self._citation(item) for item in evidence],
                "abstained": True,
                "verification_status": VerificationStatus.SKIPPED.value,
                "stage_timings": {"generate": time.perf_counter() - started},
                "iterations": state["iterations"] + 1,
            }

        cited = {f"S{number}" for number in _CITATION_RE.findall(result.content)}
        citations = [self._citation(item) for item in evidence if item.get("ref") in cited]

        return {
            "draft_answer": result.content,
            "final_answer": result.content,
            "citations": citations,
            "used_evidence": [self._citation(item) for item in evidence],
            "model": result.model or self.chat_model.model_name,
            "generation_attempts": state.get("generation_attempts", 0) + 1,
            "stage_timings": {"generate": time.perf_counter() - started},
            "usage": self._merge_usage(
                state,
                {
                    "prompt_tokens": result.prompt_tokens or 0,
                    "completion_tokens": result.completion_tokens or 0,
                },
            ),
            "iterations": state["iterations"] + 1,
        }

    async def verify(self, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        evidence = self._dedup(state.get("evidence", []))
        parsed, usage = await self._chat_json(
            prompts.verify_messages(state["question"], state.get("draft_answer", ""), evidence),
            fallback={
                "status": VerificationStatus.SKIPPED.value,
                "reason": "verification_unavailable",
            },
        )
        status = (parsed or {}).get("status", VerificationStatus.SKIPPED.value)
        if status not in {v.value for v in VerificationStatus}:
            status = VerificationStatus.SKIPPED.value
        return {
            "verification_status": status,
            "verification_notes": str((parsed or {}).get("reason", "")),
            "stage_timings": {"verify": time.perf_counter() - started},
            "usage": self._merge_usage(state, usage),
            "iterations": state["iterations"] + 1,
        }

    async def no_retrieval(self, state: AgentState) -> dict[str, Any]:
        """Answer meta/greeting messages directly, without touching the corpus."""
        started = time.perf_counter()
        answer = prompts.NO_RETRIEVAL_FALLBACK
        model = ""
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        try:
            result = await self.chat_model.chat(prompts.no_retrieval_messages(state["question"]))
        except ProviderError:
            logger.warning("agent_no_retrieval_call_failed")
        else:
            if result.content.strip():
                answer = result.content.strip()
                model = result.model or self.chat_model.model_name
            usage = {
                "prompt_tokens": result.prompt_tokens or 0,
                "completion_tokens": result.completion_tokens or 0,
            }

        return {
            "final_answer": answer,
            "draft_answer": answer,
            "citations": [],
            "used_evidence": [],
            "model": model,
            "verification_status": VerificationStatus.SKIPPED.value,
            "stage_timings": {"no_retrieval": time.perf_counter() - started},
            "usage": self._merge_usage(state, usage),
            "iterations": state["iterations"] + 1,
        }

    async def abstain(self, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        return {
            "final_answer": prompts.ABSTENTION_MESSAGE,
            "citations": [],
            "used_evidence": [
                self._citation(item) for item in self._dedup(state.get("evidence", []))
            ],
            "abstained": True,
            "verification_status": VerificationStatus.UNSUPPORTED.value,
            "stage_timings": {"abstain": time.perf_counter() - started},
            "iterations": state["iterations"] + 1,
        }

    async def respond(self, state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        update: dict[str, Any] = {
            "final_answer": state.get("final_answer") or state.get("draft_answer", ""),
            "stage_timings": {"respond": time.perf_counter() - started},
        }
        return update

    # ------------------------------------------------------------------ #
    # Conditional routing
    # ------------------------------------------------------------------ #
    def route_after_plan(self, state: AgentState) -> str:
        intent = state.get("intent")
        if intent == QueryIntent.NO_RETRIEVAL.value:
            return "no_retrieval"
        if intent == QueryIntent.CLARIFY.value:
            return "respond"
        return "retrieve"

    def route_after_retrieve(self, state: AgentState) -> str:
        more_sub_queries = state["current_query_index"] < len(state.get("sub_queries", []))
        under_limit = state.get("retrievals", 0) < self.settings.agent_max_retrievals
        if more_sub_queries and under_limit:
            return "retrieve"
        return "grade"

    def route_after_grade(self, state: AgentState) -> str:
        return "generate" if state.get("evidence_sufficient") else "abstain"

    def route_after_generate(self, state: AgentState) -> str:
        if state.get("error"):
            return "respond"
        if self.settings.agent_enable_verification:
            return "verify"
        return "respond"

    def route_after_verify(self, state: AgentState) -> str:
        unsupported = state.get("verification_status") == VerificationStatus.UNSUPPORTED.value
        can_regenerate = state.get("generation_attempts", 0) < 2
        if unsupported and can_regenerate:
            return "generate"
        return "respond"
