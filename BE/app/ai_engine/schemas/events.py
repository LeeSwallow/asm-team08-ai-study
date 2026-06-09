from __future__ import annotations

from typing import Any
from pydantic import Field

from app.ai_engine.schemas.base import FlexibleModel


class ProposedEvent(FlexibleModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    sourceRefs: dict[str, list[str]] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0, le=1)


class AllowedEventPolicy(FlexibleModel):
    allowedTypes: list[str] = Field(default_factory=list)
    relatedEvidenceIds: list[str] = Field(default_factory=list)
    relatedTimelineEventIds: list[str] = Field(default_factory=list)
    relatedStatementIds: list[str] = Field(default_factory=list)
    relatedQuestionIds: list[str] = Field(default_factory=list)
    relatedContradictionIds: list[str] = Field(default_factory=list)
