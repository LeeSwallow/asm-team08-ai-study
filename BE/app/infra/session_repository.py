from __future__ import annotations

from datetime import datetime

from app.domain.models import SessionState
from app.infra.db import get_session_factory
from app.infra.state_orm import SessionRecord


class SessionRepository:
    def get(self, session_id: str) -> SessionState | None:
        session_factory = get_session_factory()
        if session_factory is None:
            return None
        with session_factory() as db:
            record = db.get(SessionRecord, session_id)
            return self._validate(record.payload) if record is not None else None

    def save(self, session: SessionState) -> SessionState:
        session.updatedAt = datetime.utcnow()
        session_factory = get_session_factory()
        if session_factory is None:
            raise RuntimeError("database session factory is not configured")
        payload = self._dump(session)
        with session_factory() as db:
            db.merge(SessionRecord(session_id=session.sessionId, case_id=session.caseId, payload=payload))
            db.commit()
        return session

    def list_ids(self) -> list[str]:
        session_factory = get_session_factory()
        if session_factory is None:
            return []
        with session_factory() as db:
            return [item[0] for item in db.query(SessionRecord.session_id).order_by(SessionRecord.session_id).all()]

    def _validate(self, payload: dict) -> SessionState:
        if hasattr(SessionState, "model_validate"):
            return SessionState.model_validate(payload)
        return SessionState.parse_obj(payload)

    def _dump(self, session: SessionState) -> dict:
        if hasattr(session, "model_dump"):
            return session.model_dump(mode="json")
        return session.dict()
