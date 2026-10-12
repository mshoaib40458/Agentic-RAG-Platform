"""Agent routing decisions (SRS FR-026/FR-030/FR-034)."""

from __future__ import annotations

from app.agent.nodes import AgentNodes
from app.core.constants import QueryIntent, VerificationStatus


def _nodes() -> AgentNodes:
    # Routing methods are pure functions of state; dependencies are unused here.
    return AgentNodes(retriever=object(), chat_model=object())


def test_plan_routes_meta_queries_to_respond():
    nodes = _nodes()
    assert nodes.route_after_plan({"intent": QueryIntent.NO_RETRIEVAL.value}) == "respond"
    assert nodes.route_after_plan({"intent": QueryIntent.CLARIFY.value}) == "respond"
    assert nodes.route_after_plan({"intent": QueryIntent.DIRECT.value}) == "retrieve"


def test_retrieve_loops_over_sub_queries_then_grades():
    nodes = _nodes()
    looping = {"current_query_index": 1, "sub_queries": ["a", "b"], "retrievals": 1}
    assert nodes.route_after_retrieve(looping) == "retrieve"
    done = {"current_query_index": 2, "sub_queries": ["a", "b"], "retrievals": 2}
    assert nodes.route_after_retrieve(done) == "grade"


def test_retrieve_respects_max_retrievals():
    nodes = _nodes()
    over_limit = {
        "current_query_index": 1,
        "sub_queries": ["a", "b", "c"],
        "retrievals": nodes.settings.agent_max_retrievals,
    }
    assert nodes.route_after_retrieve(over_limit) == "grade"


def test_grade_routes_to_abstain_without_evidence():
    nodes = _nodes()
    assert nodes.route_after_grade({"evidence_sufficient": True}) == "generate"
    assert nodes.route_after_grade({"evidence_sufficient": False}) == "abstain"


def test_generate_skips_verification_on_error_or_when_disabled():
    nodes = _nodes()
    assert nodes.route_after_generate({"error": "generation_unavailable"}) == "respond"
    assert nodes.route_after_generate({}) == "verify"

    nodes.settings.agent_enable_verification = False
    assert nodes.route_after_generate({}) == "respond"


def test_verify_regenerates_once_then_responds():
    nodes = _nodes()
    unsupported_first = {
        "verification_status": VerificationStatus.UNSUPPORTED.value,
        "generation_attempts": 1,
    }
    assert nodes.route_after_verify(unsupported_first) == "generate"

    unsupported_second = {
        "verification_status": VerificationStatus.UNSUPPORTED.value,
        "generation_attempts": 2,
    }
    assert nodes.route_after_verify(unsupported_second) == "respond"

    supported = {
        "verification_status": VerificationStatus.SUPPORTED.value,
        "generation_attempts": 1,
    }
    assert nodes.route_after_verify(supported) == "respond"
