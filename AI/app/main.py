from fastapi import FastAPI

from app.api.internal_routes import router


app = FastAPI(
    title="Detective Agent AI Service",
    version="0.1.0",
    description="Internal AI service for deterministic narrative generation.",
)

app.include_router(router)
