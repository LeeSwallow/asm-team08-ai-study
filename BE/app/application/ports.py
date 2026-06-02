from __future__ import annotations

from typing import Any, Iterable, Protocol

from app.domain.models import Case, EventEntry, SessionState


class CaseRepositoryPort(Protocol):
    def list_cases(self) -> list[Case]:
        ...

    def get_case(self, case_id: str) -> Case | None:
        ...


class SessionRepositoryPort(Protocol):
    def get(self, session_id: str) -> SessionState | None:
        ...

    def save(self, session: SessionState) -> SessionState:
        ...

    def list_ids(self) -> list[str]:
        ...


class EventRepositoryPort(Protocol):
    def append_many(self, events: Iterable[EventEntry]) -> list[EventEntry]:
        ...

    def list_for_session(self, session_id: str, after_event_id: str | None = None) -> list[EventEntry]:
        ...

    def last_id(self, session_id: str) -> str | None:
        ...

    def next_index(self, session_id: str) -> int:
        ...

    def next_id(self, session_id: str) -> str:
        ...


class AIClientPort(Protocol):
    async def dialogue_response_info(self, payload: dict[str, Any], fallback: str) -> dict[str, Any]:
        ...

    async def dialogue_response(self, payload: dict[str, Any], fallback: str) -> str:
        ...

    async def notes_summary(self, payload: dict[str, Any], fallback: str) -> str:
        ...

    async def hint(self, payload: dict[str, Any], fallback: str) -> str:
        ...

    async def ending(self, payload: dict[str, Any], fallback: str) -> str:
        ...

    async def health(self) -> dict[str, Any]:
        ...


class CaseGraphPort(Protocol):
    @property
    def available(self) -> bool:
        ...

    def run(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        ...

    def run_write(self, cypher: str, **params: Any) -> list[dict[str, Any]]:
        ...


class KnowledgeGraphRepositoryPort(Protocol):
    @property
    def available(self) -> bool:
        ...

    def find_alibi_conflicts(
        self,
        *,
        case_id: str,
        suspect_id: str,
        time_expressions: list[str],
        unlocked_statement_ids: list[str],
        discovered_contradiction_ids: list[str],
    ) -> list[dict[str, Any]]:
        ...

    def find_evidence_context(
        self,
        *,
        case_id: str,
        evidence_terms: list[str],
        unlocked_evidence_ids: list[str],
    ) -> list[dict[str, Any]]:
        ...

    def find_timeline_events(self, *, case_id: str, time_expressions: list[str]) -> list[dict[str, Any]]:
        ...
