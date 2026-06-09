from __future__ import annotations

import logging
from typing import Any

from app.ai_engine.agents.character_agent import CharacterAgent, build_character_agent_input, render_dialogue_seed
from app.ai_engine.agents.dialogue_director_agent import DialogueDirectorAgent
from app.ai_engine.agents.dialogue_tone_polisher import DialogueTonePolisher
from app.ai_engine.agents.game_master_agent import GameMasterAgent
from app.ai_engine.agents.light_rule_check_agent import LightRuleCheck
from app.ai_engine.core.observability import emit_ai_node_log, now_ms
from app.ai_engine.core.text_normalization import normalize_text
from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent
from app.ai_engine.schemas.agents import DialogueDirectorInput, GameMasterAgentInput, LightRuleCheckInput
from app.ai_engine.schemas.dialogue import DialogueRequest
from app.ai_engine.schemas.retrieval import CharacterRetrievedContext


from app.ai_engine.graph.dialogue_context_nodes import (
    allowed_context_terms,
    dialogue_log_context,
    event_policy_has_public_contradiction_context,
    should_enforce_exact_statement_scope,
)


def direct_dialogue(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    plan = DialogueDirectorAgent().run(
        DialogueDirectorInput(
            payload=payload,
            retrieved_context=state.get("character_context"),
        )
    )
    emit_ai_node_log(
        dialogue_log_context(payload),
        node="DialogueDirectorAgent",
        started_at=started_at,
        repaired=bool(plan.seedText),
        blocked_reason=plan.reason,
    )
    return {"dialogue_director_plan": plan}


def generate_response(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    retrieved: CharacterRetrievedContext | None = state.get("character_context")
    director_plan = state.get("dialogue_director_plan")
    agent_input = build_character_agent_input(payload, director_plan)
    result = CharacterAgent().run(agent_input, retrieved_context=retrieved)
    emit_ai_node_log(
        dialogue_log_context(payload),
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
        enforceStatementScope=should_enforce_exact_statement_scope(payload, intent=intent, provider_blocked=provider_blocked),
        allowedContextTerms=allowed_context_terms(payload),
        intent=intent,
        suspectName=payload.suspect.name,
        retrieved_context=state.get("character_context"),
        dialogueDirectorPlan=state.get("dialogue_director_plan"),
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
            update={
                "draft": state["draft_reply"].model_copy(
                    update={"draftText": render_dialogue_seed(payload, state.get("dialogue_director_plan"))}
                )
            }
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
                and event_policy_has_public_contradiction_context(payload)
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
        dialogue_log_context(payload),
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


def polish_tone(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    draft_reply = state["draft_reply"]
    director_plan = state.get("dialogue_director_plan")
    if director_plan and director_plan.strategy in {"defensive_pressure", "deflect_unmatched", "small_talk_boundary"}:
        emit_ai_node_log(
            dialogue_log_context(payload),
            node="DialogueTonePolisher",
            started_at=started_at,
            provider=state.get("provider"),
            model=state.get("model"),
            fallback_used=bool(state.get("fallback_used", False)),
            repaired=False,
        )
        return {
            "draft_reply": draft_reply,
            "text": draft_reply.draftText,
            "tone_polished": False,
        }
    polished = DialogueTonePolisher().run(payload, draft_reply)
    tone_polished = polished.draftText != draft_reply.draftText
    emit_ai_node_log(
        dialogue_log_context(payload),
        node="DialogueTonePolisher",
        started_at=started_at,
        provider=state.get("provider"),
        model=state.get("model"),
        fallback_used=bool(state.get("fallback_used", False)),
        repaired=tone_polished,
    )
    return {
        "draft_reply": polished,
        "text": polished.draftText,
        "tone_polished": tone_polished,
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
        event_context=state.get("event_context"),
    )
    proposal = GameMasterAgent().run(gm_input)
    emit_ai_node_log(
        dialogue_log_context(payload),
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

