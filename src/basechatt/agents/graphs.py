"""LangGraph wiring for the research agent.

Graph: START -> scope_check -> (fast_path | retrieve) -> web_search -> answer -> verify -> END.

The graph is a thin shell: all real work lives in the node functions in
``tools.py`` so it can be unit-tested directly and executed without LangGraph if
desired. LangGraph provides structured routing, retries and step tracking.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from basechatt.agents.state import ResearchState
from basechatt.agents.tools import (
    answer_node,
    fast_path_node,
    retrieve_node,
    scope_check_node,
    verify_node,
    web_search_node,
)
from basechatt.observability.logging import get_logger

logger = get_logger("basechatt.agents.graphs")


class _GraphState(TypedDict, total=False):
    # Thin mapping over ResearchState; the heavy lifting uses ResearchState
    # directly via the node closures below.
    query: str


def _errors_for(name):
    def _node(state: ResearchState) -> ResearchState:
        state.answer.is_satisfactory = False
        logger.warning("agent pipeline errored at step %s", name)
        return state

    return _node


def build_graph():
    g = StateGraph(ResearchState)

    g.add_node("scope_check", scope_check_node)
    g.add_node("fast_path", fast_path_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("web_search", web_search_node)
    g.add_node("answer", answer_node)
    g.add_node("verify", verify_node)

    g.add_edge(START, "scope_check")
    g.add_conditional_edges(
        "scope_check",
        lambda s: "fast_path" if s.metadata.get("route") == "fast_path" else (
            "reject" if s.metadata.get("route") == "reject" else "retrieve"
        ),
        {
            "fast_path": "fast_path",
            "reject": "fast_path",  # reuse fast_path for rejection message
            "retrieve": "retrieve",
        },
    )
    g.add_edge("fast_path", END)
    g.add_edge("retrieve", "web_search")
    g.add_edge("web_search", "answer")
    g.add_edge("answer", "verify")
    g.add_edge("verify", END)

    g.set_entry_point("scope_check")
    graph = g.compile()
    return graph


def _route(state: ResearchState) -> str:
    # Currently a linear pipeline; reserved for future routing/reflection.
    return "end"


async def run_research(state: ResearchState) -> ResearchState:
    """Run the research pipeline over a prepared state (with .session set)."""
    graph = build_graph()
    result = await graph.ainvoke(state)
    if isinstance(result, dict):
        state.answer = result.get("answer")
        state.retrieval = result.get("retrieval")
        state.metadata = result.get("metadata", {})
        state.web_evidence = result.get("web_evidence", [])
    return state
