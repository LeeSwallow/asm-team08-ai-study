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
    "forbidden_style_token": "캐릭터 speechStyle의 hard avoid 어휘/어미/호칭이 응답에 포함되었습니다. 해당 표현을 쓰지 말고 새로 답해야 합니다.",
    "forbidden_answer_plan_phrase": "구조화된 answerPlan에서 금지한 메타/규칙형 문구가 응답에 포함되었습니다. 용의자 대사로 다시 써야 합니다.",
    "near_duplicate_recent_reply": "최근 같은 용의자 대사와 거의 같습니다. 같은 사실 범위를 유지하되 다른 감정 반응과 문장 구조로 다시 답해야 합니다.",
    "vulgar_style_token": "비속어는 아니어도 거칠고 저급한 표현이 섞였습니다. 욕설 없이 날 선 방어적 말투로 다시 답해야 합니다.",
    "relationship_scope_drift": "관계 질문에서 FACT ANCHOR 밖의 사업/동선/새 갈등을 끌어왔습니다. 피해자와의 관계만 답해야 합니다.",
}


def build_rule_check_regen_prompt(
    agent_input: LightRuleCheckInput,
    issues: list[str],
    seed_text: str,
    attempt: int,
) -> tuple[LLMChatPrompt, str]:
    """재생성 프롬프트 payload와 seed를 반환한다."""
    draft = agent_input.draft
    tic, vocab_str, avoid_str, style_contract = _extract_voice_directives(draft)
    tone_meta = getattr(draft, "tone", {}) or {}
    base_persona = _short_persona(getattr(draft, "persona", {}) or {})

    prompt = LLMChatPrompt(
        systemPrompt="당신은 탐정 누아르 추리 게임의 용의자입니다.",
        sections=[
            PromptSection(title="Quality Failures", kind="constraint", content=_render_fail_reasons(issues, tic)),
            PromptSection(title="Player Turn", kind="input", content=_build_player_turn_context(agent_input)),
            PromptSection(title="Structured Answer Plan", kind="constraint", content=_build_answer_plan_context(agent_input)),
            PromptSection(
                title="Character",
                kind="context",
                content={
                    "name": getattr(agent_input, "suspectName", None) or "(미지정)",
                    "persona": base_persona or "(미지정)",
                    "styleDirectives": _render_style_directives(tic, vocab_str, avoid_str, style_contract),
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


def _extract_voice_directives(draft: object) -> tuple[str, str, str, str]:
    voice = getattr(draft, "voice", {}) or {}
    speech_style = voice.get("speechStyle") or {}
    tic = str(speech_style.get("tic") or speech_style.get("prefix") or "").strip()
    vocab = speech_style.get("vocabulary") or []
    vocab_str = ", ".join(str(item) for item in vocab[:3]) if isinstance(vocab, list) else ""
    avoid = speech_style.get("avoid") or speech_style.get("avoidPhrases") or []
    avoid_str = ", ".join(str(item) for item in avoid[:24]) if isinstance(avoid, list) else ""
    register = str(speech_style.get("register") or "").strip()
    address_style = str(speech_style.get("addressStyle") or speech_style.get("formality") or "").strip()
    style_contract = " / ".join(item for item in (f"register={register}" if register else "", f"addressStyle={address_style}" if address_style else "") if item)
    return tic, vocab_str, avoid_str, style_contract


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


def _build_answer_plan_context(agent_input: LightRuleCheckInput) -> dict[str, object]:
    plan = agent_input.dialogueDirectorPlan
    answer_plan = dict(plan.answerPlan) if plan and plan.answerPlan else {}
    return {
        "directAnswer": answer_plan.get("directAnswer"),
        "factAnchor": answer_plan.get("factAnchor") or agent_input.allowedStatement.text,
        "admissionBoundary": answer_plan.get("admissionBoundary") or (plan.allowedAdmissionLevel if plan else None),
        "focusTerms": answer_plan.get("focusTerms") or (plan.focusTerms if plan else []),
        "recentDialogue": answer_plan.get("recentDialogue") or [],
        "repeatPolicy": answer_plan.get("repeatPolicy"),
        "forbiddenSurfacePhrases": answer_plan.get("forbiddenSurfacePhrases") or [],
        "outputShape": answer_plan.get("outputShape") or "말풍선 대사 한 줄",
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


def _render_style_directives(tic: str, vocab_str: str, avoid_str: str, style_contract: str) -> str:
    tic_directive = f"말투 습관: {tic}" if tic else ""
    vocab_directive = f"주요 어휘: {vocab_str}" if vocab_str else ""
    avoid_directive = f"hard avoid: {avoid_str}" if avoid_str else ""
    contract_directive = f"style contract: {style_contract}" if style_contract else ""
    return "\n".join(d for d in [tic_directive, vocab_directive, avoid_directive, contract_directive] if d) or "(기본 스타일)"
