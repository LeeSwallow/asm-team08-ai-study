from __future__ import annotations

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
        safe_avoid = [_safe_short_text(item, max_length=40) for item in avoid[:4]]
        safe_avoid = [item for item in safe_avoid if item]
        if safe_avoid:
            voice_parts.append("avoid=" + ", ".join(safe_avoid))
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
        recent = [_safe_short_text(item.text, max_length=80) for item in pack.recentDialogue[-4:]]
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
    sections.append(
        PromptSection(
            title="Player Turn",
            kind="input",
            content={
                "playerQuestion": payload.question.text,
                "dialogueMode": payload.dialogueMode,
                "turnIntent": (payload.turnInterpretation or {}).get("intent"),
                "responseRequirement": "사용자의 이번 발화에 직접 반응하라. 단, 공개 사실 범위 안에서만 답하고 모르면 모른다고/구체화해 달라고 말하라. 플레이어가 '뭐야'처럼 매우 짧게 물으면 임의로 시간/증거/진술 축을 만들지 말고, FACT ANCHOR에 가깝게 인물의 말투로 무엇을 묻는지 특정해 달라고 하라.",
            },
        )
    )
    if plan:
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
                    ],
                    "forbiddenClaims": plan.forbiddenClaims,
                    "focusTerms": plan.focusTerms,
                    "functionCall": plan.functionCall,
                    "reason": plan.reason,
                },
            )
        )
    output_instruction = "따옴표 없이, 현대 한국어 구어체로, 용의자의 다음 대사 한 줄만 출력하라."
    if terse_vague:
        output_instruction += " 이번 턴은 모호한 짧은 발화이므로 FACT ANCHOR를 거의 유지하고, '시간/증거/진술 중' 같은 선택지 나열을 추가하지 마라."
    return LLMChatPrompt(
        systemPrompt=DIALOGUE_SYSTEM_PROMPT,
        sections=sections,
        outputInstruction=output_instruction,
    )
