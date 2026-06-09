from __future__ import annotations

import logging
from typing import Any, Callable

from app.ai_engine.schemas.dialogue import DialogueRequest, DialogueResponse
from app.ai_engine.schemas.graph import patch_to_raw_dict
from .dialogue_nodes import (
    build_answer_relevant_plan,
    build_ask_clarification_plan,
    build_challenge_player_contradiction_plan,
    build_deflect_irrelevant_plan,
    build_react_to_valid_pressure_plan,
    build_refuse_meta_or_private_plan,
    build_reject_false_premise_plan,
    format_response,
    generate_response,
    guard_response,
    judge_character_reaction,
    archive_character_reaction,
    load_context,
    polish_tone,
    propose_events,
    review_character_reaction,
    retrieve_context,
    select_character_reaction_route,
    validate_character_reaction,
    validate_scope,
)

logger = logging.getLogger("app.ai")
Node = Callable[[dict[str, Any]], dict[str, Any]]

_ROUTE_NODES: dict[str, tuple[str, Node]] = {
    "answer_relevant": ("AnswerRelevantRoute", build_answer_relevant_plan),
    "deflect_irrelevant": ("DeflectIrrelevantRoute", build_deflect_irrelevant_plan),
    "reject_false_premise": ("RejectFalsePremiseRoute", build_reject_false_premise_plan),
    "challenge_player_contradiction": ("ChallengePlayerContradictionRoute", build_challenge_player_contradiction_plan),
    "react_to_valid_pressure": ("ReactToValidPressureRoute", build_react_to_valid_pressure_plan),
    "ask_clarification": ("AskClarificationRoute", build_ask_clarification_plan),
    "refuse_meta_or_private": ("RefuseMetaOrPrivateRoute", build_refuse_meta_or_private_plan),
}

_PREFIX_NODES: list[tuple[str, Node]] = [
    ("load_context", load_context),
    ("validate_scope", validate_scope),
    ("KnowledgeRetriever", retrieve_context),
    ("CharacterReactionJudgeAgent", judge_character_reaction),
    ("CharacterReactionValidator", validate_character_reaction),
]

_SUFFIX_NODES: list[tuple[str, Node]] = [
    ("ReactionReviewAgent", review_character_reaction),
    ("ReactionLibrarianAgent", archive_character_reaction),
    ("CharacterAgent", generate_response),
    ("DialogueTonePolisher", polish_tone),
    ("LightRuleCheck", guard_response),
    ("GameMasterAgent", propose_events),
    ("format_response", format_response),
]


def _apply_node(state: dict[str, Any], node: Node) -> dict[str, Any]:
    state.update(patch_to_raw_dict(node(state)))
    return state


def _run_route_aware_pipeline(initial_state: dict[str, Any], reason: str) -> dict[str, Any]:
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
    state = {**initial_state, "graph_runner": "pipeline", "graph_fallback_reason": reason}
    for _, node in _PREFIX_NODES:
        _apply_node(state, node)
    route = select_character_reaction_route(state)
    _, route_node = _ROUTE_NODES.get(route, _ROUTE_NODES["ask_clarification"])
    _apply_node(state, route_node)
    for _, node in _SUFFIX_NODES:
        _apply_node(state, node)
    return state


def _run_langgraph(initial_state: dict[str, Any]) -> dict[str, Any]:
    from langgraph.graph import END, StateGraph
    from typing_extensions import TypedDict

    class WorkflowState(TypedDict, total=False):
        payload: Any
        knowledge_retriever: Any
        result: Any
        text: str
        character_context: Any
        event_context: Any
        retrieved_context: Any
        character_reaction_decision: Any
        character_reaction_route: str
        character_reaction_route_node: str
        reaction_review: dict[str, Any]
        reaction_librarian_card: dict[str, Any]
        dialogue_director_plan: Any
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
    for name, node in [*_PREFIX_NODES, *_ROUTE_NODES.values(), *_SUFFIX_NODES]:
        graph.add_node(name, lambda state, _node=node: patch_to_raw_dict(_node(state)))

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "validate_scope")
    graph.add_edge("validate_scope", "KnowledgeRetriever")
    graph.add_edge("KnowledgeRetriever", "CharacterReactionJudgeAgent")
    graph.add_edge("CharacterReactionJudgeAgent", "CharacterReactionValidator")
    graph.add_conditional_edges(
        "CharacterReactionValidator",
        select_character_reaction_route,
        {route: node_name for route, (node_name, _) in _ROUTE_NODES.items()},
    )
    for node_name, _ in _ROUTE_NODES.values():
        graph.add_edge(node_name, "ReactionReviewAgent")
    graph.add_edge("ReactionReviewAgent", "ReactionLibrarianAgent")
    graph.add_edge("ReactionLibrarianAgent", "CharacterAgent")
    graph.add_edge("CharacterAgent", "DialogueTonePolisher")
    graph.add_edge("DialogueTonePolisher", "LightRuleCheck")
    graph.add_edge("LightRuleCheck", "GameMasterAgent")
    graph.add_edge("GameMasterAgent", "format_response")
    graph.add_edge("format_response", END)
    return graph.compile().invoke({**initial_state, "graph_runner": "langgraph"})


def run_dialogue_graph(payload: DialogueRequest, knowledge_retriever: Any) -> DialogueResponse:
    initial_state = {"payload": payload, "knowledge_retriever": knowledge_retriever}
    try:
        state = _run_langgraph(initial_state)
    except ImportError as exc:
        state = _run_route_aware_pipeline(initial_state, f"langgraph_import_error:{type(exc).__name__}")
    except Exception as exc:
        state = _run_route_aware_pipeline(initial_state, f"langgraph_runtime_error:{type(exc).__name__}")
    return state["result"]
