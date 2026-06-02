from __future__ import annotations

from app.ai_engine.core.guard import contains_secret
from app.ai_engine.core.llm import ChainedLLM, deterministic_clip, get_llm, llm_status
from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent, normalize_dialogue_text
from app.ai_engine.prompts.dialogue import DIALOGUE_SYSTEM_PROMPT
from app.ai_engine.schemas.agents import CharacterAgentInput, DialogueDirectorPlan, DraftCharacterReply
from app.ai_engine.schemas.common import PersonaOverlay, PersonaVariant
from app.ai_engine.schemas.dialogue import DialogueRequest


def _normalized_tension_score(value: int | float | None) -> float | None:
    if value is None:
        return None
    score = float(value)
    if score <= 1:
        return score * 100
    return score


def _safe_short_text(value: object, max_length: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if contains_secret(text)[0] or any(term in text.lower() for term in ("secret", "solution", "isculprit", "secretnote")):
        return ""
    if len(text) > max_length:
        return text[: max_length - 1].rstrip() + "…"
    return text


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


def _knowledge_persona(payload: DialogueRequest) -> str:
    pack = payload.characterKnowledgePack
    if not pack:
        return payload.suspect.publicPersona or ""
    return _safe_short_text(pack.publicPersona or pack.persona or payload.suspect.publicPersona, max_length=160)


def _knowledge_speech_style(payload: DialogueRequest) -> dict[str, object]:
    pack = payload.characterKnowledgePack
    overlay = select_persona_overlay(payload)
    if overlay and overlay.speechStyle:
        return overlay.speechStyle
    if pack and pack.speechStyle:
        return pack.speechStyle
    return payload.suspect.speechStyle


def _recent_dialogue_pressure(payload: DialogueRequest) -> bool:
    pack = payload.characterKnowledgePack
    if not pack:
        return False
    recent_text = " ".join(_safe_short_text(item.text, max_length=80) for item in pack.recentDialogue[-4:])
    pressure_tokens = ("왜", "말이", "답변", "못해", "정말", "거짓", "이상", "모순", "압박")
    return any(token in recent_text for token in pressure_tokens)


def _question_focus(payload: DialogueRequest) -> str | None:
    normalized = normalize_dialogue_text(payload.question.text)
    if any(token in normalized for token in ("립스틱", "와인잔", "와인", "자국")):
        return "lipstick_wine"
    if any(token in normalized for token in ("약", "약물", "복용", "처방", "의사", "의료", "피해자")):
        return "medical"
    if any(token in normalized for token in ("누가", "누구", "다른 사람", "관계")):
        return "person_relation"
    return None


def _question_mentions_lipstick_mark(payload: DialogueRequest) -> bool:
    normalized = normalize_dialogue_text(payload.question.text)
    return any(token in normalized for token in ("립스틱", "자국"))


def _has_matched_evidence_refs(payload: DialogueRequest) -> bool:
    refs = payload.allowedStatement.sourceRefs
    return bool(refs.evidenceIds or payload.allowedEventPolicy.relatedEvidenceIds)


def _has_matched_contradiction_refs(payload: DialogueRequest) -> bool:
    refs = payload.allowedStatement.sourceRefs
    return bool(refs.contradictionIds or payload.allowedEventPolicy.relatedContradictionIds)


def _knowledge_prompt_context(payload: DialogueRequest, retrieved_context: object | None = None) -> str:
    pack = payload.characterKnowledgePack
    sections: list[str] = []

    source_facts = getattr(payload.allowedStatement, "sourceFacts", None) or []
    if isinstance(source_facts, list):
        safe_facts = [_safe_short_text(item, max_length=120) for item in source_facts[:4]]
        safe_facts = [item for item in safe_facts if item]
        if safe_facts:
            sections.append("Visible source facts: " + " / ".join(safe_facts))

    # ── 페르소나 ─────────────────────────────────────────────────────────────
    persona = _knowledge_persona(payload)
    if persona:
        sections.append(f"Persona: {persona}")
    speech_style = _knowledge_speech_style(payload)
    overlay = select_persona_overlay(payload)
    voice_parts = []
    if speech_style.get("vocabulary"):
        voice_parts.append("preferred words=" + ", ".join(str(item) for item in speech_style.get("vocabulary", [])[:4]))
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

    # ── KnowledgeRetriever 결과 우선 사용 (질문 관련 이벤트/증거/진술) ────────
    if retrieved_context is not None and not getattr(retrieved_context, "is_empty", lambda: True)():
        rc = retrieved_context
        if getattr(rc, "matched_timeline_events", None):
            timeline_texts = [
                _safe_short_text(f"{ev.get('time', '')} {ev.get('title', '')} {ev.get('description', '')}", max_length=100)
                for ev in rc.matched_timeline_events[:4]
            ]
            timeline_texts = [t for t in timeline_texts if t]
            if timeline_texts:
                sections.append("Relevant timeline: " + " / ".join(timeline_texts))
        if getattr(rc, "matched_evidence", None):
            ev_texts = [
                _safe_short_text(f"{ev.get('name', '')} — {ev.get('description', '')}", max_length=100)
                for ev in rc.matched_evidence[:3]
            ]
            ev_texts = [t for t in ev_texts if t]
            if ev_texts:
                sections.append("Matched evidence: " + " / ".join(ev_texts))
        if getattr(rc, "matched_statements", None):
            st_texts = [
                _safe_short_text(st.get("text", ""), max_length=120)
                for st in rc.matched_statements[:2]
            ]
            st_texts = [t for t in st_texts if t]
            if st_texts:
                sections.append("Related statements: " + " / ".join(st_texts))
        if getattr(rc, "alibi_summary", None):
            sections.append(f"Alibi summary: {_safe_short_text(rc.alibi_summary, max_length=100)}")
    elif pack:
        # ── KnowledgeRetriever 없을 때 기존 방식 (pack.visibleTimeline[:4]) ──
        for label, snippets in (
            ("Visible timeline", pack.visibleTimeline[:4]),
            ("Alibi", pack.alibiSnippets[:3]),
            ("Evidence", pack.evidenceSnippets[:3]),
        ):
            values = [_safe_short_text(snippet.text, max_length=120) for snippet in snippets]
            values = [value for value in values if value]
            if values:
                sections.append(f"{label}: " + " / ".join(values))

    # ── 관계 및 최근 대화 (항상 pack에서) ─────────────────────────────────────
    if pack:
        rel_snippets = pack.relationshipSnippets[:3]
        rel_values = [_safe_short_text(s.text, max_length=120) for s in rel_snippets]
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


def _director_prompt_context(plan: DialogueDirectorPlan | None) -> str:
    if plan is None:
        return ""
    parts = [
        f"strategy={plan.strategy}",
        f"admission={plan.allowedAdmissionLevel}",
    ]
    if plan.focusTerms:
        parts.append("focusTerms=" + ", ".join(plan.focusTerms[:3]))
    if plan.styleDirectives:
        parts.append("directives=" + " / ".join(plan.styleDirectives[:3]))
    if plan.forbiddenClaims:
        parts.append("forbidden=" + " / ".join(plan.forbiddenClaims[:3]))
    return (
        "\n\nDialogue director plan for this turn: "
        + " / ".join(str(part) for part in parts if part)
        + "\nFollow the director seed and constraints before style embellishment."
    )


def _interrogation_prompt_context(payload: DialogueRequest, plan: DialogueDirectorPlan | None = None) -> str:
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
    return context + _director_prompt_context(plan)


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


def build_character_agent_input(
    payload: DialogueRequest,
    dialogue_director_plan: DialogueDirectorPlan | None = None,
) -> CharacterAgentInput:
    pack = payload.characterKnowledgePack
    intent = classify_dialogue_intent(payload.question.text, payload.dialogueMode)
    return CharacterAgentInput(
        payload=payload,
        requestId=payload.requestId,
        correlationId=payload.correlationId,
        message=payload.question.text,
        dialogueMode=payload.dialogueMode,
        intent=intent,
        allowedStatement=payload.allowedStatement,
        allowedEventPolicy=payload.allowedEventPolicy,
        characterKnowledgePack=pack,
        activePersonaOverlay=select_persona_overlay(payload),
        personaVariants=pack.personaVariants if pack else [],
        style=payload.style.model_dump(),
        revealAllowed=payload.revealAllowed,
        tensionLevel=payload.suspect.tensionLevel,
        pressureState=payload.suspect.pressureState,
        emotionalState=payload.suspect.emotionalState,
        tensionScore=payload.suspect.tensionScore if payload.suspect.tensionScore is not None else payload.suspect.pressure,
        interrogationState=payload.interrogationState,
        interrogationTransition=payload.interrogationTransition,
        dialogueDirectorPlan=dialogue_director_plan,
        recentDialogue=pack.recentDialogue if pack else [],
    )


def render_dialogue_seed(payload: DialogueRequest, dialogue_director_plan: DialogueDirectorPlan | None = None) -> str:
    if dialogue_director_plan and dialogue_director_plan.seedText:
        return dialogue_director_plan.seedText
    base = payload.allowedStatement.text.strip()
    name = payload.suspect.name.strip()
    intent = classify_dialogue_intent(payload.question.text, payload.dialogueMode)
    if intent == "greeting":
        return f"저는 {name}입니다."
    if intent == "unmatched":
        return "그 질문에는 바로 답하기 어렵습니다."
    return base or "제가 공개적으로 말할 수 있는 건 거기까지입니다."


class CharacterAgent:
    def run(
        self,
        agent_input: CharacterAgentInput,
        retrieved_context: object | None = None,
    ) -> DraftCharacterReply:
        payload = agent_input.payload
        seed = render_dialogue_seed(payload, agent_input.dialogueDirectorPlan)
        status = llm_status()
        provider = str(status["provider"])
        model = str(status["model"])

        def draft(
            text: str,
            *,
            fallback_used: bool,
            degraded: bool | None = None,
            blocked_reason: str | None = None,
            provider_name: str | None = None,
            error_type: str | None = None,
        ) -> DraftCharacterReply:
            overlay = agent_input.activePersonaOverlay
            text = _strip_outer_dialogue_quotes(text)
            refs = payload.allowedStatement.sourceRefs.model_copy()
            intent = agent_input.intent or classify_dialogue_intent(payload.question.text, payload.dialogueMode)
            if intent in {"greeting", "unmatched"}:
                refs.statementIds = []
                refs.evidenceIds = []
                refs.timelineIds = []
                refs.questionIds = []
                refs.contradictionIds = []
            elif payload.allowedStatement.id not in refs.statementIds:
                refs.statementIds = [payload.allowedStatement.id, *refs.statementIds]
            return DraftCharacterReply(
                requestId=payload.requestId,
                correlationId=payload.correlationId,
                suspectId=payload.suspect.id,
                draftText=text,
                usedRefs=refs,
                sourceRefs=refs,
                voiceMetadata={
                    "tone": overlay.tone if overlay else payload.style.tone,
                    "hesitation": overlay.hesitation if overlay else None,
                    "evasiveness": overlay.evasiveness if overlay else None,
                    "tensionLevel": agent_input.tensionLevel,
                    "pressureState": agent_input.pressureState,
                },
                personaOverlayId=overlay.id if overlay else None,
                voice={
                    "speechStyle": _knowledge_speech_style(payload),
                    "overlayVoice": overlay.voice if overlay else None,
                },
                tone={
                    "styleTone": payload.style.tone,
                    "tensionLevel": agent_input.tensionLevel,
                    "pressureState": agent_input.pressureState,
                    "emotionalState": agent_input.emotionalState,
                    "tensionScore": agent_input.tensionScore,
                    "overlayTone": overlay.tone if overlay else None,
                },
                persona={
                    "basePersona": _knowledge_persona(payload),
                    "overlayId": overlay.id if overlay else None,
                    "overlayLabel": overlay.label if overlay else None,
                    "selectedFrom": overlay.selectedFrom if overlay else None,
                    "variantCount": len(agent_input.personaVariants),
                    "recentDialogueCount": len(agent_input.recentDialogue),
                },
                fallbackUsed=fallback_used,
                degraded=fallback_used if degraded is None else degraded,
                provider=provider_name or provider,
                model=model,
                blockedReason=blocked_reason,
                errorType=error_type,
                timeoutMs=status.get("timeoutMs") if isinstance(status.get("timeoutMs"), int) else None,
                providerConfigured=bool(status.get("configured", provider not in {"provider-unavailable"})),
            )

        if provider == "deterministic-fallback":
            return draft(
                deterministic_clip(seed, max_length=payload.style.maxLength),
                fallback_used=True,
                blocked_reason="deterministic_fallback_selected",
            )

        if provider == "provider-unavailable":
            return draft(
                "현재 생성 provider 설정 문제로 인물 답변을 제공할 수 없습니다.",
                fallback_used=True,
                degraded=True,
                blocked_reason=str(status.get("degradedReason") or "provider_unavailable"),
                error_type="provider_unavailable",
            )

        if agent_input.dialogueDirectorPlan and agent_input.dialogueDirectorPlan.seedText:
            strategy = agent_input.dialogueDirectorPlan.strategy
            if strategy in {"defensive_pressure", "deflect_unmatched"}:
                return draft(
                    deterministic_clip(seed, max_length=payload.style.maxLength),
                    fallback_used=False,
                    degraded=False,
                    provider_name="dialogue-director",
                )

        try:
            prompt = (
                DIALOGUE_SYSTEM_PROMPT
                + _interrogation_prompt_context(payload, agent_input.dialogueDirectorPlan)
                + _knowledge_prompt_context(payload, retrieved_context)
            )
            llm = get_llm()
            text = llm.complete(prompt, seed_text=seed, max_length=payload.style.maxLength)
            # If ChainedLLM silently switched to fallback, report it honestly.
            if isinstance(llm, ChainedLLM) and llm.used_fallback_on_last_call:
                actual_provider = getattr(llm.fallback, "provider_name", "chain-fallback")
                return draft(
                    text,
                    fallback_used=True,
                    degraded=False,
                    blocked_reason=f"primary_provider_failed:{llm.fallback_reason_on_last_call}",
                    provider_name=actual_provider,
                )
            return draft(text, fallback_used=False)
        except Exception as exc:
            return draft(
                "현재 생성 provider 장애로 인물 답변을 제공할 수 없습니다.",
                fallback_used=True,
                degraded=True,
                blocked_reason="provider_exception_fallback",
                provider_name=provider,
                error_type=type(exc).__name__,
            )


def run_character_agent(
    payload: DialogueRequest,
    retrieved_context: object | None = None,
) -> DraftCharacterReply:
    return CharacterAgent().run(build_character_agent_input(payload), retrieved_context)
