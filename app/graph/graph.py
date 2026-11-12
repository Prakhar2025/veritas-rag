"""Grounded pipeline graph: condense, retrieve, grade, generate, attribute, finalize.

History persists through the SQLite session store and is injected at invoke time;
the store is the durability layer described in docs/03 and docs/06.
"""

from __future__ import annotations

from typing import cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.graph.nodes import (
    Runtime,
    make_attribute,
    make_condense,
    make_finalize,
    make_generate,
    make_grade,
    make_retrieve,
)
from app.graph.state import PipelineState


def build_graph(runtime: Runtime) -> CompiledStateGraph:
    """Compile the grounded pipeline as a state graph."""
    graph = StateGraph(PipelineState)
    graph.add_node("condense", make_condense(runtime))  # type: ignore[call-overload]
    graph.add_node("retrieve", make_retrieve(runtime))  # type: ignore[call-overload]
    graph.add_node("grade", make_grade(runtime))  # type: ignore[call-overload]
    graph.add_node("generate", make_generate(runtime))  # type: ignore[call-overload]
    graph.add_node("attribute", make_attribute(runtime))  # type: ignore[call-overload]
    graph.add_node("finalize", make_finalize(runtime))  # type: ignore[call-overload]

    graph.add_edge(START, "condense")
    graph.add_edge("condense", "retrieve")

    def after_retrieve(state: PipelineState) -> str:
        if state.get("refusal"):
            return "finalize"
        return "grade"

    def after_grade(state: PipelineState) -> str:
        if state.get("refusal"):
            return "finalize"
        return "generate"

    def after_generate(state: PipelineState) -> str:
        if state.get("refusal"):
            return "finalize"
        return "attribute"

    def after_attribute(state: PipelineState) -> str:
        if state.get("refusal"):
            return "finalize"
        return "finalize"

    graph.add_conditional_edges("retrieve", after_retrieve, ["grade", "finalize"])
    graph.add_conditional_edges("grade", after_grade, ["generate", "finalize"])
    graph.add_conditional_edges("generate", after_generate, ["attribute", "finalize"])
    graph.add_conditional_edges("attribute", after_attribute, ["finalize"])
    graph.add_edge("finalize", END)

    return graph.compile()


def run_turn(
    runtime: Runtime,
    session_id: str,
    question: str,
    role: str = "analyst",
) -> PipelineState:
    """Run one conversation turn: inject history, invoke, return final state."""
    history = runtime.store.history(session_id)
    compiled = build_graph(runtime)
    # langgraph invoke returns a dynamic dict; coerce for the type checker.
    final = cast(PipelineState, compiled.invoke(
        {"session_id": session_id, "role": role, "question": question, "history": history},
    ))
    return final
