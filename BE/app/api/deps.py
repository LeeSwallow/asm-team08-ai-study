from functools import lru_cache

from app.application.dialogue_service import DialogueService
from app.application.session_commands import SessionCommands
from app.core.config import get_settings
from app.core.errors import service_unavailable
from app.domain.rule_engine import RuleEngine
from app.infra.db import ensure_schema
from app.infra.local_ai_client import LocalAIClient
from app.infra.case_repository import CaseRepository
from app.infra.event_repository import EventRepository
from app.infra.session_repository import SessionRepository


@lru_cache
def get_case_repository() -> CaseRepository:
    _require_database()
    return CaseRepository()


@lru_cache
def get_session_repository() -> SessionRepository:
    _require_database()
    return SessionRepository()


@lru_cache
def get_event_repository() -> EventRepository:
    _require_database()
    return EventRepository()


def _require_database() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise service_unavailable("DATABASE_URL_REQUIRED", {"reason": "BE_DATABASE_URL is required for persistence"})
    ensure_schema()


@lru_cache
def get_rule_engine() -> RuleEngine:
    return RuleEngine()


@lru_cache
def get_ai_client() -> LocalAIClient:
    return LocalAIClient()


def get_session_commands() -> SessionCommands:
    return SessionCommands(
        case_repo=get_case_repository(),
        session_repo=get_session_repository(),
        rule_engine=get_rule_engine(),
        ai_client=get_ai_client(),
    )


def get_dialogue_service() -> DialogueService:
    return DialogueService(
        case_repo=get_case_repository(),
        session_repo=get_session_repository(),
        event_repo=get_event_repository(),
        rule_engine=get_rule_engine(),
        ai_client=get_ai_client(),
    )
