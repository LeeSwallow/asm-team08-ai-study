from __future__ import annotations

from typing import Literal
from pydantic import Field

from app.ai_engine.schemas.base import FlexibleModel


class BackendVerdict(FlexibleModel):
    result: Literal["correct", "partial", "insufficient", "wrong"] | str
    label: str | None = None
    reason: str | None = None
    score: float | None = None
    evidenceIds: list[str] = Field(default_factory=list)
    statementIds: list[str] = Field(default_factory=list)
    missedEvidenceIds: list[str] = Field(default_factory=list)
    revealAllowed: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)
