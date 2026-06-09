from __future__ import annotations

from app.ai_engine.schemas.persona import PersonaOverlay, PersonaVariant
from app.ai_engine.schemas.dialogue import DialogueRequest
from app.ai_engine.agents.character_utils import _normalized_tension_score, _safe_short_text


def knowledge_persona(payload: DialogueRequest) -> str:
    pack = payload.characterKnowledgePack
    if not pack:
        return payload.suspect.publicPersona or ""
    return _safe_short_text(pack.publicPersona or pack.persona or payload.suspect.publicPersona, max_length=160)


def knowledge_speech_style(payload: DialogueRequest) -> dict[str, object]:
    pack = payload.characterKnowledgePack
    overlay = select_persona_overlay(payload)
    if overlay and overlay.speechStyle:
        return overlay.speechStyle
    if pack and pack.speechStyle:
        return pack.speechStyle
    return payload.suspect.speechStyle


def _variant_matches(
    variant: PersonaVariant,
    *,
    tension_level: str | None,
    pressure_state: str | None,
    emotional_state: str | None,
    tension_score: float | None,
) -> bool:
    if variant.tensionLevels and tension_level not in variant.tensionLevels:
        return False
    if variant.pressureStates and pressure_state not in variant.pressureStates:
        return False
    if variant.emotionalStates and emotional_state not in variant.emotionalStates:
        return False
    if tension_score is not None:
        if variant.minTensionScore is not None and tension_score < _normalized_tension_score(variant.minTensionScore):
            return False
        if variant.maxTensionScore is not None and tension_score > _normalized_tension_score(variant.maxTensionScore):
            return False
    return True


def select_persona_overlay(payload: DialogueRequest) -> PersonaOverlay | None:
    pack = payload.characterKnowledgePack
    if not pack:
        return None
    tension_score = _normalized_tension_score(
        payload.suspect.tensionScore if payload.suspect.tensionScore is not None else payload.suspect.pressure
    )
    if pack.activePersonaOverlay:
        overlay = pack.activePersonaOverlay.model_copy()
        overlay.selectedFrom = overlay.selectedFrom or "activePersonaOverlay"
        overlay.tensionLevel = overlay.tensionLevel or payload.suspect.tensionLevel
        overlay.pressureState = overlay.pressureState or payload.suspect.pressureState
        overlay.emotionalState = overlay.emotionalState or payload.suspect.emotionalState
        overlay.tensionScore = overlay.tensionScore if overlay.tensionScore is not None else tension_score
        return overlay
    for variant in pack.personaVariants:
        if _variant_matches(
            variant,
            tension_level=payload.suspect.tensionLevel,
            pressure_state=payload.suspect.pressureState,
            emotional_state=payload.suspect.emotionalState,
            tension_score=tension_score,
        ):
            overlay = variant.overlay.model_copy()
            overlay.id = overlay.id or variant.id
            overlay.label = overlay.label or variant.label
            overlay.selectedFrom = variant.id
            overlay.tensionLevel = overlay.tensionLevel or payload.suspect.tensionLevel
            overlay.pressureState = overlay.pressureState or payload.suspect.pressureState
            overlay.emotionalState = overlay.emotionalState or payload.suspect.emotionalState
            overlay.tensionScore = overlay.tensionScore if overlay.tensionScore is not None else tension_score
            return overlay
    return None
