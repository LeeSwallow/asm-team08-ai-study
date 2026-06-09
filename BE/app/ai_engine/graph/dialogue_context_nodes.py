from __future__ import annotations

from typing import Any

from app.ai_engine.core.dialogue_guard import extract_case_context_terms
from app.ai_engine.core.observability import AiLogContext, emit_ai_node_log, now_ms
from app.ai_engine.schemas.dialogue import DialogueRequest


def dialogue_log_context(payload: DialogueRequest) -> AiLogContext:
    return AiLogContext(
        request_id=payload.requestId,
        session_id=payload.sessionId,
        case_id=payload.caseId,
        graph="dialogue",
        suspect_id=payload.suspect.id,
        suspect_name=payload.suspect.name,
        dialogue_mode=payload.dialogueMode,
        question_preview=getattr(payload, "playerMessage", None) or payload.question.text,
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
    emit_ai_node_log(dialogue_log_context(payload), node="load_context", started_at=started_at)
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
    emit_ai_node_log(dialogue_log_context(payload), node="validate_scope", started_at=started_at)
    return result


def should_enforce_exact_statement_scope(payload: DialogueRequest, *, intent: str, provider_blocked: bool) -> bool:
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


def allowed_context_terms(payload: DialogueRequest) -> list[str]:
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


def event_policy_has_public_contradiction_context(payload: DialogueRequest) -> bool:
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
        dialogue_log_context(payload),
        node="KnowledgeRetriever",
        started_at=started_at,
    )
    return {
        "character_context": retrieved.character_context,
        "event_context": retrieved.event_context,
        # Compatibility key for existing LightRule/diagnostic code paths.
        "retrieved_context": retrieved.character_context,
    }

