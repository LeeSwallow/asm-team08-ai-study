import logging
from uuid import uuid4

from app.domain.case_engine import pressure_state, visible_timeline
from app.domain.event_types import EventType, GAME_MASTER_PUBLIC_EVENT_TYPES, NOTE_EVENT_TYPES, SUPPORTED_EVENT_TYPES
from app.domain.models import Case, EventEntry, NoteEntry, SessionState

logger = logging.getLogger(__name__)


class EventProcessor:
    def __init__(self, start_index: int):
        self._next_event_index = start_index

    def process_dialogue_events(
        self,
        session: SessionState,
        case: Case,
        suspect_id: str,
        player_message: str,
        answer: str,
        proposed_events: list[dict] | None,
        allow_implicit_note: bool = True,
        allowed_event_types: set[str] | None = None,
        allowed_event_policy: dict | None = None,
    ) -> list[EventEntry]:
        events: list[EventEntry] = []
        proposals = proposed_events or []
        seen_candidate_ids: set[str] = set()
        for proposal in proposals:
            event_type = proposal.get("type") or proposal.get("eventType")
            payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
            if event_type == EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value:
                contradiction_id = str(payload.get("contradictionId") or "")
                if contradiction_id and contradiction_id in seen_candidate_ids:
                    continue
                if contradiction_id:
                    seen_candidate_ids.add(contradiction_id)
            event = self._validate_proposed_event(session, case, proposal, allowed_event_types, allowed_event_policy)
            if event is not None:
                events.append(event)

        if allow_implicit_note:
            self._log_rejected_event(session, case, EventType.NOTE_FACT_ADDED.value, "implicit_note_creation_disabled")

        self._append_unlock_events(session, case, events)

        events.append(self._new_event(session, case, EventType.VISUAL_STATE_CHANGED, build_visual_state(session, case, suspect_id)))
        return events

    def _append_unlock_events(self, session: SessionState, case: Case, events: list[EventEntry]) -> None:
        evidence_ids = {item.evidenceId for item in case.evidence}
        for item_id in session.newlyUnlockedIds:
            if item_id in evidence_ids:
                events.append(self._new_event(session, case, EventType.EVIDENCE_UNLOCKED, {"evidenceId": item_id}))
        existing_timeline_sources = {
            event.payload.get("sourceId")
            for event in events
            if event.type == EventType.TIMELINE_EVENT_REVEALED.value
        }
        for timeline_item in visible_timeline(case, session):
            source_id = timeline_item.get("sourceId")
            if source_id in session.newlyUnlockedIds and source_id not in existing_timeline_sources:
                events.append(self._new_event(session, case, EventType.TIMELINE_EVENT_REVEALED, timeline_item))
                existing_timeline_sources.add(source_id)

    def _validate_proposed_event(
        self,
        session: SessionState,
        case: Case,
        proposal: dict,
        allowed_event_types: set[str] | None,
        allowed_event_policy: dict | None,
    ) -> EventEntry | None:
        event_type = proposal.get("type") or proposal.get("eventType")
        payload = proposal.get("payload") or {}
        if allowed_event_types is not None and event_type not in GAME_MASTER_PUBLIC_EVENT_TYPES:
            self._log_rejected_event(session, case, event_type, "ai_event_type_not_public_gamemaster_event")
            return None
        if allowed_event_types is not None and event_type not in allowed_event_types:
            self._log_rejected_event(session, case, event_type, "event_type_not_allowed_for_dialogue_mode")
            return None
        if event_type not in SUPPORTED_EVENT_TYPES or not isinstance(payload, dict):
            self._log_rejected_event(session, case, event_type, "unsupported_type_or_payload")
            return None

        if event_type == EventType.NOTE_FACT_ADDED.value:
            if not self._note_fact_is_in_turn_policy(payload, allowed_event_policy):
                self._log_rejected_event(session, case, event_type, "note_source_not_related_to_turn_policy")
                return None
            return self._validate_note_fact_event(session, case, payload)

        if event_type == EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value:
            if not self._contradiction_is_in_turn_policy(payload, allowed_event_policy):
                self._log_rejected_event(session, case, event_type, "contradiction_not_related_to_turn_policy")
                return None
            return self._validate_contradiction_note_event(session, case, payload)

        if event_type == EventType.EVIDENCE_UNLOCKED.value:
            evidence_id = str(payload.get("evidenceId") or payload.get("id") or "")
            evidence = next((item for item in case.evidence if item.evidenceId == evidence_id), None)
            if evidence is None or evidence_id not in session.newlyUnlockedIds:
                self._log_rejected_event(session, case, event_type, "evidence_not_newly_unlocked")
                return None
            return self._new_event(session, case, EventType.EVIDENCE_UNLOCKED, {"evidenceId": evidence_id})

        if event_type == EventType.TIMELINE_EVENT_REVEALED.value:
            source_id = str(payload.get("sourceId") or "")
            visible_items = visible_timeline(case, session)
            visible_source_ids = {item.get("sourceId") for item in visible_items}
            if source_id not in visible_source_ids:
                self._log_rejected_event(session, case, event_type, "timeline_source_not_visible")
                return None
            timeline_item = next(item for item in visible_items if item.get("sourceId") == source_id)
            return self._new_event(session, case, EventType.TIMELINE_EVENT_REVEALED, timeline_item)

        if event_type == EventType.TENSION_CHANGED.value:
            self._log_rejected_event(session, case, event_type, "ai_owned_tension_not_allowed")
            return None

        if event_type == EventType.VISUAL_STATE_CHANGED.value:
            target_id = str(payload.get("suspectId") or session.selectedSuspectId or "")
            if target_id not in {suspect.characterId for suspect in case.suspects}:
                self._log_rejected_event(session, case, event_type, "suspect_not_found")
                return None
            return self._new_event(session, case, EventType.VISUAL_STATE_CHANGED, build_visual_state(session, case, target_id))

        if event_type == EventType.BOOKMARK_SUGGESTED.value:
            target_type = str(payload.get("targetType") or "")
            target_id = str(payload.get("targetId") or "")
            if not target_is_visible(session, target_type, target_id):
                self._log_rejected_event(session, case, event_type, "bookmark_target_not_visible")
                return None
            return self._new_event(
                session,
                case,
                EventType.BOOKMARK_SUGGESTED,
                {"targetType": target_type, "targetId": target_id},
            )

        if event_type == EventType.VISUAL_REACTION_SUGGESTED.value:
            target_id = str(payload.get("suspectId") or session.selectedSuspectId or "")
            if target_id not in {suspect.characterId for suspect in case.suspects}:
                self._log_rejected_event(session, case, event_type, "suspect_not_found")
                return None
            visual_state = build_visual_state(session, case, target_id)
            return self._new_event(session, case, EventType.VISUAL_REACTION_SUGGESTED, visual_state)

        return None

    def _note_fact_is_in_turn_policy(self, payload: dict, allowed_event_policy: dict | None) -> bool:
        if allowed_event_policy is None:
            return True
        source_type = str(payload.get("sourceType") or "")
        source_id = str(payload.get("sourceId") or payload.get("targetId") or "")
        if source_type == "statement":
            return source_id in set(allowed_event_policy.get("relatedStatementIds") or [])
        if source_type == "evidence":
            return source_id in set(allowed_event_policy.get("relatedEvidenceIds") or [])
        if source_type == "timeline":
            return source_id in set(allowed_event_policy.get("relatedTimelineEventIds") or [])
        if source_type == "record":
            return source_id in set(allowed_event_policy.get("relatedRecordIds") or [])
        return False

    def _contradiction_is_in_turn_policy(self, payload: dict, allowed_event_policy: dict | None) -> bool:
        if allowed_event_policy is None:
            return True
        contradiction_id = str(payload.get("contradictionId") or "")
        if contradiction_id not in set(allowed_event_policy.get("relatedContradictionIds") or []):
            return False
        statement_ids = set(payload.get("statementIds") or [])
        evidence_ids = set(payload.get("evidenceIds") or [])
        allowed_statement_ids = set(allowed_event_policy.get("relatedStatementIds") or [])
        allowed_evidence_ids = set(allowed_event_policy.get("relatedEvidenceIds") or [])
        return statement_ids.issubset(allowed_statement_ids) and evidence_ids.issubset(allowed_evidence_ids)

    def _validate_note_fact_event(self, session: SessionState, case: Case, payload: dict) -> EventEntry | None:
        source_type = str(payload.get("sourceType") or "")
        source_id = str(payload.get("sourceId") or payload.get("targetId") or "")
        safe_text = self._safe_note_text_for_source(session, case, source_type, source_id)
        if safe_text is None:
            self._log_rejected_event(session, case, EventType.NOTE_FACT_ADDED.value, "note_source_not_visible")
            return None
        note = NoteEntry(id=f"note_{uuid4().hex}", text=safe_text, tags=[EventType.NOTE_FACT_ADDED.value.lower()])
        session.notes.append(note)
        return self._new_event(
            session,
            case,
            EventType.NOTE_FACT_ADDED,
            {"text": safe_text, "noteId": note.id, "sourceType": source_type, "sourceId": source_id},
        )

    def _validate_contradiction_note_event(self, session: SessionState, case: Case, payload: dict) -> EventEntry | None:
        contradiction_id = str(payload.get("contradictionId") or "")
        contradiction = next((item for item in case.contradictions if item.contradictionId == contradiction_id), None)
        if contradiction is None:
            self._log_rejected_event(session, case, EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value, "contradiction_not_found")
            return None
        if not set(contradiction.requiredStatementIds).issubset(set(session.unlockedStatementIds)):
            self._log_rejected_event(session, case, EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value, "required_statement_not_visible")
            return None
        if not set(contradiction.requiredEvidenceIds).issubset(set(session.unlockedEvidenceIds)):
            self._log_rejected_event(session, case, EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value, "required_evidence_not_visible")
            return None
        note_text = f"모순 후보: {contradiction.title}"
        note = NoteEntry(
            id=f"note_{uuid4().hex}",
            text=note_text,
            tags=[EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value.lower()],
            linkedStatementIds=list(contradiction.requiredStatementIds),
            linkedEvidenceIds=list(contradiction.requiredEvidenceIds),
        )
        session.notes.append(note)
        return self._new_event(
            session,
            case,
            EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED,
            {
                "text": note_text,
                "noteId": note.id,
                "contradictionId": contradiction.contradictionId,
                "statementIds": list(contradiction.requiredStatementIds),
                "evidenceIds": list(contradiction.requiredEvidenceIds),
                "timelineIds": _timeline_ids_for_sources(
                    case,
                    session,
                    [*contradiction.requiredStatementIds, *contradiction.requiredEvidenceIds],
                ),
                "submitEligible": True,
            },
        )

    def _safe_note_text_for_source(self, session: SessionState, case: Case, source_type: str, source_id: str) -> str | None:
        if source_type == "statement" and source_id in session.unlockedStatementIds:
            statement = next((item for item in case.statements if item.statementId == source_id), None)
            return statement.text if statement else None
        if source_type == "evidence" and source_id in session.unlockedEvidenceIds:
            evidence = next((item for item in case.evidence if item.evidenceId == source_id), None)
            return f"단서 확인: {evidence.name} - {evidence.description}" if evidence else None
        if source_type == "record" and source_id in session.unlockedRecordIds:
            record = next((item for item in case.records if item.recordId == source_id), None)
            return f"기록 확인: {record.name} - {record.description}" if record else None
        if source_type == "timeline":
            item = next((entry for entry in visible_timeline(case, session) if entry.get("sourceId") == source_id), None)
            return f"타임라인 확인: {item.get('time')} {item.get('title')}" if item else None
        return None

    def _new_event(self, session: SessionState, case: Case, event_type: EventType, payload: dict) -> EventEntry:
        event_id = f"evt_{self._next_event_index:06d}"
        self._next_event_index += 1
        return EventEntry(
            id=event_id,
            sessionId=session.sessionId,
            caseId=case.caseId,
            type=event_type.value,
            payload=payload,
        )

    def _log_rejected_event(self, session: SessionState, case: Case, event_type: object, reason: str) -> None:
        logger.warning(
            "rejected proposed event",
            extra={
                "service": "backend",
                "session_id": session.sessionId,
                "case_id": case.caseId,
                "event_type": event_type,
                "reason": reason,
                "fallback_used": False,
            },
        )


def build_visual_state(session: SessionState, case: Case, suspect_id: str | None = None) -> dict:
    selected = suspect_id or session.selectedSuspectId or (case.suspects[0].characterId if case.suspects else None)
    pressure = session.pressureBySuspect.get(selected, 0) if selected else 0
    state = pressure_state(pressure)
    return {
        "backgroundId": f"{case.sceneId}_{session.phase}",
        "suspectId": selected,
        "characterImageState": emotional_state(pressure),
        "emotionalState": emotional_state(pressure),
        "expression": emotional_state(pressure),
        "pressureState": state,
        "tensionLevel": tension_level(pressure),
        "tensionScore": pressure,
    }


def emotional_state(pressure: int) -> str:
    if pressure >= 70:
        return "breakdown"
    if pressure >= 45:
        return "shocked"
    if pressure >= 30:
        return "defensive"
    if pressure >= 15:
        return "wary"
    return "neutral"


def tension_level(pressure: int) -> str:
    if pressure >= 70:
        return "critical"
    if pressure >= 45:
        return "high"
    if pressure >= 30:
        return "medium"
    return "low"


def _timeline_ids_for_sources(case: Case, session: SessionState, source_ids: list[str]) -> list[str]:
    source_set = set(source_ids)
    timeline_ids = []
    for item in visible_timeline(case, session):
        if item.get("sourceId") not in source_set:
            continue
        timeline_id = str(item.get("timelineId") or item.get("sourceId") or "")
        if timeline_id and timeline_id not in timeline_ids:
            timeline_ids.append(timeline_id)
    return timeline_ids


def target_is_visible(session: SessionState, target_type: str, target_id: str) -> bool:
    visible_ids = {
        "dialogue": {item.id for item in session.dialogueLog},
        "statement": set(session.unlockedStatementIds),
        "evidence": set(session.unlockedEvidenceIds),
        "record": set(session.unlockedRecordIds),
        "relation": set(session.unlockedRelationIds),
    }
    return target_id in visible_ids.get(target_type, set())
