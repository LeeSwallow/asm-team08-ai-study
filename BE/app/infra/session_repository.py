from datetime import datetime
from pathlib import Path
from typing import List

from app.domain.models import SessionState


class SessionRepository:
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def get(self, session_id: str) -> SessionState | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        if hasattr(SessionState, "model_validate_json"):
            return SessionState.model_validate_json(raw)
        return SessionState.parse_raw(raw)

    def save(self, session: SessionState) -> SessionState:
        session.updatedAt = datetime.utcnow()
        if hasattr(session, "model_dump_json"):
            payload = session.model_dump_json(indent=2)
        else:
            payload = session.json(ensure_ascii=False, indent=2)
        self._path(session.sessionId).write_text(payload, encoding="utf-8")
        return session

    def list_ids(self) -> List[str]:
        return [path.stem for path in sorted(self.sessions_dir.glob("*.json"))]

    def _path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.json"
