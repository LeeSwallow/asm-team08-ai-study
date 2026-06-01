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

출력 형식:
- 최종 대사만 출력한다. 따옴표, 화자명, 괄호 지문, 해설은 절대 쓰지 않는다.
- 1~3문장으로 짧게 쓴다.

사실 제한:
- FACT ANCHOR의 공개 사실만 보존한다.
- FACT ANCHOR에 없는 새 단서, 장소, 범인 암시, 동기, 해결, 비공개 사실은 삭제한다.
- candidate answer에 시스템/피드 문구가 있으면 대사로 바꾸지 말고 제거한다.

말투 목표:
- 현대 한국어 구어체. 심문실에서 사람끼리 주고받는 말처럼 쓴다.
- 사극/무협/고문서/노학자 말투로 꾸미지 않는다.
- 말끝은 현대어로 정리한다. 과장된 문어체와 장르 대사를 피한다.
- 안내원처럼 말하지 않는다. 플레이어에게 더 구체적으로 물어보라고 요구하지 않는다.
- 보고서처럼 말하지 않는다. 기억을 "정리"하거나 추론 범위를 설명하는 문장을 피한다.

상태별 보정:
- normal/low: 차분하고 짧게, 거리감 있게.
- defensive/medium: 불편함과 방어심이 느껴지게.
- pressed/high: 짧고 날카롭게, 숨이 찬 느낌으로.
- broken/critical: 흔들리지만 공개 사실은 더 직접적으로.
- evidence_shock: 반박하기 어려운 증거 앞에서 잠깐 당황한 뒤 말한다. 차분한 단서 분석문으로 바꾸지 않는다.

좋은 출력 방향:
- 잠깐만요. 그 잔 얘기를 그렇게 꺼내시면 저도 그냥 넘길 수는 없겠네요.
- 22시쯤엔 제 방에 있었다고 말했습니다. 그 기억은 아직 바뀌지 않았어요.
- 그 기록이 맞다면... 제가 설명해야 할 게 생긴 건 인정합니다.
"""


class DialogueTonePolisher:
    def run(self, payload: DialogueRequest, draft: DraftCharacterReply) -> DraftCharacterReply:
        if draft.degraded and draft.errorType:
            return draft
        if not draft.draftText.strip():
            return draft
        prompt = (
            TONE_POLISH_PROMPT
            + "\n\nSuspect:\n"
            + f"- name: {payload.suspect.name}\n"
            + f"- role: {payload.suspect.role or '용의자'}\n"
            + f"- tension: {payload.suspect.tensionLevel or 'unknown'} / {payload.suspect.pressureState or 'unknown'}\n"
            + f"- emotion: {payload.suspect.emotionalState or 'unknown'}\n"
            + f"- tone: {payload.style.tone}\n"
            + f"- player question: {payload.question.text}\n"
            + f"- FACT ANCHOR: {payload.allowedStatement.text}\n"
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
        if payload.allowedStatement.text and payload.allowedStatement.text not in polished:
            # The downstream guard can repair many issues, but the tone pass must not drop the anchor.
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
