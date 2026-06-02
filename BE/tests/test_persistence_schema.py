from __future__ import annotations

from pathlib import Path

from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql, sqlite

from app.infra.case_orm import CaseRecord
from app.infra.state_orm import EventRecord, SessionRecord


def _postgres_ddl(model: type) -> str:
    return str(CreateTable(model.__table__).compile(dialect=postgresql.dialect()))


def _sqlite_ddl(model: type) -> str:
    return str(CreateTable(model.__table__).compile(dialect=sqlite.dialect()))


def test_case_session_event_orm_schema_uses_postgres_jsonb_and_sqlite_json_variant() -> None:
    postgres_ddl = "\n".join(
        [
            _postgres_ddl(CaseRecord),
            _postgres_ddl(SessionRecord),
            _postgres_ddl(EventRecord),
        ]
    )
    sqlite_ddl = "\n".join(
        [
            _sqlite_ddl(CaseRecord),
            _sqlite_ddl(SessionRecord),
            _sqlite_ddl(EventRecord),
        ]
    )

    assert "payload JSONB NOT NULL" in postgres_ddl
    assert "payload JSON NOT NULL" in sqlite_ddl
    assert "FOREIGN KEY(case_id) REFERENCES cases (case_id) ON DELETE RESTRICT" in postgres_ddl
    assert "FOREIGN KEY(session_id) REFERENCES sessions (session_id) ON DELETE CASCADE" in postgres_ddl


def test_init_schema_matches_runtime_aggregate_tables() -> None:
    schema_sql = Path("scripts/init_schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE cases" in schema_sql
    assert "CREATE TABLE sessions" in schema_sql
    assert "CREATE TABLE events" in schema_sql
    assert "payload JSONB NOT NULL" in schema_sql
    assert "REFERENCES cases(case_id) ON DELETE RESTRICT" in schema_sql
    assert "REFERENCES sessions(session_id) ON DELETE CASCADE" in schema_sql
    assert "CREATE TABLE asked_questions" not in schema_sql
    assert "CREATE TABLE dialogue_log" not in schema_sql
