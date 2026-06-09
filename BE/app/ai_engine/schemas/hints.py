from __future__ import annotations

from typing import Literal
from pydantic import Field

from app.ai_engine.schemas.base import FlexibleModel
from app.ai_engine.schemas.evidence import EvidenceRef
from app.ai_engine.schemas.safety import Safety
from app.ai_engine.schemas.storyline import CharacterTimelineContext, StorylineContext
from app.ai_engine.schemas.visual import VisualState


class HintRequest(FlexibleModel):
    requestId: str | None = None
    sessionId: str
    caseId: str
    discoveredEvidence: list[EvidenceRef] = Field(default_factory=list)
    discoveredStatementIds: list[str] = Field(default_factory=list)
    allowedClues: list[str] = Field(default_factory=list)
    storyline: StorylineContext | None = None
    characterTimelines: list[CharacterTimelineContext] = Field(default_factory=list)
    visualState: VisualState = Field(default_factory=VisualState)
    hintLevel: Literal["gentle", "direct", "strong"] = "gentle"
    revealAllowed: bool = False


class HintResponse(FlexibleModel):
    text: str
    level: str
    referencedEvidenceIds: list[str] = Field(default_factory=list)
    safety: Safety = Field(default_factory=Safety)
