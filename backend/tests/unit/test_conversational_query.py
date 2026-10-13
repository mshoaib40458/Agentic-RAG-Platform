"""Conversational query understanding: history context + query rewriting."""

from __future__ import annotations

import json
from typing import Any

from app.agent import prompts
from app.agent.nodes import AgentNodes
from app.llm.base import ChatResult, Message

_HISTORY = [
    {"question": "What is this project about?", "answer": "It is an SRS document platform."},
]


class _StubChat:
    model_name = "stub"

    def __init__(self, content: str) -> None:
        self._content = content

    async def chat(self, messages: list[Message], **_: Any) -> ChatResult:
        return ChatResult(content=self._content, model="stub", prompt_tokens=1, completion_tokens=1)


def test_router_prompt_embeds_history_and_rewrite_schema():
    messages = prompts.router_messages(
        "and its deadline?", allow_decomposition=True, history=_HISTORY
    )
    system = messages[0]["content"]
    assert "Conversation so far" in system
    assert "What is this project about?" in system
    assert "standalone_query" in system


def test_router_prompt_guides_query_normalization():
    """The planner must normalize typos/vague phrasing and prefer retrieval."""
    messages = prompts.router_messages("tell me about shoaib", allow_decomposition=True)
    system = messages[0]["content"]
    assert "spelling" in system
    assert "Prefer direct over clarify" in system
    assert "standalone_query" in system


def test_generate_prompt_embeds_history():
    messages = prompts.generate_messages("and its deadline?", [], history=_HISTORY)
    user = messages[1]["content"]
    assert "Conversation so far" in user
    assert "What is this project about?" in user
    assert "It is an SRS document platform." in user


def test_no_retrieval_prompt_embeds_history():
    messages = prompts.no_retrieval_messages("thanks!", history=_HISTORY)
    assert "Conversation so far" in messages[1]["content"]


async def test_plan_rewrites_followup_into_standalone_query():
    content = json.dumps(
        {
            "intent": "direct",
            "sub_queries": [],
            "standalone_query": "What is the deadline of the SRS document platform?",
        }
    )
    nodes = AgentNodes(retriever=object(), chat_model=_StubChat(content))
    state: dict[str, Any] = {
        "question": "and its deadline?",
        "history": _HISTORY,
        "iterations": 0,
        "usage": {},
    }
    update = await nodes.plan(state)  # type: ignore[arg-type]
    assert update["sub_queries"] == ["What is the deadline of the SRS document platform?"]
    assert update["standalone_query"] == "What is the deadline of the SRS document platform?"


async def test_plan_falls_back_to_question_without_rewrite():
    content = json.dumps({"intent": "direct", "sub_queries": [], "standalone_query": ""})
    nodes = AgentNodes(retriever=object(), chat_model=_StubChat(content))
    state: dict[str, Any] = {
        "question": "and its deadline?",
        "history": _HISTORY,
        "iterations": 0,
        "usage": {},
    }
    update = await nodes.plan(state)  # type: ignore[arg-type]
    assert update["sub_queries"] == ["and its deadline?"]


async def test_plan_retrieves_vague_reference_when_documents_exist():
    """'what is in this file?' must search the user's documents, not clarify."""
    content = json.dumps(
        {
            "intent": "clarify",
            "sub_queries": [],
            "standalone_query": "what are the skills mentioned in this file",
            "clarification": "Which file do you mean?",
        }
    )
    nodes = AgentNodes(retriever=object(), chat_model=_StubChat(content))
    state: dict[str, Any] = {
        "question": "what are the skills mention in this file",
        "history": [],
        "iterations": 0,
        "usage": {},
        "accessible_document_ids": ["doc-1"],
    }
    update = await nodes.plan(state)  # type: ignore[arg-type]
    assert update["intent"] == "direct"
    assert update["sub_queries"] == ["what are the skills mentioned in this file"]


async def test_plan_keeps_clarify_when_no_documents():
    content = json.dumps(
        {
            "intent": "clarify",
            "sub_queries": [],
            "standalone_query": "",
            "clarification": "Which file?",
        }
    )
    nodes = AgentNodes(retriever=object(), chat_model=_StubChat(content))
    state: dict[str, Any] = {
        "question": "what is in this file",
        "history": [],
        "iterations": 0,
        "usage": {},
        "accessible_document_ids": [],
    }
    update = await nodes.plan(state)  # type: ignore[arg-type]
    assert update["intent"] == "clarify"
