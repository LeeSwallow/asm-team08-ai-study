from functools import lru_cache

from app.application.dialogue_service import DialogueService
from app.application.session_commands import SessionCommands
from app.core.config import get_settings
from app.domain.rule_engine import RuleEngine
from app.infra.local_ai_client import LocalAIClient
from app.infra.case_repository import CaseRepository
from app.infra.event_repository import EventRepository
from app.infra.session_repository import SessionRepository


@lru_cache
def get_case_repository() -> CaseRepository:
    settings = get_settings()
    return CaseRepository(settings.data_dir / "cases", use_database=bool(settings.database_url))


@lru_cache
def get_session_repository() -> SessionRepository:
    settings = get_settings()
    return SessionRepository(settings.data_dir / "sessions")


@lru_cache
def get_event_repository() -> EventRepository:
    settings = get_settings()
    return EventRepository(settings.data_dir / "events")


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
