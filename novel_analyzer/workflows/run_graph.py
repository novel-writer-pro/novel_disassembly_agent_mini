"""LangGraph workflow skeleton for chapter-progressive execution."""

from __future__ import annotations

from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


class RunGraphState(TypedDict):
    """Minimal state used by the scaffold workflow."""

    current_chapter: int
    max_chapter: int
    committed: list[int]


def _process_chapter(state: RunGraphState) -> RunGraphState:
    current = state["current_chapter"]
    return {
        "current_chapter": current + 1,
        "max_chapter": state["max_chapter"],
        "committed": state["committed"] + [current],
    }


def _route(state: RunGraphState) -> str:
    return "done" if state["current_chapter"] > state["max_chapter"] else "continue"


def build_run_graph() -> object:
    """Build a simple checkpoint-capable workflow graph."""

    graph = StateGraph(RunGraphState)
    graph.add_node("process_chapter", _process_chapter)
    graph.add_edge(START, "process_chapter")
    graph.add_conditional_edges(
        "process_chapter",
        _route,
        {"continue": "process_chapter", "done": END},
    )
    return graph.compile(checkpointer=InMemorySaver())
