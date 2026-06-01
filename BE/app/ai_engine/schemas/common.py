from __future__ import annotations

from typing import Any, Literal
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.ai_engine.core.guard import strip_forbidden_private_refs


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Safety(FlexibleModel):
    leaksSolution: bool = False
    violatesCaseFacts: bool = False
    blockedTerms: list[str] = Field(default_factory=list)
    fallbackUsed: bool = False
    degraded: bool = False
    provider: str | None = None
    model: str | None = None
    repaired: bool = False
    blockedReason: str | None = None
    errorType: str | None = None
    graphRunner: str | None = None
    graphFallbackReason: str | None = None


class VisualState(FlexibleModel):
    suspectId: str | None = None
    backgroundId: str | None = None
    characterImageState: str | None = None
    emotionalState: str | None = None
    expression: str | None = None
    tensionLevel: str | None = None
    pressure: int | float | None = None


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


class DialogueLog(FlexibleModel):
    id: str | None = None
    speaker: str
    text: str
    questionId: str | None = None
    statementId: str | None = None
    evidenceIds: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)


class KnowledgeSnippet(FlexibleModel):
    id: str | None = None
    text: str
    sourceType: str | None = None
    sourceId: str | None = None
    relatedStatementIds: list[str] = Field(default_factory=list)
    relatedEvidenceIds: list[str] = Field(default_factory=list)
    relatedTimelineIds: list[str] = Field(default_factory=list)
    relatedContradictionIds: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)


class PersonaOverlay(FlexibleModel):
    id: str | None = Field(default=None, validation_alias=AliasChoices("id", "variantId"))
    label: str | None = None
    voice: str | None = None
    tone: str | None = None
    persona: str | None = None
    styleDirectives: list[str] = Field(default_factory=list)
    speechStyle: dict[str, Any] = Field(default_factory=dict)
    tensionLevel: str | None = None
    pressureState: str | None = None
    emotionalState: str | None = None
    tensionScore: int | float | None = None
    selectedFrom: str | None = None
    selectionReason: str | None = None
    evasiveness: float | None = Field(default=None, ge=0, le=1)
    hesitation: str | int | float | None = None
    allowedTone: list[str] = Field(default_factory=list)
    forbiddenTone: list[str] = Field(default_factory=list)
    recentDialoguePressure: float | None = Field(default=None, ge=0, le=1)
    contradictionPressure: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)


class PersonaVariant(FlexibleModel):
    id: str = Field(validation_alias=AliasChoices("id", "variantId"))
    label: str | None = None
    tensionLevels: list[str] = Field(default_factory=list, validation_alias=AliasChoices("tensionLevels", "tensionLevel"))
    pressureStates: list[str] = Field(default_factory=list, validation_alias=AliasChoices("pressureStates", "pressureState"))
    emotionalStates: list[str] = Field(default_factory=list, validation_alias=AliasChoices("emotionalStates", "emotionalState"))
    minTensionScore: int | float | None = None
    maxTensionScore: int | float | None = None
    overlay: PersonaOverlay = Field(default_factory=PersonaOverlay)

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        value = strip_forbidden_private_refs(value)
        if isinstance(value, dict) and "overlay" not in value:
            overlay_keys = {
                "variantId",
                "tone",
                "evasiveness",
                "hesitation",
                "allowedTone",
                "forbiddenTone",
                "sample",
                "speechStyle",
                "styleDirectives",
                "voice",
                "selectionReason",
            }
            overlay = {key: item for key, item in value.items() if key in overlay_keys}
            value = {**value, "overlay": overlay}
        return value

    @field_validator("tensionLevels", "pressureStates", "emotionalStates", mode="before")
    @classmethod
    def _single_selector_to_list(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return value


class CharacterKnowledgePack(FlexibleModel):
    packId: str | None = None
    caseId: str | None = None
    sessionId: str | None = None
    suspectId: str | None = None
    visibility: str = "public"
    persona: str | None = None
    publicPersona: str | None = None
    publicMask: str | None = None
    speechStyle: dict[str, Any] = Field(default_factory=dict)
    activePersonaOverlay: PersonaOverlay | None = None
    personaVariants: list[PersonaVariant] = Field(default_factory=list)
    visibleTimeline: list[KnowledgeSnippet] = Field(default_factory=list)
    alibiSnippets: list[KnowledgeSnippet] = Field(default_factory=list)
    evidenceSnippets: list[KnowledgeSnippet] = Field(default_factory=list)
    relationshipSnippets: list[KnowledgeSnippet] = Field(default_factory=list)
    recentDialogue: list[DialogueLog] = Field(default_factory=list)
    forbiddenRefs: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _strip_private_refs(cls, value: Any) -> Any:
        return strip_forbidden_private_refs(value)

    @field_validator("personaVariants", mode="before")
    @classmethod
    def _persona_variants_from_contract_map(cls, value: Any) -> Any:
        if isinstance(value, dict):
            variants = []
            for key, item in value.items():
                if isinstance(item, dict):
                    item_id = item.get("id") or item.get("variantId") or key
                    variants.append({"id": item_id, **item})
                else:
                    variants.append({"id": str(key), "overlay": {"voice": str(item)}})
            return variants
        return value


class BackendVerdict(FlexibleModel):
    result: Literal["correct", "partial", "insufficient", "wrong"] | str
    label: str | None = None
    reason: str | None = None
    score: float | None = None
    evidenceIds: list[str] = Field(default_factory=list)
    statementIds: list[str] = Field(default_factory=list)
    missedEvidenceIds: list[str] = Field(default_factory=list)
    revealAllowed: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
