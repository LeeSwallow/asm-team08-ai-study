from __future__ import annotations

from typing import Any

from app.ai_engine.schemas.dialogue import DialogueRequest, DialogueResponse

from .common import run_langgraph_or_pipeline
from .dialogue_nodes import (
    direct_dialogue,
    format_response,
    generate_response,
    guard_response,
    load_context,
    polish_tone,
    propose_events,
    retrieve_context,
    validate_scope,
)


def run_dialogue_graph(payload: DialogueRequest, knowledge_retriever: Any) -> DialogueResponse:
    state = run_langgraph_or_pipeline(
        {"payload": payload, "knowledge_retriever": knowledge_retriever},
        [
            ("load_context", load_context),
            ("validate_scope", validate_scope),
            ("KnowledgeRetriever", retrieve_context),
            ("DialogueDirectorAgent", direct_dialogue),
            ("CharacterAgent", generate_response),
            ("DialogueTonePolisher", polish_tone),
            ("LightRuleCheck", guard_response),
            ("GameMasterAgent", propose_events),
            ("format_response", format_response),
        ],
    )
    return state["result"]
