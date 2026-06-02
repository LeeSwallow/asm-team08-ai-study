from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.domain.models import Case
from app.infra.case_mapper import case_from_payload
from app.infra.case_orm import CaseRecord
from app.infra.db import Base


SessionFactory = sessionmaker[Session]


class SqlAlchemyCaseStore:
    def __init__(
        self,
        engine_factory: Callable[[], Engine | None],
        session_factory_provider: Callable[[], SessionFactory | None],
    ) -> None:
        self._engine_factory = engine_factory
        self._session_factory_provider = session_factory_provider
        self._schema_ready = False

    @property
    def available(self) -> bool:
        return self._engine_factory() is not None and self._session_factory_provider() is not None

    def seed(self, payloads: list[dict]) -> bool:
        engine = self._engine_factory()
        session_factory = self._session_factory_provider()
        if engine is None or session_factory is None:
            return False
        try:
            if not self._schema_ready:
                Base.metadata.create_all(engine)
                self._schema_ready = True
            with session_factory() as db:
                for payload in payloads:
                    case_id = str(payload["caseId"])
                    existing = db.get(CaseRecord, case_id)
                    if existing is None:
                        db.add(CaseRecord(case_id=case_id, payload=payload))
                    else:
                        existing.payload = payload
                db.commit()
            return True
        except SQLAlchemyError:
            return False

    def list_cases(self) -> list[Case] | None:
        session_factory = self._session_factory_provider()
        if session_factory is None:
            return None
        try:
            with session_factory() as db:
                records = db.query(CaseRecord).order_by(CaseRecord.case_id).all()
                return [case_from_payload(record.payload) for record in records]
        except SQLAlchemyError:
            return None

    def get_case(self, case_id: str) -> Case | None:
        session_factory = self._session_factory_provider()
        if session_factory is None:
            return None
        try:
            with session_factory() as db:
                record = db.get(CaseRecord, case_id)
                return case_from_payload(record.payload) if record is not None else None
        except SQLAlchemyError:
            return None
