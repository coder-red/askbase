"""LangGraph wiring for the research agent.

Graph: START -> retrieve -> answer -> verify -> END.

The graph is a thin shell: all real work lives in the node functions in
``tools.py`` so it can be unit-tested directly and executed without LangGraph if
desired. LangGraph provides structured routing, retries and step tracking.
"""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from basechatt.agents.state import ResearchState
from basechatt.agents.tools import answer_node, retrieve_node, verify_node
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

    g.add_node("retrieve", retrieve_node)
    g.add_node("answer", answer_node)
    g.add_node("verify", verify_node)

    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "answer")
    g.add_edge("answer", "verify")
    g.add_edge("verify", END)

    g.set_entry_point("retrieve")
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
    return state
