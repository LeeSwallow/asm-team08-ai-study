from __future__ import annotations

from typing import Literal
from pydantic import Field

from app.schemas.common import CharacterTimelineContext, EvidenceRef, FlexibleModel, Safety, StorylineContext, VisualState


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
