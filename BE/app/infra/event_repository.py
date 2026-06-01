import json
from pathlib import Path
from typing import Iterable, List

from app.domain.models import EventEntry


class EventRepository:
    def __init__(self, events_dir: Path):
        self.events_dir = events_dir
        self.events_dir.mkdir(parents=True, exist_ok=True)

    def append_many(self, events: Iterable[EventEntry]) -> List[EventEntry]:
        stored = list(events)
        if not stored:
            return []
        existing = self.list_for_session(stored[0].sessionId)
        all_events = [*existing, *stored]
        payload = [self._dump(event) for event in all_events]
        self._path(stored[0].sessionId).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return stored

    def list_for_session(self, session_id: str, after_event_id: str | None = None) -> List[EventEntry]:
        path = self._path(session_id)
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        events = [self._validate(item) for item in raw]
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

    def _path(self, session_id: str) -> Path:
        return self.events_dir / f"{session_id}.json"

    def _validate(self, payload: dict) -> EventEntry:
        if hasattr(EventEntry, "model_validate"):
            return EventEntry.model_validate(payload)
        return EventEntry.parse_obj(payload)

    def _dump(self, event: EventEntry) -> dict:
        if hasattr(event, "model_dump"):
            return event.model_dump(mode="json")
        return event.dict()
