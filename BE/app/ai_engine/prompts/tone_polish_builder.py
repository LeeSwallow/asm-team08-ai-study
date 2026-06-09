from __future__ import annotations

from app.ai_engine.prompts.dialogue import TONE_POLISH_PROMPT
from app.ai_engine.schemas.prompts import LLMChatPrompt, PromptSection


def build_tone_polish_prompt(
    *,
    suspect: dict[str, object],
    candidate_answer: str,
    public_context: dict[str, object],
) -> LLMChatPrompt:
    return LLMChatPrompt(
        systemPrompt=TONE_POLISH_PROMPT,
        sections=[
            PromptSection(title="Suspect", kind="context", content=suspect),
            PromptSection(title="Candidate Answer", kind="input", content=candidate_answer),
            PromptSection(title="Public Context", kind="context", content=public_context),
        ],
        outputInstruction="candidate answer를 공개 사실 범위 안에서 자연스러운 용의자 대사 한 줄로 다시 써라.",
    )
