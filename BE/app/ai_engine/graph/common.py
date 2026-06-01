from __future__ import annotations

import logging
from typing import Any, Callable


Node = Callable[[dict[str, Any]], dict[str, Any]]
logger = logging.getLogger("app.ai")


def run_pipeline(initial_state: dict[str, Any], nodes: list[Node]) -> dict[str, Any]:
    state = dict(initial_state)
    for node in nodes:
        state.update(node(state))
    return state


def _run_observable_pipeline(initial_state: dict[str, Any], nodes: list[tuple[str, Node]], reason: str) -> dict[str, Any]:
    logger.warning(
        "ai graph runner fallback selected",
        extra={
            "service": "ai",
            "graph": "dialogue",
            "node": "graph_runner",
            "graph_runner": "pipeline",
            "graph_fallback_reason": reason,
        },
    )
    return run_pipeline(
        {**initial_state, "graph_runner": "pipeline", "graph_fallback_reason": reason},
        [node for _, node in nodes],
    )


def run_langgraph_or_pipeline(initial_state: dict[str, Any], nodes: list[tuple[str, Node]]) -> dict[str, Any]:
    try:
        from langgraph.graph import END, StateGraph
        from typing_extensions import TypedDict
    except ImportError as exc:
        return _run_observable_pipeline(initial_state, nodes, f"langgraph_import_error:{type(exc).__name__}")

    try:
        class WorkflowState(TypedDict, total=False):
            payload: Any
            result: Any
            text: str
            character_input: Any
            draft_reply: Any
            rule_check_input: Any
            checked_reply: Any
            gm_input: Any
            game_master_proposal: Any
            safety_findings: dict[str, Any]
            meta: dict[str, Any]
            fallback_used: bool
            degraded: bool
            proposed_events: Any
            fallback_reason: str
            error_type: str
            provider: str
            model: str
            graph_runner: str
            graph_fallback_reason: str

        graph = StateGraph(WorkflowState)
        for name, node in nodes:
            graph.add_node(name, node)
        for index, (name, _) in enumerate(nodes):
            if index == 0:
                graph.set_entry_point(name)
            if index + 1 < len(nodes):
                graph.add_edge(name, nodes[index + 1][0])
            else:
                graph.add_edge(name, END)
        return graph.compile().invoke({**initial_state, "graph_runner": "langgraph"})
    except Exception as exc:
        return _run_observable_pipeline(initial_state, nodes, f"langgraph_runtime_error:{type(exc).__name__}")
