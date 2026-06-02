from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from app.api import deps
from app.core.config import get_settings
from app.infra.case_orm import CaseRecord
from app.infra.db import Base, ensure_schema, get_engine, get_session_factory


@pytest.fixture
def seed_case_database(tmp_path, monkeypatch) -> Callable[[], None]:
    def _seed() -> None:
        monkeypatch.setenv("BE_DATABASE_URL", f"sqlite:///{tmp_path / 'cases.db'}")
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        ensure_schema.cache_clear()
        deps.get_case_repository.cache_clear()

        engine = get_engine()
        session_factory = get_session_factory()
        assert engine is not None
        assert session_factory is not None

        Base.metadata.create_all(engine)
        with session_factory() as db:
            for path in sorted(Path("data/cases").glob("*.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                db.merge(CaseRecord(case_id=str(payload["caseId"]), payload=payload))
            db.commit()

    return _seed
