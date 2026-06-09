from __future__ import annotations

from typing import Any

from app.ai_engine.schemas.base import FlexibleModel


class DialogueGraphPatch(FlexibleModel):
    """Validated graph node output patch.

    Graph nodes still compose through LangGraph's dict-shaped state API, but every
    node return is validated through this Pydantic model before it is merged into
    runtime state. Extra keys remain allowed because LangGraph state is sparse by
    node, but accidental non-mapping outputs fail at the graph boundary.
    """

    payload: Any | None = None
    knowledge_retriever: Any | None = None
    result: Any | None = None
    text: str | None = None
    character_context: Any | None = None
    event_context: Any | None = None
    retrieved_context: Any | None = None
    dialogue_director_plan: Any | None = None
    character_input: Any | None = None
    draft_reply: Any | None = None
    rule_check_input: Any | None = None
    checked_reply: Any | None = None
    gm_input: Any | None = None
    game_master_proposal: Any | None = None
    safety_findings: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    fallback_used: bool | None = None
    degraded: bool | None = None
    proposed_events: Any | None = None
    fallback_reason: str | None = None
    error_type: str | None = None
    provider: str | None = None
    model: str | None = None
    graph_runner: str | None = None
    graph_fallback_reason: str | None = None


def patch_to_raw_dict(patch: dict[str, Any]) -> dict[str, Any]:
    """Validate a sparse graph-state patch and return mergeable keys.

    Dialogue graph nodes emit partial state updates, not full state snapshots. None
    values are therefore treated as omitted keys rather than state-clearing
    commands; future nodes that need explicit clearing should introduce a typed
    sentinel/update contract instead of returning {field: None}.
    """
    validated = DialogueGraphPatch.model_validate(patch)
    raw = {
        field_name: getattr(validated, field_name)
        for field_name in type(validated).model_fields
        if getattr(validated, field_name) is not None
    }
    extra = getattr(validated, "__pydantic_extra__", None) or {}
    raw.update({key: value for key, value in extra.items() if value is not None})
    return raw
