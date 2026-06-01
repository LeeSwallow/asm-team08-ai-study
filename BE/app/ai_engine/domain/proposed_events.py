from __future__ import annotations

from typing import Any, cast

from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent
from app.ai_engine.schemas.common import ProposedEvent
from app.ai_engine.schemas.dialogue import DialogueRequest

AI_PROPOSABLE_EVENT_TYPES = {
    "NOTE_FACT_ADDED",
    "NOTE_CONTRADICTION_CANDIDATE_ADDED",
    "BOOKMARK_SUGGESTED",
}


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _policy_value(policy: object, name: str) -> object | None:
    return getattr(policy, name, None)


def _event_source_refs(
    *,
    statement_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    timeline_ids: list[str] | None = None,
    question_ids: list[str] | None = None,
    contradiction_ids: list[str] | None = None,
) -> dict[str, list[str]]:
    refs = {
        "statementIds": _unique(statement_ids or []),
        "evidenceIds": _unique(evidence_ids or []),
        "timelineIds": _unique(timeline_ids or []),
        "questionIds": _unique(question_ids or []),
        "contradictionIds": _unique(contradiction_ids or []),
    }
    return {key: value for key, value in refs.items() if value}


def _context_values(event_context: object | None, name: str) -> list[str]:
    value = getattr(event_context, name, []) if event_context is not None else []
    return _unique([str(item) for item in value if item])


def _contradiction_payload(
    payload: DialogueRequest,
    reason_code: str,
    *,
    event_context: object | None = None,
) -> dict[str, object]:
    source_refs = payload.allowedStatement.sourceRefs
    statement_ids = _unique(
        payload.allowedEventPolicy.relatedStatementIds
        or source_refs.statementIds
        or _context_values(event_context, "matched_statement_ids")
        or [payload.allowedStatement.id]
    )
    evidence_ids = _unique(
        payload.allowedEventPolicy.relatedEvidenceIds
        or source_refs.evidenceIds
        or _context_values(event_context, "matched_evidence_ids")
    )
    timeline_ids = _unique(
        payload.allowedEventPolicy.relatedTimelineEventIds
        or source_refs.timelineIds
        or _context_values(event_context, "matched_timeline_ids")
    )
    contradiction_id = _policy_value(payload.allowedEventPolicy, "contradictionId")
    if contradiction_id is None and payload.allowedEventPolicy.relatedContradictionIds:
        contradiction_id = payload.allowedEventPolicy.relatedContradictionIds[0]
    if contradiction_id is None:
        candidate_ids = _context_values(event_context, "candidate_contradiction_ids")
        if candidate_ids:
            contradiction_id = candidate_ids[0]
    confidence_value = _policy_value(payload.allowedEventPolicy, "confidence")
    try:
        confidence = float(cast(Any, confidence_value)) if confidence_value is not None else 0.5
    except (TypeError, ValueError):
        confidence = 0.5
    return {
        "candidateId": str(_policy_value(payload.allowedEventPolicy, "candidateId") or f"candidate_{payload.allowedStatement.id}"),
        "contradictionId": contradiction_id,
        "suspectId": payload.suspect.id,
        "statementIds": statement_ids,
        "evidenceIds": evidence_ids,
        "timelineIds": timeline_ids,
        "confidence": confidence,
        "reasonCode": str(_policy_value(payload.allowedEventPolicy, "reasonCode") or reason_code),
        "displayText": str(_policy_value(payload.allowedEventPolicy, "displayText") or payload.allowedStatement.text),
        "submitEligible": bool(_policy_value(payload.allowedEventPolicy, "submitEligible") or False),
    }


def _contradiction_event(
    payload: DialogueRequest,
    reason_code: str,
    *,
    event_context: object | None = None,
) -> ProposedEvent:
    event_payload = _contradiction_payload(payload, reason_code, event_context=event_context)
    return ProposedEvent(
        type="NOTE_CONTRADICTION_CANDIDATE_ADDED",
        payload=event_payload,
        sourceRefs=_event_source_refs(
            statement_ids=cast(list[str], event_payload["statementIds"]),
            evidence_ids=cast(list[str], event_payload["evidenceIds"]),
            timeline_ids=cast(list[str], event_payload["timelineIds"]),
            contradiction_ids=[str(event_payload["contradictionId"])] if event_payload["contradictionId"] else [],
        ),
        confidence=cast(float, event_payload["confidence"]),
    )


def _timeline_conflict_present(payload: DialogueRequest) -> bool:
    if not payload.allowedEventPolicy.relatedContradictionIds:
        return False
    source_refs = payload.allowedStatement.sourceRefs
    related_statement_ids = set(payload.allowedEventPolicy.relatedStatementIds or source_refs.statementIds)
    related_evidence_ids = set(payload.allowedEventPolicy.relatedEvidenceIds or source_refs.evidenceIds)
    if not related_statement_ids or not related_evidence_ids:
        return False
    timeline = payload.characterTimeline.events if payload.characterTimeline else []
    has_claimed_alibi = any(
        (getattr(event, "sourceType", None) == "statement" or bool(getattr(event, "claimedLocation", None)))
        and bool(set(getattr(event, "relatedStatementIds", []) or [getattr(event, "sourceId", "")]) & related_statement_ids)
        for event in timeline
    )
    has_counter_evidence = any(
        getattr(event, "sourceType", None) == "evidence"
        and bool(set(getattr(event, "relatedEvidenceIds", []) or [getattr(event, "sourceId", "")]) & related_evidence_ids)
        for event in timeline
    )
    return has_claimed_alibi and has_counter_evidence


def propose_dialogue_events(
    payload: DialogueRequest,
    *,
    provider_degraded: bool = False,
    event_context: object | None = None,
) -> list[ProposedEvent]:
    """Return BE-validated event suggestions only; never mutate game/session state."""
    if provider_degraded:
        return []

    allowed_types = [
        event_type
        for event_type in payload.allowedEventPolicy.allowedTypes
        if event_type in AI_PROPOSABLE_EVENT_TYPES
    ]
    source_refs = payload.allowedStatement.sourceRefs
    related_ids = _unique(
        payload.allowedEventPolicy.relatedEvidenceIds
        or source_refs.evidenceIds
        or _context_values(event_context, "matched_evidence_ids")
    )
    related_timeline_ids = _unique(
        payload.allowedEventPolicy.relatedTimelineEventIds
        or source_refs.timelineIds
        or _context_values(event_context, "matched_timeline_ids")
    )
    related_statement_ids = _unique(
        payload.allowedEventPolicy.relatedStatementIds
        or source_refs.statementIds
        or _context_values(event_context, "matched_statement_ids")
    )
    related_question_ids = _unique(payload.allowedEventPolicy.relatedQuestionIds or source_refs.questionIds)
    statement_text = payload.allowedStatement.text
    source_statement_id = payload.allowedStatement.id
    intent = classify_dialogue_intent(payload.question.text, payload.dialogueMode)

    if intent in {"greeting", "unmatched"}:
        return []

    if intent == "evidence" and "NOTE_CONTRADICTION_CANDIDATE_ADDED" in allowed_types:
        return [_contradiction_event(payload, intent, event_context=event_context)]

    if (
        intent == "location_time"
        and "NOTE_CONTRADICTION_CANDIDATE_ADDED" in allowed_types
        and _timeline_conflict_present(payload)
    ):
        return [
            _contradiction_event(payload, "timeline_conflict", event_context=event_context)
        ]

    if "NOTE_FACT_ADDED" in allowed_types:
        event_payload: dict[str, object] = {
            "sourceType": "statement",
            "sourceId": source_statement_id,
            "statementIds": related_statement_ids or [source_statement_id],
            "evidenceIds": related_ids,
            "timelineIds": related_timeline_ids,
        }
        if related_statement_ids:
            event_payload["statementIds"] = related_statement_ids
        if related_timeline_ids:
            event_payload["timelineIds"] = related_timeline_ids
        if related_ids:
            event_payload["evidenceIds"] = related_ids
        if related_question_ids:
            event_payload["questionIds"] = related_question_ids
        return [
            ProposedEvent(
                type="NOTE_FACT_ADDED",
                payload=event_payload,
                sourceRefs=_event_source_refs(
                    statement_ids=cast(list[str], event_payload.get("statementIds", [])),
                    evidence_ids=cast(list[str], event_payload.get("evidenceIds", [])),
                    timeline_ids=cast(list[str], event_payload.get("timelineIds", [])),
                    question_ids=cast(list[str], event_payload.get("questionIds", [])),
                ),
                confidence=0.75,
            )
        ]

    if "NOTE_CONTRADICTION_CANDIDATE_ADDED" in allowed_types:
        return [_contradiction_event(payload, intent, event_context=event_context)]

    if "BOOKMARK_SUGGESTED" in allowed_types:
        return [
            ProposedEvent(
                type="BOOKMARK_SUGGESTED",
                payload={"sourceType": "statement", "sourceId": source_statement_id, "questionIds": related_question_ids},
                sourceRefs=_event_source_refs(statement_ids=[source_statement_id], question_ids=related_question_ids),
                confidence=0.6,
            )
        ]

    return []
