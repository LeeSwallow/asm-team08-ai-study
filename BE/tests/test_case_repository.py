import shutil
from pathlib import Path

from app.core.config import get_settings
from app.infra.case_repository import CaseRepository
from app.infra.db import get_engine, get_session_factory


def test_case_repository_seeds_and_reads_case_from_orm(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    shutil.copytree(Path("data/cases"), data_dir / "cases")
    monkeypatch.setenv("BE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("BE_DATABASE_URL", f"sqlite:///{tmp_path / 'cases.db'}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()

    repo = CaseRepository(data_dir / "cases", use_database=True)
    case = repo.get_case("case_001")

    assert case is not None
    assert case.caseId == "case_001"
    assert case.suspects[0].speechStyle["tone"] == "defensive"
    assert case.suspects[0].personaVariants
