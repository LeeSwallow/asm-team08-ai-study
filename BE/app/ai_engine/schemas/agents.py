from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from app.ai_engine.schemas.common import AllowedEventPolicy, CharacterKnowledgePack, FlexibleModel, PersonaOverlay, PersonaVariant, ProposedEvent
from app.ai_engine.schemas.dialogue import AllowedStatement, DialogueRequest, SourceRefs

if TYPE_CHECKING:
    from app.ai_engine.application.knowledge_retriever import CharacterRetrievedContext, GameMasterEventContext


class CharacterAgentInput(FlexibleModel):
    payload: DialogueRequest
    requestId: str | None = None
    correlationId: str | None = None
    message: str
    dialogueMode: str | None = None
    intent: str | None = None
    allowedStatement: AllowedStatement
    allowedEventPolicy: AllowedEventPolicy = Field(default_factory=AllowedEventPolicy)
    characterKnowledgePack: CharacterKnowledgePack | None = None
    activePersonaOverlay: PersonaOverlay | None = None
    personaVariants: list[PersonaVariant] = Field(default_factory=list)
    style: dict[str, Any] = Field(default_factory=dict)
    revealAllowed: bool = False
    tensionLevel: str | None = None
    pressureState: str | None = None
    emotionalState: str | None = None
    tensionScore: int | float | None = None
    interrogationState: dict[str, Any] = Field(default_factory=dict)
    interrogationTransition: dict[str, Any] = Field(default_factory=dict)
    recentDialogue: list[Any] = Field(default_factory=list)


class DraftCharacterReply(FlexibleModel):
    requestId: str | None = None
    correlationId: str | None = None
    suspectId: str | None = None
    draftText: str
    usedRefs: SourceRefs = Field(default_factory=SourceRefs)
    sourceRefs: SourceRefs = Field(default_factory=SourceRefs)
    voiceMetadata: dict[str, Any] = Field(default_factory=dict)
    personaOverlayId: str | None = None
    voice: dict[str, Any] = Field(default_factory=dict)
    tone: dict[str, Any] = Field(default_factory=dict)
    persona: dict[str, Any] = Field(default_factory=dict)
    fallbackUsed: bool = False
    degraded: bool = False
    provider: str
    model: str
    blockedReason: str | None = None
    errorType: str | None = None
    timeoutMs: int | None = None
    providerConfigured: bool | None = None


class LightRuleCheckInput(FlexibleModel):
    requestId: str | None = None
    correlationId: str | None = None
    draft: DraftCharacterReply
    characterKnowledgePack: CharacterKnowledgePack | None = None
    allowedStatement: AllowedStatement
    allowedEventPolicy: AllowedEventPolicy = Field(default_factory=AllowedEventPolicy)
    forbiddenRefs: list[str] = Field(default_factory=list)
    revealAllowed: bool = False
    enforceStatementScope: bool = True
    allowedContextTerms: list[str] = Field(default_factory=list)
    intent: str | None = None
    suspectName: str | None = None
    # CharacterKnowledgeRetriever 결과 (재생성 품질 개선에 사용, 없으면 기본 동작)
    retrieved_context: Any | None = Field(default=None, exclude=True)


class CheckedCharacterReply(FlexibleModel):
    requestId: str | None = None
    correlationId: str | None = None
    suspectId: str | None = None
    finalText: str
    repairedText: str | None = None
    blockedText: str | None = None
    repaired: bool = False
    blocked: bool = False
    blockedReason: str | None = None
    usedRefs: SourceRefs = Field(default_factory=SourceRefs)
    sourceRefs: SourceRefs = Field(default_factory=SourceRefs)
    personaOverlayId: str | None = None
    safetyFindings: dict[str, Any] = Field(default_factory=dict)
    fallbackUsed: bool = False
    degraded: bool = False
    provider: str | None = None
    model: str | None = None
    errorType: str | None = None


class GameMasterAgentInput(FlexibleModel):
    requestId: str | None = None
    correlationId: str | None = None
    payload: DialogueRequest
    checkedReply: CheckedCharacterReply
    characterKnowledgePack: CharacterKnowledgePack | None = None
    allowedEventPolicy: AllowedEventPolicy = Field(default_factory=AllowedEventPolicy)
    visibleRefs: SourceRefs = Field(default_factory=SourceRefs)
    providerDegraded: bool = False
    # GameMasterKnowledgeRetriever 결과. 캐릭터 말투/개별 발화 근거와 분리된 이벤트 제안용 공개 refs.
    event_context: Any | None = Field(default=None, exclude=True)


class GameMasterProposal(FlexibleModel):
    proposedEvents: list[ProposedEvent] = Field(default_factory=list)
    sourceRefs: SourceRefs = Field(default_factory=SourceRefs)
    filteredEventTypes: list[str] = Field(default_factory=list)
    rejectedByAgent: list[dict[str, Any]] = Field(default_factory=list)
    invariants: dict[str, bool] = Field(default_factory=dict)
