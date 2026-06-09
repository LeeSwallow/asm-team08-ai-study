from __future__ import annotations

from pydantic import Field

from app.ai_engine.schemas.base import FlexibleModel


class Safety(FlexibleModel):
    leaksSolution: bool = False
    violatesCaseFacts: bool = False
    blockedTerms: list[str] = Field(default_factory=list)
    fallbackUsed: bool = False
    degraded: bool = False
    provider: str | None = None
    model: str | None = None
    repaired: bool = False
    blockedReason: str | None = None
    errorType: str | None = None
    graphRunner: str | None = None
    graphFallbackReason: str | None = None
