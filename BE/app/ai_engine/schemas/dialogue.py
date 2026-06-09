from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field, model_validator

from app.ai_engine.core.private_ref_guard import strip_forbidden_private_refs
from app.ai_engine.schemas.base import FlexibleModel
from app.ai_engine.schemas.events import AllowedEventPolicy, ProposedEvent
from app.ai_engine.schemas.knowledge_pack import CharacterKnowledgePack
from app.ai_engine.schemas.safety import Safety
from app.ai_engine.schemas.storyline import CharacterTimelineContext, StorylineContext
from app.ai_engine.schemas.visual import VisualState


class SourceRefs(FlexibleModel):
    statementIds: list[str] = Field(default_factory=list)
    timelineIds: list[str] = Field(default_factory=list)
    evidenceIds: list[str] = Field(default_factory=list)
    questionIds: list[str] = Field(default_factory=list)
    contradictionIds: list[str] = Field(default_factory=list)


class Suspect(FlexibleModel):
    id: str
    name: str
    role: str | None = None
    pressureState: str = "normal"
    publicPersona: str | None = Field(
        default=None,
        validation_alias=AliasChoices("publicPersona", "publicProfile"),
    )
    speechStyle: dict[str, Any] = Field(default_factory=dict)
    publicTimeline: list[dict[str, Any]] = Field(default_factory=list)
    tensionLevel: str | None = None
    pressure: int | float | None = Field(default=None, ge=0)
    tensionScore: int | float | None = Field(default=None, ge=0)
    emotionalState: str | None = None
    expression: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)


class Question(FlexibleModel):
    id: str
    text: str

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)


class AllowedStatement(FlexibleModel):
    id: str
    text: str
    sourceRefs: SourceRefs = Field(default_factory=SourceRefs)

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)


class DialogueStyle(FlexibleModel):
    tone: str = "neutral"
    maxLength: int = Field(default=180, ge=40, le=1000)


class DialogueRequest(FlexibleModel):
    requestId: str | None = None
    correlationId: str | None = None
    sessionId: str
    caseId: str
    suspect: Suspect
    question: Question = Field(validation_alias=AliasChoices("question", "playerMessage"))
    playerMessage: str | None = Field(default=None, validation_alias=AliasChoices("playerMessage", "message"))
    allowedStatement: AllowedStatement
    style: DialogueStyle = Field(default_factory=DialogueStyle)
    visualState: VisualState = Field(default_factory=VisualState)
    allowedEventPolicy: AllowedEventPolicy = Field(default_factory=AllowedEventPolicy)
    characterKnowledgePack: CharacterKnowledgePack | None = Field(
        default=None,
        validation_alias=AliasChoices("characterKnowledgePack", "knowledgePack"),
    )
    dialogueMode: str | None = None
    storyline: StorylineContext | None = None
    characterTimeline: CharacterTimelineContext | None = None
    turnInterpretation: dict[str, Any] = Field(default_factory=dict)
    interrogationState: dict[str, Any] = Field(default_factory=dict)
    interrogationTransition: dict[str, Any] = Field(default_factory=dict)
    revealAllowed: bool = False

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)


class DialogueResponse(FlexibleModel):
    requestId: str | None = None
    correlationId: str | None = None
    statementId: str
    text: str
    dialogueMode: str | None = None
    intent: str | None = None
    provider: str | None = None
    model: str | None = None
    fallbackUsed: bool = False
    degraded: bool = False
    visualState: VisualState = Field(default_factory=VisualState)
    proposedEvents: list[ProposedEvent] = Field(default_factory=list)
    matchedRefs: SourceRefs = Field(default_factory=SourceRefs)
    proposedEventsCount: int = 0
    runtimeDiagnostics: dict[str, Any] = Field(default_factory=dict)
    safety: Safety = Field(default_factory=Safety)
