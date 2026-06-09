from __future__ import annotations

from pydantic import Field

from app.ai_engine.schemas.base import FlexibleModel
from app.ai_engine.schemas.evidence import EvidenceRef
from app.ai_engine.schemas.knowledge_pack import DialogueLog
from app.ai_engine.schemas.safety import Safety
from app.ai_engine.schemas.storyline import CharacterTimelineContext, StorylineContext
from app.ai_engine.schemas.visual import VisualState


class NotesSummaryRequest(FlexibleModel):
    requestId: str | None = None
    sessionId: str
    caseId: str
    dialogueLogs: list[DialogueLog] = Field(default_factory=list)
    discoveredEvidence: list[EvidenceRef] = Field(default_factory=list)
    storyline: StorylineContext | None = None
    characterTimelines: list[CharacterTimelineContext] = Field(default_factory=list)
    visualState: VisualState = Field(default_factory=VisualState)
    maxItems: int = Field(default=6, ge=1, le=20)
    revealAllowed: bool = False


class SummaryItem(FlexibleModel):
    sourceId: str
    text: str


class NotesSummaryResponse(FlexibleModel):
    summary: str
    items: list[SummaryItem] = Field(default_factory=list)
    evidenceIds: list[str] = Field(default_factory=list)
    safety: Safety = Field(default_factory=Safety)
