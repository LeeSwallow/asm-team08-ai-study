import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_cases import router as cases_router
from app.api.routes_agent_logs import router as agent_logs_router
from app.api.routes_sessions import router as sessions_router
from app.api import deps
from app.core.config import get_settings
from app.core.logging import RequestIdLoggingMiddleware
from app.infra.case_orm import CaseRecord
from app.infra.db import ensure_schema, get_session_factory

logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(RequestIdLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(f"{settings.api_prefix}/health", tags=["health"])
def health():
    return {"status": "ok", "service": settings.app_name}


@app.get(f"{settings.api_prefix}/ready", tags=["health"])
async def ready():
    ai_health = await deps.get_ai_client().health()
    status = "ok" if ai_health.get("ok") else "degraded"
    return {"status": status, "service": settings.app_name, "ai": ai_health}


@app.on_event("startup")
def seed_case_files() -> None:
    if not settings.database_url:
        return
    try:
        ensure_schema()
        session_factory = get_session_factory()
        if session_factory is None:
            return
        with session_factory() as db:
            for path in sorted(Path("data/cases").glob("*.json")):
                payload = json.loads(path.read_text(encoding="utf-8"))
                db.merge(CaseRecord(case_id=str(payload["caseId"]), payload=payload))
            db.commit()
    except Exception as exc:
        logger.warning("case file seed failed", extra={"service": "backend", "reason": type(exc).__name__})


app.include_router(cases_router, prefix=settings.api_prefix)
app.include_router(sessions_router, prefix=settings.api_prefix)
app.include_router(agent_logs_router, prefix=settings.api_prefix)
