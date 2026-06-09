from __future__ import annotations

import logging

from app.ai_engine.core.solution_guard import contains_secret
from app.ai_engine.core.llm import deterministic_clip, get_tone_llm
from app.ai_engine.prompts.tone_polish_builder import build_tone_polish_prompt
from app.ai_engine.schemas.agents import DraftCharacterReply
from app.ai_engine.schemas.dialogue import DialogueRequest

logger = logging.getLogger(__name__)




class DialogueTonePolisher:
    def run(self, payload: DialogueRequest, draft: DraftCharacterReply) -> DraftCharacterReply:
        if draft.degraded and draft.errorType:
            return draft
        if not draft.draftText.strip():
            return draft
        public_facts = _allowed_source_facts(payload)
        refs = payload.allowedStatement.sourceRefs
        has_public_context = bool(
            payload.interrogationTransition
            or payload.turnInterpretation
            or refs.statementIds
            or refs.timelineIds
            or refs.evidenceIds
            or refs.contradictionIds
            or public_facts
        )
        prompt = build_tone_polish_prompt(
            suspect={
                "name": payload.suspect.name,
                "role": payload.suspect.role or "용의자",
                "tensionLevel": payload.suspect.tensionLevel or "unknown",
                "pressureState": payload.suspect.pressureState or "unknown",
                "emotionalState": payload.suspect.emotionalState or "unknown",
                "tone": payload.style.tone,
            },
            candidate_answer=draft.draftText,
            public_context={
                "interrogationState": payload.interrogationTransition or payload.interrogationState or {},
                "playerQuestion": payload.question.text,
                "factAnchor": payload.allowedStatement.text,
                "visibleSourceFacts": public_facts[:4],
            },
        )
        try:
            polished = get_tone_llm().complete(
                prompt,
                seed_text=payload.allowedStatement.text,
                max_length=min(payload.style.maxLength, 220),
            )
        except Exception as exc:
            logger.warning(
                "dialogue tone polish failed",
                extra={"service": "ai_engine", "reason": type(exc).__name__},
            )
            return draft
        polished = _strip_outer_dialogue_quotes(polished)
        if not polished or contains_secret(polished)[0]:
            return draft
        if payload.allowedStatement.text and payload.allowedStatement.text not in polished and not has_public_context:
            # For neutral fallback text with no public refs, keep the anchor. Ref-backed turns should stay conversational.
            polished = deterministic_clip(f"{polished} {payload.allowedStatement.text}", max_length=payload.style.maxLength)
        polished = _normalize_modern_spoken_korean(_strip_outer_dialogue_quotes(polished))
        return draft.model_copy(
            update={
                "draftText": polished,
                "voiceMetadata": {**draft.voiceMetadata, "tonePolished": True},
            }
        )


def _strip_outer_dialogue_quotes(text: str) -> str:
    stripped = text.strip()
    quote_pairs = (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"))
    changed = True
    while changed and len(stripped) >= 2:
        changed = False
        for left, right in quote_pairs:
            if stripped.startswith(left) and stripped.endswith(right):
                stripped = stripped[len(left) : -len(right)].strip()
                changed = True
                break
    return stripped


def _allowed_source_facts(payload: DialogueRequest) -> list[str]:
    raw = getattr(payload.allowedStatement, "sourceFacts", None) or []
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item or "").strip()]


def _normalize_modern_spoken_korean(text: str) -> str:
    replacements = {
        "것이오": "겁니다",
        "하오": "해요",
        "하소": "하세요",
        "했소": "했습니다",
        "계셨지": "계셨습니다",
        "걷고 계셨지": "악화되고 있었습니다",
        "그대": "형사님",
    }
    normalized = text
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized.strip()
