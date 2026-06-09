from __future__ import annotations

import logging
from typing import Any

from app.ai_engine.application.character_agent import CharacterAgent, build_character_agent_input, render_dialogue_seed
from app.ai_engine.application.dialogue_director_agent import DialogueDirectorAgent
from app.ai_engine.application.dialogue_tone_polisher import DialogueTonePolisher
from app.ai_engine.application.game_master_agent import GameMasterAgent
from app.ai_engine.application.knowledge_retriever import CharacterRetrievedContext
from app.ai_engine.application.light_rule_check import LightRuleCheck
from app.ai_engine.core.guard import extract_case_context_terms, normalize_text
from app.ai_engine.core.observability import AiLogContext, emit_ai_node_log, now_ms
from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent
from app.ai_engine.schemas.agents import DialogueDirectorInput, GameMasterAgentInput, LightRuleCheckInput
from app.ai_engine.schemas.common import Safety
from app.ai_engine.schemas.dialogue import DialogueRequest, DialogueResponse


def _context(payload: DialogueRequest) -> AiLogContext:
    return AiLogContext(
        request_id=payload.requestId,
        session_id=payload.sessionId,
        case_id=payload.caseId,
        graph="dialogue",
        suspect_id=payload.suspect.id,
        suspect_name=payload.suspect.name,
        dialogue_mode=payload.dialogueMode,
        question_preview=payload.playerMessage or payload.question.text,
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


def _should_enforce_exact_statement_scope(payload: DialogueRequest, *, intent: str, provider_blocked: bool) -> bool:
    if intent in {"greeting", "unmatched"} or provider_blocked:
        return False
    if _has_public_context_ref(payload):
        return False
    return not bool(payload.interrogationTransition or payload.turnInterpretation)


def _allowed_source_facts(payload: DialogueRequest) -> list[str]:
    raw = getattr(payload.allowedStatement, "sourceFacts", None) or []
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item or "").strip()]


def _has_public_context_ref(payload: DialogueRequest) -> bool:
    refs = payload.allowedStatement.sourceRefs
    policy = payload.allowedEventPolicy
    return bool(
        refs.statementIds
        or refs.evidenceIds
        or refs.timelineIds
        or refs.questionIds
        or refs.contradictionIds
        or _allowed_source_facts(payload)
        or policy.relatedStatementIds
        or policy.relatedQuestionIds
        or policy.relatedEvidenceIds
        or policy.relatedTimelineEventIds
        or policy.relatedContradictionIds
    )


def _allowed_context_terms(payload: DialogueRequest) -> list[str]:
    terms = set(extract_case_context_terms(payload.allowedStatement.text))
    for fact in _allowed_source_facts(payload):
        terms.update(extract_case_context_terms(fact))
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


def retrieve_context(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    pack = payload.characterKnowledgePack
    unlocked_statement_ids = list(getattr(pack, "unlockedStatementIds", []) or []) if pack else []
    unlocked_evidence_ids = list(getattr(pack, "unlockedEvidenceIds", []) or []) if pack else []
    discovered_contradiction_ids = list(getattr(pack, "discoveredContradictionIds", []) or []) if pack else []
    knowledge_retriever = state["knowledge_retriever"]
    retrieved = knowledge_retriever.retrieve_dialogue_context(
        case_id=payload.caseId,
        suspect_id=payload.suspect.id,
        question_text=payload.question.text,
        allowed_statement_text=payload.allowedStatement.text,
        unlocked_statement_ids=unlocked_statement_ids,
        unlocked_evidence_ids=unlocked_evidence_ids,
        discovered_contradiction_ids=discovered_contradiction_ids,
    )
    emit_ai_node_log(
        _context(payload),
        node="KnowledgeRetriever",
        started_at=started_at,
    )
    return {
        "character_context": retrieved.character_context,
        "event_context": retrieved.event_context,
        # Compatibility key for existing LightRule/diagnostic code paths.
        "retrieved_context": retrieved.character_context,
    }


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
        _context(payload),
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
        enforceStatementScope=_should_enforce_exact_statement_scope(payload, intent=intent, provider_blocked=provider_blocked),
        allowedContextTerms=_allowed_context_terms(payload),
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


def _route_after_generate(state: dict[str, Any]) -> str:
    director_plan = state.get("dialogue_director_plan")
    if state.get("fallback_used") or (
        director_plan and director_plan.strategy in {"defensive_pressure", "deflect_unmatched"}
    ):
        return "LightRuleCheck"
    return "DialogueTonePolisher"


def polish_tone(state: dict[str, Any]) -> dict[str, Any]:
    started_at = now_ms()
    payload: DialogueRequest = state["payload"]
    draft_reply = state["draft_reply"]
    polished = DialogueTonePolisher().run(payload, draft_reply)
    tone_polished = polished.draftText != draft_reply.draftText
    emit_ai_node_log(
        _context(payload),
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
            "dialogueDirector": state.get("dialogue_director_plan").model_dump()
            if state.get("dialogue_director_plan")
            else None,
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


_logger = logging.getLogger("app.ai")

_NODES_BEFORE_POLISH: list[tuple[str, Any]] = [
    ("load_context", load_context),
    ("validate_scope", validate_scope),
    ("KnowledgeRetriever", retrieve_context),
    ("DialogueDirectorAgent", direct_dialogue),
    ("CharacterAgent", generate_response),
]

_NODES_AFTER_POLISH: list[tuple[str, Any]] = [
    ("LightRuleCheck", guard_response),
    ("GameMasterAgent", propose_events),
    ("format_response", format_response),
]


def _run_dialogue_pipeline(initial_state: dict[str, Any], reason: str) -> dict[str, Any]:
    _logger.warning(
        "ai graph runner fallback selected",
        extra={
            "service": "ai",
            "graph": "dialogue",
            "node": "graph_runner",
            "graph_runner": "pipeline",
            "graph_fallback_reason": reason,
        },
    )
    state: dict[str, Any] = {**initial_state, "graph_runner": "pipeline", "graph_fallback_reason": reason}
    for _, node in _NODES_BEFORE_POLISH:
        state.update(node(state))
    if _route_after_generate(state) == "DialogueTonePolisher":
        state.update(polish_tone(state))
    for _, node in _NODES_AFTER_POLISH:
        state.update(node(state))
    return state


def run_dialogue_graph(payload: DialogueRequest, knowledge_retriever: Any) -> DialogueResponse:
    initial_state: dict[str, Any] = {"payload": payload, "knowledge_retriever": knowledge_retriever}

    try:
        from langgraph.graph import END, StateGraph
        from typing_extensions import TypedDict
    except ImportError as exc:
        return _run_dialogue_pipeline(initial_state, f"langgraph_import_error:{type(exc).__name__}")["result"]

    try:
        class WorkflowState(TypedDict, total=False):
            payload: Any
            knowledge_retriever: Any
            result: Any
            text: str
            character_context: Any
            event_context: Any
            retrieved_context: Any
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
            tone_polished: bool

        graph: StateGraph = StateGraph(WorkflowState)

        for name, node in [*_NODES_BEFORE_POLISH, ("DialogueTonePolisher", polish_tone), *_NODES_AFTER_POLISH]:
            graph.add_node(name, node)

        graph.set_entry_point(_NODES_BEFORE_POLISH[0][0])
        for i in range(len(_NODES_BEFORE_POLISH) - 1):
            graph.add_edge(_NODES_BEFORE_POLISH[i][0], _NODES_BEFORE_POLISH[i + 1][0])

        graph.add_conditional_edges(
            "CharacterAgent",
            _route_after_generate,
            {"DialogueTonePolisher": "DialogueTonePolisher", "LightRuleCheck": "LightRuleCheck"},
        )
        graph.add_edge("DialogueTonePolisher", "LightRuleCheck")

        for i in range(len(_NODES_AFTER_POLISH) - 1):
            graph.add_edge(_NODES_AFTER_POLISH[i][0], _NODES_AFTER_POLISH[i + 1][0])
        graph.add_edge(_NODES_AFTER_POLISH[-1][0], END)

        state = graph.compile().invoke({**initial_state, "graph_runner": "langgraph"})
        return state["result"]
    except Exception as exc:
        return _run_dialogue_pipeline(initial_state, f"langgraph_runtime_error:{type(exc).__name__}")["result"]
