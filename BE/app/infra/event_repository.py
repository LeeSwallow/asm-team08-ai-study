from __future__ import annotations

from typing import Iterable

from app.domain.models import EventEntry
from app.infra.db import get_session_factory
from app.infra.state_orm import EventRecord


class EventRepository:
    def append_many(self, events: Iterable[EventEntry]) -> list[EventEntry]:
        stored = list(events)
        if not stored:
            return []
        session_factory = get_session_factory()
        if session_factory is None:
            raise RuntimeError("database session factory is not configured")
        with session_factory() as db:
            for event in stored:
                db.merge(
                    EventRecord(
                        id=event.id,
                        session_id=event.sessionId,
                        case_id=event.caseId,
                        type=event.type,
                        payload=self._dump(event),
                    )
                )
            db.commit()
        return stored

    def list_for_session(self, session_id: str, after_event_id: str | None = None) -> list[EventEntry]:
        session_factory = get_session_factory()
        if session_factory is None:
            return []
        with session_factory() as db:
            records = (
                db.query(EventRecord)
                .filter(EventRecord.session_id == session_id)
                .order_by(EventRecord.created_at, EventRecord.id)
                .all()
            )
        events = [self._validate(record.payload) for record in records]
        if after_event_id:
            index = next((idx for idx, event in enumerate(events) if event.id == after_event_id), None)
            if index is not None:
                return events[index + 1 :]
        return events

    def last_id(self, session_id: str) -> str | None:
        events = self.list_for_session(session_id)
        if not events:
            return None
        return events[-1].id

    def next_index(self, session_id: str) -> int:
        return len(self.list_for_session(session_id)) + 1

    def next_id(self, session_id: str) -> str:
        return f"evt_{self.next_index(session_id):06d}"

    def _validate(self, payload: dict) -> EventEntry:
        if hasattr(EventEntry, "model_validate"):
            return EventEntry.model_validate(payload)
        return EventEntry.parse_obj(payload)

    def _dump(self, event: EventEntry) -> dict:
        if hasattr(event, "model_dump"):
            return event.model_dump(mode="json")
        return event.dict()
