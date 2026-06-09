from __future__ import annotations

from typing import Any, Literal
from pydantic import Field, field_validator, model_validator

from app.ai_engine.core.private_ref_guard import strip_forbidden_private_refs
from app.ai_engine.schemas.base import FlexibleModel


class StoryTimelineEvent(FlexibleModel):
    time: str | None = None
    title: str
    description: str | None = None
    sourceType: str | None = None
    sourceId: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)


class CharacterTimelineItem(FlexibleModel):
    time: str | None = None
    claimedLocation: str | None = None
    claimedAction: str | None = None
    witnessedBy: list[str] = Field(default_factory=list)
    relatedEvidenceIds: list[str] = Field(default_factory=list)
    relatedStatementIds: list[str] = Field(default_factory=list)
    emotionalState: Literal["neutral", "tense", "surprised", "angry", "broken"] | str | None = None
    public: bool = True

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)


class CharacterTimelineContext(FlexibleModel):
    suspectId: str
    publicPersona: str | None = None
    events: list[CharacterTimelineItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)

    @field_validator("events", mode="before")
    @classmethod
    def _strip_hidden_events(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)


class StorylineContext(FlexibleModel):
    currentObjective: str | None = None
    currentActId: str | None = None
    visibleTimeline: list[StoryTimelineEvent] = Field(default_factory=list)
    characterTimelines: list[CharacterTimelineContext] = Field(default_factory=list)
    publicPremise: str | None = None
    openingObjective: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)

    @field_validator("visibleTimeline", "characterTimelines", mode="before")
    @classmethod
    def _strip_hidden_lists(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)
