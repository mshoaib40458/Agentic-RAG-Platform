"""LangGraph workflow state for the agentic RAG pipeline (SRS 4.4)."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def _merge_dicts(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {**left, **right}


class AgentState(TypedDict, total=False):
    """State threaded through the graph.

    Fields with reducers accumulate across nodes; the rest are overwritten by
    whichever node returns them.
    """

    # --- Inputs ---
    question: str
    history: list[dict[str, str]]      # prior {question, answer} turns
    filters: dict[str, Any]              # document_ids / category / collection
    user_id: str
    role: str
    accessible_document_ids: list[str]   # authorization scope (FR-027)
    retrieval_mode: str
    top_k: int

    # --- Planning ---
    intent: str
    sub_queries: list[str]
    current_query_index: int
    standalone_query: str                 # context-resolved retrieval query

    # --- Retrieval / evidence ---
    evidence: Annotated[list[dict[str, Any]], operator.add]
    retrievals: int
    evidence_sufficient: bool
    grade_reason: str

    # --- Answering / verification ---
    draft_answer: str
    final_answer: str
    citations: list[dict[str, Any]]
    used_evidence: list[dict[str, Any]]
    verification_status: str
    verification_notes: str
    generation_attempts: int
    abstained: bool

    # --- Bookkeeping ---
    iterations: int
    model: str
    usage: dict[str, int]
    stage_timings: Annotated[dict[str, float], _merge_dicts]
    error: str | None


def initial_state(
    *,
    question: str,
    user_id: str,
    role: str,
    accessible_document_ids: list[str],
    history: list[dict[str, str]] | None = None,
    filters: dict[str, Any] | None = None,
    retrieval_mode: str = "hybrid_rerank",
    top_k: int = 5,
) -> AgentState:
    return AgentState(
        question=question,
        history=history or [],
        filters=filters or {},
        user_id=user_id,
        role=role,
        accessible_document_ids=accessible_document_ids,
        retrieval_mode=retrieval_mode,
        top_k=top_k,
        intent="",
        sub_queries=[],
        current_query_index=0,
        standalone_query="",
        evidence=[],
        retrievals=0,
        evidence_sufficient=False,
        grade_reason="",
        draft_answer="",
        final_answer="",
        citations=[],
        used_evidence=[],
        verification_status="skipped",
        verification_notes="",
        generation_attempts=0,
        abstained=False,
        iterations=0,
        model="",
        usage={"prompt_tokens": 0, "completion_tokens": 0},
        stage_timings={},
        error=None,
    )
