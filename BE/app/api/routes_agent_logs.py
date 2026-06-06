from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from app.ai_engine.core.trace_store import agent_trace_store
from app.core.config import Settings, get_settings
from app.core.errors import forbidden
from app.core.leak_guard import assert_no_forbidden_refs


router = APIRouter(prefix="/agent-logs", tags=["agent-logger"])


def _require_agent_logger(settings: Settings) -> None:
    if not settings.debug_tools_enabled:
        raise forbidden(
            "AGENT_LOGGER_DISABLED",
            {"message": "Agent logger requires BE_DEBUG_TOOLS_ENABLED=true."},
        )


@router.get("")
def list_agent_logs(
    session_id: str | None = Query(default=None, alias="sessionId"),
    case_id: str | None = Query(default=None, alias="caseId"),
    graph: str | None = Query(default=None),
    limit: int = Query(default=40, ge=1, le=100),
    settings: Settings = Depends(get_settings),
):
    _require_agent_logger(settings)
    payload = {
        "enabled": True,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "capacity": agent_trace_store.capacity,
        "traces": agent_trace_store.list_traces(
            session_id=session_id,
            case_id=case_id,
            graph=graph,
            limit=limit,
        ),
    }
    assert_no_forbidden_refs(payload, surface="agent_logger")
    return payload


@router.delete("")
def clear_agent_logs(settings: Settings = Depends(get_settings)):
    _require_agent_logger(settings)
    return {"cleared": agent_trace_store.clear()}
