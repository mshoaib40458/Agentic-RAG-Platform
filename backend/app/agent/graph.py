"""Graph wiring for the agentic RAG workflow (SRS FR-025/FR-030).

    START -> plan -+- no_retrieval -> respond -> END
                   +- respond -> END
                   +- retrieve -+-> retrieve (loop over sub-queries)
                                +-> grade -+- generate -> verify -+- generate (retry)
                                           |                     +-> respond -> END
                                           +-> abstain -> respond -> END
"""

from __future__ import annotations

from typing import Any

from app.agent.nodes import AgentNodes
from app.agent.state import AgentState


def build_agent_graph(nodes: AgentNodes) -> Any:
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(AgentState)

    graph.add_node("plan", nodes.plan)
    graph.add_node("retrieve", nodes.retrieve)
    graph.add_node("grade", nodes.grade)
    graph.add_node("generate", nodes.generate)
    graph.add_node("verify", nodes.verify)
    graph.add_node("no_retrieval", nodes.no_retrieval)
    graph.add_node("abstain", nodes.abstain)
    graph.add_node("respond", nodes.respond)

    graph.add_edge(START, "plan")
    graph.add_conditional_edges(
        "plan",
        nodes.route_after_plan,
        {"retrieve": "retrieve", "no_retrieval": "no_retrieval", "respond": "respond"},
    )
    graph.add_conditional_edges(
        "retrieve", nodes.route_after_retrieve, {"retrieve": "retrieve", "grade": "grade"}
    )
    graph.add_conditional_edges(
        "grade", nodes.route_after_grade, {"generate": "generate", "abstain": "abstain"}
    )
    graph.add_conditional_edges(
        "generate", nodes.route_after_generate, {"verify": "verify", "respond": "respond"}
    )
    graph.add_conditional_edges(
        "verify", nodes.route_after_verify, {"generate": "generate", "respond": "respond"}
    )
    graph.add_edge("no_retrieval", "respond")
    graph.add_edge("abstain", "respond")
    graph.add_edge("respond", END)

    return graph.compile()
