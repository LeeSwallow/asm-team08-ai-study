from __future__ import annotations

import json

from app.ai_engine.prompts.dialogue import DIALOGUE_SYSTEM_PROMPT
from app.ai_engine.schemas.agents import DialogueDirectorPlan
from app.ai_engine.schemas.dialogue import DialogueRequest
from app.ai_engine.schemas.prompts import LLMChatPrompt, PromptSection


def knowledge_prompt_context(payload: DialogueRequest, retrieved_context: object | None = None) -> str:
    from app.ai_engine.agents.character_utils import _safe_short_text
    from app.ai_engine.agents.character_persona import knowledge_persona, knowledge_speech_style, select_persona_overlay

    pack = payload.characterKnowledgePack
    sections: list[str] = []

    source_facts = getattr(payload.allowedStatement, "sourceFacts", None) or []
    if isinstance(source_facts, list):
        safe_facts = [_safe_short_text(item, max_length=120) for item in source_facts[:4]]
        safe_facts = [item for item in safe_facts if item]
        if safe_facts:
            sections.append("Visible source facts: " + " / ".join(safe_facts))

    persona = knowledge_persona(payload)
    if persona:
        sections.append(f"Persona: {persona}")
    speech_style = knowledge_speech_style(payload)
    overlay = select_persona_overlay(payload)
    voice_parts = []
    vocabulary = speech_style.get("vocabulary")
    if isinstance(vocabulary, list):
        voice_parts.append("preferred words=" + ", ".join(str(item) for item in vocabulary[:4]))
    register = speech_style.get("register")
    if isinstance(register, str) and register.strip():
        voice_parts.append("register=" + _safe_short_text(register, max_length=60))
    address_style = speech_style.get("addressStyle") or speech_style.get("formality")
    if isinstance(address_style, str) and address_style.strip():
        voice_parts.append("address style=" + _safe_short_text(address_style, max_length=120))
    rhythm = speech_style.get("sentenceRhythm") or speech_style.get("rhythm")
    if isinstance(rhythm, str) and rhythm.strip():
        voice_parts.append("sentence rhythm=" + _safe_short_text(rhythm, max_length=100))
    avoid = speech_style.get("avoid") or speech_style.get("avoidPhrases")
    if isinstance(avoid, list):
        safe_avoid = [_safe_short_text(item, max_length=40) for item in avoid[:24]]
        safe_avoid = [item for item in safe_avoid if item]
        if safe_avoid:
            voice_parts.append("hard avoid=" + ", ".join(safe_avoid))
    sample_lines = speech_style.get("sampleLines") or speech_style.get("samples")
    if isinstance(sample_lines, list):
        safe_samples = [_safe_short_text(item, max_length=80) for item in sample_lines[:2]]
        safe_samples = [item for item in safe_samples if item]
        if safe_samples:
            voice_parts.append("sample lines=" + " / ".join(safe_samples))
    if overlay:
        if overlay.tone:
            voice_parts.append(f"state tone={overlay.tone}")
        if overlay.voice:
            voice_parts.append("state behavior=" + _safe_short_text(overlay.voice, max_length=120))
        if overlay.styleDirectives:
            voice_parts.append("state directives=" + ", ".join(str(item) for item in overlay.styleDirectives[:4]))
        if overlay.evasiveness is not None:
            voice_parts.append(f"evasiveness={overlay.evasiveness}")
        if overlay.hesitation is not None:
            voice_parts.append(f"hesitation={overlay.hesitation}")
    if voice_parts:
        sections.append("Voice state: " + " / ".join(voice_parts))

    if retrieved_context is not None and not getattr(retrieved_context, "is_empty", lambda: True)():
        _append_retrieved_context_sections(sections, retrieved_context)
    elif pack:
        for label, snippets in (
            ("Visible timeline", pack.visibleTimeline[:4]),
            ("Alibi", pack.alibiSnippets[:3]),
            ("Evidence", pack.evidenceSnippets[:3]),
        ):
            values = [_safe_short_text(snippet.text, max_length=120) for snippet in snippets]
            values = [value for value in values if value]
            if values:
                sections.append(f"{label}: " + " / ".join(values))

    if pack:
        rel_values = [_safe_short_text(s.text, max_length=120) for s in pack.relationshipSnippets[:3]]
        rel_values = [v for v in rel_values if v]
        if rel_values:
            sections.append("Relationships: " + " / ".join(rel_values))
        recent = [_safe_short_text(_recent_dialogue_value(item, "text", ""), max_length=80) for item in pack.recentDialogue[-4:]]
        recent = [item for item in recent if item]
        if recent:
            sections.append("Recent dialogue: " + " / ".join(recent))

    if not sections:
        return ""
    return (
        "\n\nPublic character context follows. It can shape memory, voice, and pressure continuity, "
        "but factual claims still come only from the FACT ANCHOR or visible refs.\n"
        + "\n".join(sections)
    )


def _append_retrieved_context_sections(sections: list[str], retrieved_context: object) -> None:
    from app.ai_engine.agents.character_utils import _safe_short_text

    timeline_events = getattr(retrieved_context, "matched_timeline_events", None) or []
    if timeline_events:
        timeline_texts = [
            _safe_short_text(f"{ev.get('time', '')} {ev.get('title', '')} {ev.get('description', '')}", max_length=100)
            for ev in timeline_events[:4]
        ]
        timeline_texts = [text for text in timeline_texts if text]
        if timeline_texts:
            sections.append("Relevant timeline: " + " / ".join(timeline_texts))
    matched_evidence = getattr(retrieved_context, "matched_evidence", None) or []
    if matched_evidence:
        evidence_texts = [
            _safe_short_text(f"{ev.get('name', '')} — {ev.get('description', '')}", max_length=100)
            for ev in matched_evidence[:3]
        ]
        evidence_texts = [text for text in evidence_texts if text]
        if evidence_texts:
            sections.append("Matched evidence: " + " / ".join(evidence_texts))
    matched_statements = getattr(retrieved_context, "matched_statements", None) or []
    if matched_statements:
        statement_texts = [_safe_short_text(st.get("text", ""), max_length=120) for st in matched_statements[:2]]
        statement_texts = [text for text in statement_texts if text]
        if statement_texts:
            sections.append("Related statements: " + " / ".join(statement_texts))
    alibi_summary = getattr(retrieved_context, "alibi_summary", None)
    if alibi_summary:
        sections.append(f"Alibi summary: {_safe_short_text(str(alibi_summary), max_length=100)}")


def _recent_dialogue_value(item: object, field: str, default: object = None) -> object:
    if isinstance(item, dict):
        return item.get(field, default)
    return getattr(item, field, default)


def _recent_dialogue_list(item: object, field: str, limit: int) -> list[str]:
    value = _recent_dialogue_value(item, field, [])
    if not isinstance(value, list):
        return []
    return [str(entry) for entry in value[:limit]]


def dialogue_history_prompt_section(payload: DialogueRequest) -> PromptSection | None:
    """Expose recent dialogue as structured continuity data for CharacterAgent."""
    from app.ai_engine.agents.character_utils import _safe_short_text

    pack = payload.characterKnowledgePack
    if not pack or not pack.recentDialogue:
        return None
    turns: list[dict[str, object]] = []
    for index, item in enumerate(pack.recentDialogue[-8:], start=1):
        text = _safe_short_text(_recent_dialogue_value(item, "text", ""), max_length=140)
        if not text:
            continue
        turns.append(
            {
                "turn": index,
                "speaker": _recent_dialogue_value(item, "speaker", "unknown"),
                "text": text,
                "questionId": _recent_dialogue_value(item, "questionId"),
                "statementId": _recent_dialogue_value(item, "statementId"),
                "evidenceIds": _recent_dialogue_list(item, "evidenceIds", 3),
                "tags": _recent_dialogue_list(item, "tags", 4),
            }
        )
    if not turns:
        return None
    return PromptSection(
        title="Dialogue History",
        kind="context",
        content={
            "turns": turns,
            "continuityInstruction": (
                "이 history는 캐릭터의 기억/감정선/반복 회피를 위한 공개 대화 맥락이다. "
                "새로 받은 압박에는 마지막 suspect 답변과 같은 문장 구조를 반복하지 말고, "
                "직전 player 발화에서 이어지는 감정 반응을 먼저 만든다. "
                "history에 없는 새 사실은 만들지 않는다."
            ),
        },
    )


def character_output_contract_section() -> PromptSection:
    return PromptSection(
        title="CharacterAgent Output Contract",
        kind="output",
        content={
            "type": "object",
            "required": ["speakerIntent", "emotionalBeat", "continuityMove", "finalLine"],
            "properties": {
                "speakerIntent": "이번 발화의 목적: answer_visible_fact | deflect | resist_pressure | ask_clarification | refuse_private 중 하나",
                "emotionalBeat": "캐릭터의 즉시 감정 반응을 5~20자로 요약. 말풍선에는 직접 넣지 않아도 된다.",
                "continuityMove": "history와의 연결 방식: new_answer | escalates_previous | avoids_repetition | clarifies_short_turn 중 하나",
                "finalLine": "용의자가 직접 말하는 현대 한국어 대사 1~2문장. 이 필드만 플레이어에게 표시된다.",
            },
            "hardRules": [
                "JSON 객체 하나만 출력한다.",
                "finalLine은 Player Turn에 직접 반응해야 한다.",
                "finalLine은 FACT ANCHOR/public refs를 넘는 새 사실을 만들지 않는다.",
                "speakerIntent/emotionalBeat/continuityMove는 내부 구조화 신호이며 finalLine에 메타 단어로 노출하지 않는다.",
            ],
        },
    )


def director_prompt_context(plan: DialogueDirectorPlan | None) -> str:
    if plan is None:
        return ""
    parts = [f"strategy={plan.strategy}", f"admission={plan.allowedAdmissionLevel}"]
    if plan.focusTerms:
        parts.append("focusTerms=" + ", ".join(plan.focusTerms[:3]))
    if plan.styleDirectives:
        parts.append("directives=" + " / ".join(plan.styleDirectives[:3]))
    if plan.forbiddenClaims:
        parts.append("forbidden=" + " / ".join(plan.forbiddenClaims[:3]))
    if plan.functionCall:
        parts.append(f"function={plan.functionCall.get('name')}")
    return (
        "\n\nDialogue director plan for this turn: "
        + " / ".join(str(part) for part in parts if part)
        + "\nFollow the director seed/function transition and constraints before style embellishment."
    )


def answer_plan_prompt_section(plan: DialogueDirectorPlan | None) -> PromptSection | None:
    if plan is None or not plan.answerPlan:
        return None
    answer_plan = dict(plan.answerPlan)
    return PromptSection(
        title="Structured Answer Plan",
        kind="constraint",
        content={
            "directAnswer": answer_plan.get("directAnswer"),
            "responseIntent": answer_plan.get("responseIntent"),
            "characterStance": answer_plan.get("characterStance"),
            "reactionRoute": answer_plan.get("reactionRoute"),
            "factAnchor": answer_plan.get("factAnchor"),
            "admissionBoundary": answer_plan.get("admissionBoundary"),
            "lieRoute": answer_plan.get("lieRoute") or {},
            "focusTerms": answer_plan.get("focusTerms") or [],
            "recentDialogue": answer_plan.get("recentDialogue") or [],
            "repeatPolicy": answer_plan.get("repeatPolicy"),
            "generationDirective": (
                "finalLine은 directAnswer/admissionBoundary/lieRoute를 따른 새 대사여야 한다. "
                "lieRoute가 있으면 용의자는 아직 거짓말을 유지한다. 방금 압박받은 단서를 곧바로 인정하지 말고, "
                "거짓 알리바이를 지키기 위한 그럴듯한 변명으로 반응한다."
            ),
            "forbiddenSurfacePhrases": answer_plan.get("forbiddenSurfacePhrases") or [],
            "forbiddenClaims": answer_plan.get("forbiddenClaims") or [],
            "outputShape": answer_plan.get("outputShape"),
        },
    )


def interrogation_prompt_context(payload: DialogueRequest, plan: DialogueDirectorPlan | None = None) -> str:
    transition = payload.interrogationTransition or {}
    snapshot = payload.interrogationState or {}
    turn = payload.turnInterpretation or {}
    if not transition and not snapshot and not turn:
        return ""
    parts = [
        f"intent={turn.get('intent') or transition.get('move') or 'unknown'}",
        f"move={transition.get('move') or 'unknown'}",
        f"composure={transition.get('composure') or snapshot.get('composure') or 'calm'}",
        f"disclosure={transition.get('disclosureStage') or snapshot.get('disclosureStage') or 'denial'}",
    ]
    if turn.get("mentionedEvidenceIds"):
        parts.append("mentionedEvidenceIds=" + ",".join(turn.get("mentionedEvidenceIds") or []))
    if turn.get("matchedTimelineIds"):
        parts.append("matchedTimelineIds=" + ",".join(turn.get("matchedTimelineIds") or []))
    if transition.get("decisiveEvidence"):
        parts.append("decisiveEvidence=true")
    if transition.get("contradictionIds"):
        parts.append("visibleContradictionIds=" + ",".join(transition.get("contradictionIds") or []))
    context = "\n\nInterrogation state for this turn: " + " / ".join(str(part) for part in parts if part)
    if transition.get("decisiveEvidence"):
        context += (
            "\nThe player has just connected a visible evidence item to the suspect's earlier statement. "
            "Let the suspect react as a pressured person first, acknowledge only the conflict, and do not confess."
        )
    elif transition.get("move") == "repeat_pressure":
        context += "\nThe player is challenging the previous answer. Keep continuity and do not repeat the exact same sentence."
    return context + director_prompt_context(plan)


def build_character_dialogue_prompt(
    payload: DialogueRequest,
    retrieved_context: object | None,
    plan: DialogueDirectorPlan | None,
) -> LLMChatPrompt:
    """Build the CharacterAgent prompt as typed sections, not ad-hoc concatenated text."""
    sections: list[PromptSection] = []
    sections.append(
        PromptSection(
            title="Agent Construction",
            kind="instruction",
            content={
                "agent": "CharacterAgent",
                "role": "선택된 용의자 본인으로서 플레이어 발화에 답하는 생성 에이전트",
                "pipeline": [
                    "1. Player Turn에서 질문 대상/시간/증거/압박 의도를 먼저 파악한다.",
                    "2. Dialogue Director Plan의 functionCall/answerPlan으로 이번 턴의 반응 함수를 고른다.",
                    "3. Dialogue History에서 직전 답변과 반복 금지 지점을 확인한다.",
                    "4. Public Character Context와 speechStyle로 말투·호흡·감정선을 입힌다.",
                    "5. FACT ANCHOR 밖의 새 사실은 제거하고 CharacterAgent Output Contract JSON으로만 응답한다.",
                ],
                "stateAuthority": "CharacterAgent는 대사만 생성한다. unlock/tension/verdict/event 적용은 GameMaster 제안 후 BE EventProcessor가 검증한다.",
            },
        )
    )
    terse_vague = False
    if plan and plan.functionCall:
        raw_args = plan.functionCall.get("arguments")
        args = raw_args if isinstance(raw_args, dict) else {}
        terse_vague = bool(args.get("terseVague"))
    interrogation = interrogation_prompt_context(payload, plan).strip()
    if interrogation:
        sections.append(PromptSection(title="Interrogation State", kind="context", content=interrogation))
    knowledge = knowledge_prompt_context(payload, retrieved_context).strip()
    if knowledge:
        sections.append(PromptSection(title="Public Character Context", kind="context", content=knowledge))
    history_section = dialogue_history_prompt_section(payload)
    if history_section is not None:
        sections.append(history_section)
    sections.append(
        PromptSection(
            title="Player Turn",
            kind="input",
            content={
                "playerQuestion": payload.question.text,
                "dialogueMode": payload.dialogueMode,
                "turnIntent": (payload.turnInterpretation or {}).get("intent"),
                "responseRequirement": "사용자의 이번 발화에 직접 반응하라. 단, 공개 사실 범위 안에서만 답하고 모르면 모른다고 버틴다. FACT ANCHOR가 이번 턴의 유일한 사실 답변 축이다. Public Character Context/Relationships/Recent dialogue는 말투와 감정선 참고용이며, FACT ANCHOR와 다른 관계·증거·인물 정보를 답변 본문에 끌어오지 않는다. 플레이어가 같은 의심을 반복하면 Recent dialogue와 같은 문장 구조/같은 논지를 반복하지 말고, 감정선만 한 단계 올려 다른 표현으로 방어한다. 플레이어가 '뭐야'처럼 매우 짧게 물으면 임의로 시간/증거/진술 축을 만들지 말고, FACT ANCHOR에 가깝게 인물의 말투로 무엇을 묻는지 특정해 달라고 하라.",
            },
        )
    )
    if plan:
        answer_plan_section = answer_plan_prompt_section(plan)
        if answer_plan_section is not None:
            sections.append(answer_plan_section)
            sections.append(
                PromptSection(
                    title="Final-Line Examples",
                    kind="context",
                    content={
                        "examples": [
                            {
                                "input": {
                                    "route": "react_to_valid_pressure",
                                    "lieRoute": {"defenseTactic": "전산 오류나 카드키 분실 가능성으로 잡아뗀다."},
                                    "bad": "그 기록이 걸리는 건 알아. 그래도 그걸로 끝난 것처럼 몰지 마.",
                                },
                                "output": {"finalLine": "전산 오류겠지. 아니면 누가 내 카드키를 주웠거나. 그걸 왜 바로 나라고 해?"},
                            },
                            {
                                "input": {"route": "ask_clarification", "bad": "어떤 증거를 말하는지 구체적으로 말씀해 주세요."},
                                "output": {"finalLine": "뭘 묻는 건지부터 분명히 말해."},
                            },
                        ]
                    },
                )
            )
        sections.append(
            PromptSection(
                title="Dialogue Director Plan",
                kind="instruction",
                content={
                    "strategy": plan.strategy,
                    "allowedAdmissionLevel": plan.allowedAdmissionLevel,
                    "styleDirectives": [
                        *plan.styleDirectives,
                        "사용자 원문 질문의 대상/시간/증거에 먼저 반응한 뒤 캐릭터 말투를 입힌다.",
                        "Public Character Context의 hard avoid/register/address style/sample lines를 반드시 따른다. 후처리 보정 없이도 그대로 쓸 수 있는 대사를 만든다.",
                        "관계 질문에서는 사용자가 지정한 관계 대상만 답한다. 예: '회장님과의 관계'는 피해자와의 관계만 답하고, 다른 인물과의 유대/비밀은 언급하지 않는다.",
                        "Recent dialogue와 의미상 같은 대사를 반복하지 않는다. 재압박이면 더 짧고 흔들린 표현으로 바꾼다.",
                    ],
                    "forbiddenClaims": plan.forbiddenClaims,
                    "focusTerms": plan.focusTerms,
                    "functionCall": plan.functionCall,
                    "reason": plan.reason,
                },
            )
        )
    sections.append(character_output_contract_section())
    output_schema = {
        "speakerIntent": "answer_visible_fact | deflect | resist_pressure | ask_clarification | refuse_private",
        "emotionalBeat": "즉시 감정 반응 요약",
        "continuityMove": "new_answer | escalates_previous | avoids_repetition | clarifies_short_turn",
        "finalLine": "용의자가 직접 말하는 현대 한국어 대사 1~2문장",
    }
    output_instruction = (
        "JSON 객체만 출력하라. CharacterAgent Output Contract를 반드시 따른다. 형식: "
        + json.dumps(output_schema, ensure_ascii=False)
        + ". finalLine만 플레이어에게 노출된다. JSON 밖에 해설, 사고과정, 규칙 설명을 넣지 마라."
    )
    if terse_vague:
        output_instruction += " 이번 턴은 모호한 짧은 발화이므로 '시간/증거/진술 중' 같은 선택지 나열을 finalLine에 넣지 마라."
    return LLMChatPrompt(
        systemPrompt=DIALOGUE_SYSTEM_PROMPT,
        sections=sections,
        outputInstruction=output_instruction,
    )
