from __future__ import annotations

from app.application.ports import CaseRepositoryPort
from app.domain.models import Case
from app.infra.db import get_engine, get_session_factory
from app.infra.sqlalchemy_case_store import SqlAlchemyCaseStore


class CaseRepository(CaseRepositoryPort):
    def __init__(self) -> None:
        self._database_store = SqlAlchemyCaseStore(get_engine, get_session_factory)

    def list_cases(self) -> list[Case]:
        cases = self._database_store.list_cases()
        return sorted(cases or [], key=lambda item: item.caseId)

    def get_case(self, case_id: str) -> Case | None:
        if not self._database_store.available:
            return None
        return self._database_store.get_case(case_id)
