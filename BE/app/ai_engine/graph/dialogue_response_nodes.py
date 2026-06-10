from __future__ import annotations

from typing import Any

from app.ai_engine.core.observability import emit_ai_node_log, now_ms
from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent
from app.ai_engine.graph.dialogue_context_nodes import dialogue_log_context
from app.ai_engine.schemas.dialogue import DialogueRequest, DialogueResponse
from app.ai_engine.schemas.safety import Safety


def _sanitize_function_transition(function_call: Any) -> Any:
    if not isinstance(function_call, dict):
        return function_call
    sanitized = dict(function_call)
    args = sanitized.get("arguments")
    if isinstance(args, dict):
        sanitized["arguments"] = {k: v for k, v in args.items() if k != "playerMessage"}
    return sanitized


def _public_voice_metadata(reply: Any) -> dict[str, Any]:
    if reply is None:
        return {}
    vm = getattr(reply, "voiceMetadata", None) or {}
    return {
        "tone": vm.get("tone"),
        "tensionLevel": vm.get("tensionLevel"),
        "tonePolished": bool(vm.get("tonePolished", False)),
    }


def _public_director_dump(plan: Any) -> dict[str, Any] | None:
    if plan is None:
        return None
    dump = plan.model_dump()
    dump["functionCall"] = _sanitize_function_transition(dump.get("functionCall"))
    return dump


def format_response(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    safety = state.get("safety_findings", {})
    proposed_events = state.get("proposed_events", [])
    fallback_reason = state.get("fallback_reason")
    intent = classify_dialogue_intent(payload.question.text, payload.dialogueMode)
    checked_reply = state.get("checked_reply")
    reaction_decision = state.get("character_reaction_decision")
    reaction_dump = reaction_decision.model_dump() if reaction_decision is not None else None
    matched_refs = checked_reply.sourceRefs if checked_reply is not None else payload.allowedStatement.sourceRefs
    visual_state = payload.visualState.model_copy()
    if visual_state.suspectId is None:
        visual_state.suspectId = payload.suspect.id
    if visual_state.emotionalState is None:
        visual_state.emotionalState = payload.suspect.emotionalState
    if visual_state.tensionLevel is None:
        visual_state.tensionLevel = payload.suspect.tensionLevel
    if visual_state.pressure is None:
        visual_state.pressure = payload.suspect.pressure
    if visual_state.expression is None:
        expression = getattr(payload.suspect, "expression", None)
        if isinstance(expression, str):
            visual_state.expression = expression
    response = DialogueResponse(
        requestId=payload.requestId,
        correlationId=payload.correlationId,
        statementId=payload.allowedStatement.id,
        text=state["text"],
        dialogueMode=payload.dialogueMode,
        intent=intent,
        provider=state.get("provider"),
        model=state.get("model"),
        fallbackUsed=bool(state.get("fallback_used", False)),
        degraded=bool(state.get("degraded", False)),
        visualState=visual_state,
        proposedEvents=proposed_events,
        matchedRefs=matched_refs,
        proposedEventsCount=len(proposed_events),
        runtimeDiagnostics={
            "provider": state.get("provider"),
            "model": state.get("model"),
            "intent": intent,
            "dialogueMode": payload.dialogueMode,
            "matchedRefs": matched_refs.model_dump(),
            "matchedQuestionIds": matched_refs.questionIds,
            "matchedEvidenceIds": matched_refs.evidenceIds,
            "matchedStatementIds": matched_refs.statementIds or [payload.allowedStatement.id],
            "matchedTimelineIds": matched_refs.timelineIds,
            "proposedEventsCount": len(proposed_events),
            "safety": {
                "fallbackUsed": bool(state.get("fallback_used", False)),
                "degraded": bool(state.get("degraded", False)),
                "repaired": bool(safety.get("repaired", False)),
                "blockedReason": safety.get("blockedReason") or fallback_reason,
                "leaksSolution": bool(safety.get("leaksSolution", False)),
                "violatesCaseFacts": bool(safety.get("violatesCaseFacts", False)),
                "providerDraftRepaired": bool(safety.get("providerDraftRepaired", False)),
                "providerDraftBlockedReason": safety.get("providerDraftBlockedReason"),
                "finalTextSource": safety.get("finalTextSource") or "provider",
            },
            "graphRunner": state.get("graph_runner"),
            "graphFallbackReason": state.get("graph_fallback_reason"),
            "characterReaction": reaction_dump,
            "characterReactionRoute": getattr(reaction_decision, "reactionRoute", None),
            "conditionalRouteOwner": getattr(reaction_decision, "owner", None),
            "characterReactionRouteNode": state.get("character_reaction_route_node"),
            "voiceMetadata": _public_voice_metadata(state.get("checked_reply") or state.get("draft_reply")),
            "dialogueDirector": _public_director_dump(state.get("dialogue_director_plan")),
            "functionTransition": _sanitize_function_transition(
                getattr(state.get("dialogue_director_plan"), "functionCall", None)
            ),
        },
        safety=Safety(
            leaksSolution=bool(safety.get("leaksSolution", False)),
            violatesCaseFacts=bool(safety.get("violatesCaseFacts", False)),
            blockedTerms=list(safety.get("blockedTerms", [])),
            fallbackUsed=bool(state.get("fallback_used", False)),
            degraded=bool(state.get("degraded", False)),
            provider=state.get("provider"),
            model=state.get("model"),
            repaired=bool(safety.get("repaired", False)),
            blockedReason=safety.get("blockedReason") or fallback_reason,
            errorType=state.get("error_type"),
            graphRunner=state.get("graph_runner"),
            graphFallbackReason=state.get("graph_fallback_reason"),
        ),
    )
    emit_ai_node_log(
        dialogue_log_context(payload),
        node="format_response",
        started_at=started_at,
        provider=state.get("provider"),
        model=state.get("model"),
        fallback_used=response.safety.fallbackUsed,
        repaired=response.safety.repaired,
        blocked_reason=response.safety.blockedReason,
        proposed_event_count=len(response.proposedEvents),
    )
    return {"result": response}
