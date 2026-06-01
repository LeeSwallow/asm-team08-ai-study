import json
from pathlib import Path
from typing import Dict, List

from sqlalchemy.exc import SQLAlchemyError

from app.domain.models import Case
from app.infra.case_orm import CaseRecord
from app.infra.db import Base, get_engine, get_session_factory


class CaseRepository:
    def __init__(self, cases_dir: Path, use_database: bool = True):
        self.cases_dir = cases_dir
        self.use_database = use_database
        self._cache: Dict[str, Case] = {}
        self._db_ready = False

    def list_cases(self) -> List[Case]:
        db_cases = self._list_cases_from_db()
        if db_cases is not None:
            return sorted(db_cases, key=lambda item: item.caseId)
        self._load_all()
        return sorted(self._cache.values(), key=lambda item: item.caseId)

    def get_case(self, case_id: str) -> Case | None:
        db_case = self._get_case_from_db(case_id)
        if db_case is not None:
            return db_case
        self._load_all()
        return self._cache.get(case_id)

    def _ensure_db_seeded(self) -> bool:
        if not self.use_database:
            return False
        if self._db_ready:
            return True
        engine = get_engine()
        session_factory = get_session_factory()
        if engine is None or session_factory is None:
            return False
        try:
            Base.metadata.create_all(engine)
            with session_factory() as db:
                for path in sorted(self.cases_dir.glob("*.json")):
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    case_id = str(payload["caseId"])
                    existing = db.get(CaseRecord, case_id)
                    if existing is None:
                        db.add(CaseRecord(case_id=case_id, payload=payload))
                    else:
                        existing.payload = payload
                db.commit()
            self._db_ready = True
            return True
        except SQLAlchemyError:
            return False

    def _list_cases_from_db(self) -> List[Case] | None:
        if not self._ensure_db_seeded():
            return None
        session_factory = get_session_factory()
        if session_factory is None:
            return None
        try:
            with session_factory() as db:
                records = db.query(CaseRecord).order_by(CaseRecord.case_id).all()
                return [self._validate(record.payload) for record in records]
        except SQLAlchemyError:
            return None

    def _get_case_from_db(self, case_id: str) -> Case | None:
        if not self._ensure_db_seeded():
            return None
        session_factory = get_session_factory()
        if session_factory is None:
            return None
        try:
            with session_factory() as db:
                record = db.get(CaseRecord, case_id)
                return self._validate(record.payload) if record is not None else None
        except SQLAlchemyError:
            return None

    def _load_all(self) -> None:
        if self._cache:
            return
        for path in sorted(self.cases_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            case = self._validate(data)
            self._cache[case.caseId] = case

    def _validate(self, payload: dict) -> Case:
        if hasattr(Case, "model_validate"):
            return Case.model_validate(payload)
        return Case.parse_obj(payload)
