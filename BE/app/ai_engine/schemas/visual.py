from __future__ import annotations

from pydantic import Field

from app.ai_engine.schemas.base import FlexibleModel


class VisualState(FlexibleModel):
    suspectId: str | None = None
    backgroundId: str | None = None
    characterImageState: str | None = None
    emotionalState: str | None = None
    expression: str | None = None
    tensionLevel: str | None = None
    pressure: int | float | None = None
