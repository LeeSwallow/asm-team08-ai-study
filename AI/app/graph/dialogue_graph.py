from __future__ import annotations

import logging
from typing import Any

from app.application.character_agent import CharacterAgent, build_character_agent_input, render_dialogue_seed
from app.application.game_master_agent import GameMasterAgent
from app.application.light_rule_check import LightRuleCheck
from app.core.guard import extract_case_context_terms, normalize_text
from app.core.observability import AiLogContext, emit_ai_node_log, now_ms
from app.domain.dialogue_intent import classify_dialogue_intent
from app.schemas.agents import GameMasterAgentInput, LightRuleCheckInput
from app.schemas.common import Safety
from app.schemas.dialogue import DialogueRequest, DialogueResponse

from .common import run_langgraph_or_pipeline


def _context(payload: DialogueRequest) -> AiLogContext:
    return AiLogContext(
        request_id=payload.requestId,
        session_id=payload.sessionId,
        case_id=payload.caseId,
        graph="dialogue",
    )


def load_context(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    public_timeline = []
    if payload.storyline:
        public_timeline = [event for event in payload.storyline.visibleTimeline if not getattr(event, "hidden", False)]
    result = {
        "allowed_text": payload.allowedStatement.text,
        "public_timeline_count": len(public_timeline),
        "visual_state": payload.visualState,
    }
    emit_ai_node_log(_context(payload), node="load_context", started_at=started_at)
    return result


def validate_scope(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    result = {
        "meta": {
            "statement_id": payload.allowedStatement.id,
            "max_length": payload.style.maxLength,
            "reveal_allowed": payload.revealAllowed,
            "current_act_id": payload.storyline.currentActId if payload.storyline else None,
            "visual_state_present": bool(payload.visualState.backgroundId or payload.visualState.characterImageState),
        }
    }
    emit_ai_node_log(_context(payload), node="validate_scope", started_at=started_at)
    return result


def _has_public_context_ref(payload: DialogueRequest) -> bool:
    refs = payload.allowedStatement.sourceRefs
    policy = payload.allowedEventPolicy
    return bool(
        refs.evidenceIds
        or refs.timelineIds
        or refs.contradictionIds
        or policy.relatedEvidenceIds
        or policy.relatedTimelineEventIds
        or policy.relatedContradictionIds
    )


def _allowed_context_terms(payload: DialogueRequest) -> list[str]:
    terms = set(extract_case_context_terms(payload.allowedStatement.text))
    if not _has_public_context_ref(payload):
        return sorted(terms)

    terms.update(extract_case_context_terms(payload.question.text))
    pack = payload.characterKnowledgePack
    if pack:
        for snippet in (
            *pack.visibleTimeline,
            *pack.alibiSnippets,
            *pack.evidenceSnippets,
            *pack.relationshipSnippets,
            *pack.recentDialogue,
        ):
            text = getattr(snippet, "text", "")
            terms.update(extract_case_context_terms(text))
    if payload.characterTimeline:
        for event in payload.characterTimeline.events:
            terms.update(extract_case_context_terms(event.claimedLocation or ""))
            terms.update(extract_case_context_terms(event.claimedAction or ""))
    if terms:
        terms.update({"단서"})
    if terms & {"립스틱", "와인잔", "와인", "자국"}:
        terms.update({"단서"})
    if terms & {"약", "약물", "복용", "처방", "의료", "의사"}:
        terms.update({"단서", "기록", "약", "약물", "복용", "처방", "의료"})
    return sorted(terms)


def _event_policy_has_public_contradiction_context(payload: DialogueRequest) -> bool:
    policy = payload.allowedEventPolicy
    return bool(policy.relatedContradictionIds and (policy.relatedEvidenceIds or policy.relatedTimelineEventIds))


def generate_response(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    agent_input = build_character_agent_input(payload)
    result = CharacterAgent().run(agent_input)
    emit_ai_node_log(
        _context(payload),
        node="CharacterAgent",
        started_at=started_at,
        provider=result.provider,
        model=result.model,
        fallback_used=result.fallbackUsed,
        blocked_reason=result.blockedReason,
        level=logging.WARNING if result.fallbackUsed else logging.INFO,
    )
    return {
        "character_input": agent_input,
        "draft_reply": result,
        "text": result.draftText,
        "fallback_used": result.fallbackUsed,
        "degraded": result.degraded,
        "fallback_reason": result.blockedReason,
        "error_type": result.errorType,
        "provider": result.provider,
        "model": result.model,
    }


def guard_response(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    intent = classify_dialogue_intent(payload.question.text, payload.dialogueMode)
    draft_reply = state["draft_reply"]
    provider_blocked = bool(draft_reply.degraded and draft_reply.errorType)
    check_input = LightRuleCheckInput(
        requestId=payload.requestId,
        correlationId=payload.correlationId,
        draft=draft_reply,
        characterKnowledgePack=payload.characterKnowledgePack,
        allowedStatement=payload.allowedStatement,
        allowedEventPolicy=payload.allowedEventPolicy,
        forbiddenRefs=list(getattr(payload.characterKnowledgePack, "forbiddenRefs", []) or []) if payload.characterKnowledgePack else [],
        revealAllowed=payload.revealAllowed,
        enforceStatementScope=intent not in {"greeting", "unmatched"} and not provider_blocked,
        allowedContextTerms=_allowed_context_terms(payload),
        intent=intent,
    )
    checked = LightRuleCheck().run(check_input)
    safety = checked.safetyFindings
    if (
        safety.get("repaired", False)
        and not safety.get("leaksSolution", False)
        and intent not in {"greeting", "unmatched"}
        and not bool(state.get("fallback_used", False))
    ):
        repair_input = check_input.model_copy(
            update={"draft": state["draft_reply"].model_copy(update={"draftText": render_dialogue_seed(payload)})}
        )
        repaired_checked = LightRuleCheck().run(repair_input)
        repaired_safety = repaired_checked.safetyFindings
        if not repaired_safety.get("leaksSolution", False) and not repaired_safety.get("violatesCaseFacts", False):
            provider_draft_missing_allowed = normalize_text(payload.allowedStatement.text) not in normalize_text(
                draft_reply.draftText
            )
            seed_repair_is_benign_contract_recovery = bool(
                provider_draft_missing_allowed
                and safety.get("blockedReason") == "case_fact_scope_repaired"
                and _event_policy_has_public_contradiction_context(payload)
            )
            merged_safety = {
                **repaired_safety,
                "repaired": False if seed_repair_is_benign_contract_recovery else True,
                "blocked": False,
                "blockedReason": None
                if seed_repair_is_benign_contract_recovery
                else safety.get("blockedReason") or repaired_safety.get("blockedReason"),
                "blockedTerms": safety.get("blockedTerms") or repaired_safety.get("blockedTerms", []),
                "providerDraftRepaired": True,
                "providerDraftBlockedReason": safety.get("blockedReason"),
                "finalTextSource": "public_seed_after_provider_scope_repair",
            }
            checked = repaired_checked.model_copy(
                update={
                    "repaired": False if seed_repair_is_benign_contract_recovery else repaired_checked.repaired,
                    "blocked": False,
                    "blockedReason": None
                    if seed_repair_is_benign_contract_recovery
                    else safety.get("blockedReason") or repaired_safety.get("blockedReason"),
                    "repairedText": None if seed_repair_is_benign_contract_recovery else repaired_checked.finalText,
                    "safetyFindings": merged_safety,
                }
            )
            safety = checked.safetyFindings
    level = logging.WARNING if safety.get("repaired", False) or safety.get("blockedReason") else logging.INFO
    emit_ai_node_log(
        _context(payload),
        node="LightRuleCheck",
        started_at=started_at,
        provider=state.get("provider"),
        model=state.get("model"),
        fallback_used=bool(state.get("fallback_used", False)),
        repaired=bool(safety.get("repaired", False)),
        blocked_reason=safety.get("blockedReason"),
        level=level,
    )
    return {
        "rule_check_input": check_input,
        "checked_reply": checked,
        "text": checked.finalText,
        "safety_findings": safety,
    }


def propose_events(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    provider_degraded = bool(state.get("fallback_used", False) or state.get("degraded", False))
    gm_input = GameMasterAgentInput(
        requestId=payload.requestId,
        correlationId=payload.correlationId,
        payload=payload,
        checkedReply=state["checked_reply"],
        characterKnowledgePack=payload.characterKnowledgePack,
        allowedEventPolicy=payload.allowedEventPolicy,
        visibleRefs=state["checked_reply"].sourceRefs,
        providerDegraded=provider_degraded,
    )
    proposal = GameMasterAgent().run(gm_input)
    emit_ai_node_log(
        _context(payload),
        node="GameMasterAgent",
        started_at=started_at,
        provider=state.get("provider"),
        model=state.get("model"),
        fallback_used=bool(state.get("fallback_used", False)),
        repaired=bool(state.get("safety_findings", {}).get("repaired", False)),
        blocked_reason=state.get("safety_findings", {}).get("blockedReason"),
        proposed_event_count=len(proposal.proposedEvents),
        level=logging.WARNING if provider_degraded else logging.INFO,
    )
    return {"gm_input": gm_input, "game_master_proposal": proposal, "proposed_events": proposal.proposedEvents}


def format_response(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    safety = state.get("safety_findings", {})
    proposed_events = state.get("proposed_events", [])
    fallback_reason = state.get("fallback_reason")
    intent = classify_dialogue_intent(payload.question.text, payload.dialogueMode)
    checked_reply = state.get("checked_reply")
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
        degraded=bool(state.get("degraded", False) or state.get("fallback_used", False)),
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
                "degraded": bool(state.get("degraded", False) or state.get("fallback_used", False)),
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
        },
        safety=Safety(
            leaksSolution=bool(safety.get("leaksSolution", False)),
            violatesCaseFacts=bool(safety.get("violatesCaseFacts", False)),
            blockedTerms=list(safety.get("blockedTerms", [])),
            fallbackUsed=bool(state.get("fallback_used", False)),
            degraded=bool(state.get("degraded", False) or state.get("fallback_used", False)),
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
        _context(payload),
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


def run_dialogue_graph(payload: DialogueRequest) -> DialogueResponse:
    state = run_langgraph_or_pipeline(
        {"payload": payload},
        [
            ("load_context", load_context),
            ("validate_scope", validate_scope),
            ("CharacterAgent", generate_response),
            ("LightRuleCheck", guard_response),
            ("GameMasterAgent", propose_events),
            ("format_response", format_response),
        ],
    )
    return state["result"]
