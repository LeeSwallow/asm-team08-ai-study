from __future__ import annotations

from typing import Any
from pydantic import Field, field_validator, model_validator

from app.ai_engine.core.private_ref_guard import strip_forbidden_private_refs
from app.ai_engine.schemas.base import FlexibleModel
from app.ai_engine.schemas.persona import PersonaOverlay, PersonaVariant


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
