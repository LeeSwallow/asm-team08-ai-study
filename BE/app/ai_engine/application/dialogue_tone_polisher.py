from __future__ import annotations

import logging

from app.ai_engine.core.guard import contains_secret
from app.ai_engine.core.llm import deterministic_clip, get_tone_llm
from app.ai_engine.schemas.agents import DraftCharacterReply
from app.ai_engine.schemas.dialogue import DialogueRequest

logger = logging.getLogger(__name__)


TONE_POLISH_PROMPT = """
너는 현대 한국 추리 게임의 대사 편집자다.
candidate answer를 용의자가 심문실에서 직접 말하는 자연스러운 한국어 대사로 다시 쓴다.

사실 제한:
- FACT ANCHOR의 공개 사실만 보존한다.
- FACT ANCHOR에 없는 새 단서, 장소, 범인 암시, 동기, 해결, 비공개 사실은 삭제한다.
- candidate answer에 시스템/피드 문구가 있으면 대사로 바꾸지 말고 제거한다.

대화감:
- 현대 한국어 구어체. 심문실에서 사람끼리 주고받는 말처럼 쓴다.
- 따옴표, 화자명, 괄호 지문, 해설은 쓰지 않는다.
- 사극/무협/고문서/노학자 말투와 보고서식 정리를 피한다.
- 플레이어에게 더 구체적으로 물어보라고 요구하지 않는다.
- Interrogation state가 강한 압박이면 문장이 짧아지고 감정이 드러나야 한다.
- 용의자 본인이 말한다. 자기 이름을 제3자처럼 부르거나 "누나/형/씨" 같은 호칭으로 부르지 않는다.
- 증거 주인, 범인, 관계자는 공개 사실에 명시된 경우에만 말한다. 없으면 모른다고 버틴다.
"""


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
        prompt = (
            TONE_POLISH_PROMPT
            + "\n\nSuspect:\n"
            + f"- name: {payload.suspect.name}\n"
            + f"- role: {payload.suspect.role or '용의자'}\n"
            + f"- tension: {payload.suspect.tensionLevel or 'unknown'} / {payload.suspect.pressureState or 'unknown'}\n"
            + f"- emotion: {payload.suspect.emotionalState or 'unknown'}\n"
            + f"- tone: {payload.style.tone}\n"
            + f"- interrogation state: {payload.interrogationTransition or payload.interrogationState or {}}\n"
            + f"- player question: {payload.question.text}\n"
            + f"- FACT ANCHOR: {payload.allowedStatement.text}\n"
            + f"- VISIBLE SOURCE FACTS: {' / '.join(public_facts[:4]) if public_facts else '(none)'}\n"
            + f"- candidate answer: {draft.draftText}\n"
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
