from __future__ import annotations

from pydantic import Field

from app.ai_engine.schemas.base import FlexibleModel
from app.ai_engine.schemas.safety import Safety
from app.ai_engine.schemas.storyline import CharacterTimelineContext, StorylineContext
from app.ai_engine.schemas.verdicts import BackendVerdict
from app.ai_engine.schemas.visual import VisualState


class EndingExplainRequest(FlexibleModel):
    requestId: str | None = None
    sessionId: str
    caseId: str
    verdict: BackendVerdict
    culpritName: str | None = None
    usedQuestionCount: int | None = None
    foundCoreContradictionCount: int | None = None
    storyline: StorylineContext | None = None
    characterTimelines: list[CharacterTimelineContext] = Field(default_factory=list)
    visualState: VisualState = Field(default_factory=VisualState)
    revealAllowed: bool = True


class EndingExplainResponse(FlexibleModel):
    result: str
    explanation: str
    safety: Safety = Field(default_factory=Safety)
