from __future__ import annotations

from typing import Any
from pydantic import Field, model_validator

from app.ai_engine.core.private_ref_guard import strip_forbidden_private_refs
from app.ai_engine.schemas.base import FlexibleModel


class TimeWindow(FlexibleModel):
    start: str | None = None
    end: str | None = None


class EvidenceRef(FlexibleModel):
    id: str
    name: str | None = None
    description: str | None = None
    type: str | None = None
    timeWindow: TimeWindow | None = None
    location: str | None = None
    confidence: float | None = None

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)
