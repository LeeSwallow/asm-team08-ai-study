from __future__ import annotations

from app.ai_engine.schemas.agents import LightRuleCheckInput
from app.ai_engine.schemas.prompts import LLMChatPrompt, PromptSection


_ISSUE_MESSAGES = {
    "too_short": "답변이 너무 짧고 불완전합니다.",
    "seed_verbatim": "LLM이 기본 텍스트를 그대로 반환했습니다. 캐릭터의 목소리로 자연스럽게 다시 표현해야 합니다.",
    "no_style_tic": "캐릭터의 말투 습관이 응답에 없습니다. 자연스럽게 포함하세요.",
    "atmosphere_break": "응답이 탐정 누아르 분위기를 벗어났습니다. 용의자 심문 맥락으로 유지하세요.",
    "self_third_person": "용의자가 자기 자신을 제3자나 가족 호칭으로 불렀습니다. 반드시 1인칭으로 말해야 합니다.",
    "script_direction": "괄호 지문이나 대본식 행동 묘사가 섞였습니다. 말풍선 대사만 남겨야 합니다.",
}


def build_rule_check_regen_prompt(
    agent_input: LightRuleCheckInput,
    issues: list[str],
    seed_text: str,
    attempt: int,
) -> tuple[LLMChatPrompt, str]:
    """재생성 프롬프트 payload와 seed를 반환한다."""
    draft = agent_input.draft
    tic, vocab_str = _extract_voice_directives(draft)
    tone_meta = getattr(draft, "tone", {}) or {}
    base_persona = _short_persona(getattr(draft, "persona", {}) or {})

    prompt = LLMChatPrompt(
        systemPrompt="당신은 탐정 누아르 추리 게임의 용의자입니다.",
        sections=[
            PromptSection(title="Quality Failures", kind="constraint", content=_render_fail_reasons(issues, tic)),
            PromptSection(title="Player Turn", kind="input", content=_build_player_turn_context(agent_input)),
            PromptSection(
                title="Character",
                kind="context",
                content={
                    "name": getattr(agent_input, "suspectName", None) or "(미지정)",
                    "persona": base_persona or "(미지정)",
                    "styleDirectives": _render_style_directives(tic, vocab_str),
                    "tensionLevel": tone_meta.get("tensionLevel", "normal"),
                    "pressureState": tone_meta.get("pressureState", "normal"),
                },
            ),
            PromptSection(title="Public Context", kind="context", content=_build_public_context(agent_input)),
            PromptSection(
                title="Retry Constraints",
                kind="constraint",
                content=[
                    "허용된 공개 사실을 벗어나지 않는다.",
                    "용의자가 심문 중 직접 말하는 대사로 다시 답한다.",
                    "자기 이름을 제3자처럼 말하지 않는다.",
                    "증거 소유자를 공개 사실 없이 새로 만들지 않는다.",
                    f"재시도: {attempt + 1}",
                ],
            ),
        ],
        outputInstruction="말풍선 대사만 한 줄로 출력하라.",
    )
    return prompt, seed_text


def _extract_voice_directives(draft: object) -> tuple[str, str]:
    voice = getattr(draft, "voice", {}) or {}
    speech_style = voice.get("speechStyle") or {}
    tic = str(speech_style.get("tic") or speech_style.get("prefix") or "").strip()
    vocab = speech_style.get("vocabulary") or []
    vocab_str = ", ".join(str(item) for item in vocab[:3]) if isinstance(vocab, list) else ""
    return tic, vocab_str


def _build_player_turn_context(agent_input: LightRuleCheckInput) -> dict[str, str | None]:
    function_call = agent_input.dialogueDirectorPlan.functionCall if agent_input.dialogueDirectorPlan else None
    raw_args = function_call.get("arguments") if isinstance(function_call, dict) else None
    args = raw_args if isinstance(raw_args, dict) else {}
    player_message = str(args.get("playerMessage") or "").strip()
    return {
        "playerQuestion": player_message or None,
        "dialogueStrategy": agent_input.dialogueDirectorPlan.strategy if agent_input.dialogueDirectorPlan else None,
        "responseRequirement": "원문 질문에 대한 응답성을 유지하라. 말투만 고치고 질문 대상/시간/증거 초점을 바꾸지 마라.",
    }


def _short_persona(persona_meta: dict) -> str:
    base_persona = str(persona_meta.get("basePersona") or "").strip()
    if len(base_persona) > 80:
        return base_persona[:79] + "…"
    return base_persona


def _render_fail_reasons(issues: list[str], tic: str) -> str:
    issue_map = dict(_ISSUE_MESSAGES)
    issue_map["no_style_tic"] = f"캐릭터의 말투 습관({tic})이 응답에 없습니다. 자연스럽게 포함하세요."
    return "\n".join(f"- {issue_map.get(issue, issue)}" for issue in issues)


def _build_public_context(agent_input: LightRuleCheckInput) -> str:
    context_lines: list[str] = []
    retrieved = getattr(agent_input, "retrieved_context", None)
    if retrieved and not retrieved.is_empty():
        if retrieved.matched_timeline_events:
            for event in retrieved.matched_timeline_events[:2]:
                context_lines.append(f"- 공개 타임라인: {event.get('time', '')} {event.get('title', '')}")
        if retrieved.matched_evidence:
            for evidence in retrieved.matched_evidence[:2]:
                context_lines.append(f"- 언급된 증거: {evidence.get('name', '')} — {evidence.get('description', '')[:60]}")
        if retrieved.matched_statements:
            for statement in retrieved.matched_statements[:1]:
                context_lines.append(f"- 관련 진술: {statement.get('text', '')[:80]}")

    source_facts = getattr(agent_input.allowedStatement, "sourceFacts", None) or []
    if isinstance(source_facts, list):
        context_lines.extend(f"- 공개 사실: {str(item)[:100]}" for item in source_facts[:3] if str(item or "").strip())
    return "\n".join(context_lines) if context_lines else "(없음)"


def _render_style_directives(tic: str, vocab_str: str) -> str:
    tic_directive = f"말투 습관: {tic}" if tic else ""
    vocab_directive = f"주요 어휘: {vocab_str}" if vocab_str else ""
    return "\n".join(d for d in [tic_directive, vocab_directive] if d) or "(기본 스타일)"
