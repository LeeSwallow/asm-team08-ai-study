from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_cases import router as cases_router
from app.api.routes_sessions import router as sessions_router
from app.api import deps
from app.core.config import get_settings
from app.core.logging import RequestIdLoggingMiddleware

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


app.include_router(cases_router, prefix=settings.api_prefix)
app.include_router(sessions_router, prefix=settings.api_prefix)
