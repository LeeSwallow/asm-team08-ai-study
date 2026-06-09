from __future__ import annotations

from typing import Any, Literal
from pydantic import AliasChoices, Field, field_validator, model_validator

from app.ai_engine.core.private_ref_guard import strip_forbidden_private_refs
from app.ai_engine.schemas.base import FlexibleModel


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
