"""High-level runner that executes the agent graph with bounded execution."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

from app.agent.graph import build_agent_graph
from app.agent.nodes import AgentNodes
from app.agent.state import initial_state
from app.core.config import Settings, get_settings
from app.core.exceptions import AgentError, AppError
from app.llm.base import ChatModel
from app.retrieval.hybrid import HybridRetriever

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentResult:
    answer: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    used_evidence: list[dict[str, Any]] = field(default_factory=list)
    verification_status: str = "skipped"
    intent: str = ""
    abstained: bool = False
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    stage_timings: dict[str, float] = field(default_factory=dict)
    error: str | None = None


class AgentRunner:
    def __init__(
        self,
        *,
        retriever: HybridRetriever,
        chat_model: ChatModel,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.nodes = AgentNodes(retriever=retriever, chat_model=chat_model, settings=self.settings)
        self.graph = build_agent_graph(self.nodes)

    async def run(
        self,
        *,
        question: str,
        user_id: str,
        role: str,
        accessible_document_ids: list[str],
        filters: dict[str, Any] | None = None,
        retrieval_mode: str = "hybrid_rerank",
        top_k: int | None = None,
    ) -> AgentResult:
        state = initial_state(
            question=question,
            user_id=user_id,
            role=role,
            accessible_document_ids=accessible_document_ids,
            filters=filters,
            retrieval_mode=retrieval_mode,
            top_k=top_k or self.settings.retrieval_top_k,
        )
        # Hard recursion cap as an independent backstop to the node counters.
        config = {"recursion_limit": max(25, self.settings.agent_max_iterations * 4)}

        try:
            final = await asyncio.wait_for(
                self.graph.ainvoke(state, config=config),
                timeout=self.settings.agent_timeout_seconds,
            )
        except TimeoutError as exc:
            raise AgentError("The agent workflow timed out.", code="agent_timeout") from exc
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize graph failures
            from langgraph.errors import GraphRecursionError

            if isinstance(exc, GraphRecursionError):
                raise AgentError(
                    "The agent workflow exceeded its step limit.", code="agent_recursion_limit"
                ) from exc
            raise AgentError(
                "The agent workflow failed to complete.", code="agent_error"
            ) from exc

        return AgentResult(
            answer=final.get("final_answer", ""),
            citations=final.get("citations", []),
            used_evidence=final.get("used_evidence", []),
            verification_status=final.get("verification_status", "skipped"),
            intent=final.get("intent", ""),
            abstained=final.get("abstained", False),
            model=final.get("model", ""),
            usage=final.get("usage", {}),
            stage_timings=final.get("stage_timings", {}),
            error=final.get("error"),
        )
