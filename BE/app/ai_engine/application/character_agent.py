from __future__ import annotations

from app.ai_engine.core.guard import contains_secret
from app.ai_engine.core.llm import ChainedLLM, deterministic_clip, get_llm, llm_status
from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent, normalize_dialogue_text
from app.ai_engine.prompts.dialogue import DIALOGUE_SYSTEM_PROMPT
from app.ai_engine.schemas.agents import CharacterAgentInput, DraftCharacterReply
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

    # ── 페르소나 ─────────────────────────────────────────────────────────────
    persona = _knowledge_persona(payload)
    if persona:
        sections.append(f"Persona: {persona}")

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
        "\n\nCharacterKnowledgePack is BE-curated public context. Use it for voice, pressure continuity, "
        "and choosing which visible public angle to acknowledge. Do not add factual claims unless they are "
        "in the allowed statement or stable source refs.\n"
        + "\n".join(sections)
    )


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


def build_character_agent_input(payload: DialogueRequest) -> CharacterAgentInput:
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
        recentDialogue=pack.recentDialogue if pack else [],
    )


def render_dialogue_seed(payload: DialogueRequest) -> str:
    base = payload.allowedStatement.text.strip()
    tone = payload.style.tone
    act_id = payload.storyline.currentActId if payload.storyline else None
    visual_emotion = payload.visualState.characterImageState
    overlay = select_persona_overlay(payload)
    tension_label = payload.suspect.tensionLevel
    numeric_tension = _normalized_tension_score(
        payload.suspect.pressure if payload.suspect.pressure is not None else payload.suspect.tensionScore
    )
    speech_style = _knowledge_speech_style(payload)
    spoken_tic = str(speech_style.get("tic") or speech_style.get("prefix") or "").strip()
    if spoken_tic and len(spoken_tic) > 24:
        spoken_tic = ""
    style_vocab = speech_style.get("vocabulary")
    if isinstance(style_vocab, list):
        safe_vocab = [str(item).strip() for item in style_vocab if 0 < len(str(item).strip()) <= 12]
    else:
        safe_vocab = []
    style_word = safe_vocab[0] if safe_vocab else ""
    name = payload.suspect.name.strip()
    role = (payload.suspect.role or "용의자").strip()
    intent = classify_dialogue_intent(payload.question.text, payload.dialogueMode)
    if visual_emotion in {"tense", "surprised", "angry", "broken"}:
        tone = visual_emotion
    if payload.suspect.emotionalState in {"tense", "surprised", "angry", "broken"}:
        tone = payload.suspect.emotionalState
    if overlay and overlay.tone:
        tone = overlay.tone
    if tension_label in {"high", "critical"} and tone == "neutral":
        tone = "tense"
    if numeric_tension is not None and numeric_tension >= 70 and tone == "neutral":
        tone = "tense"
    if act_id in {"first_break", "motive_reveal", "final_accusation"} and payload.suspect.pressureState == "normal":
        tone = "pressed"
    is_broken_state = (
        payload.suspect.pressureState == "broken"
        or tension_label == "critical"
        or payload.suspect.emotionalState in {"breakdown", "broken"}
        or (numeric_tension is not None and numeric_tension >= 70)
        or (overlay and overlay.tone == "broken")
    )

    def say(prefix: str, include_base: bool = True, suffix: str = "") -> str:
        parts = []
        if spoken_tic:
            parts.append(spoken_tic)
        if style_word and intent not in {"greeting", "unmatched"}:
            parts.append(style_word)
        parts.append(prefix)
        if include_base:
            parts.append(base)
        if suffix:
            parts.append(suffix)
        return " ".join(part.strip() for part in parts if part.strip())

    if intent == "greeting":
        return say(f"안녕하세요. 저는 {name}입니다. 사건에 대해 제가 공개적으로 말할 수 있는 범위에서만 답하겠습니다.", include_base=False)
    if intent == "unmatched":
        if is_broken_state:
            return say("알겠습니다. 지금 공개적으로 말할 수 있는 건 더 돌리지 않고 말씀드리겠습니다.", include_base=False)
        if tension_label == "high" or payload.suspect.pressureState == "pressed":
            return say("그 질문은 너무 넓습니다. 핵심만 물어보시죠.", include_base=False)
        if tension_label == "medium" or tone in {"defensive", "guarded_defensive"}:
            return say("잠깐만요. 그렇게 몰아가듯 물으시면 대답하기 어렵습니다.", include_base=False)
        return say("그렇게 넓게 물으시면 제가 뭘 더 말해야 할지 모르겠군요. 기억나는 것만 말씀드리겠습니다.", include_base=False)
    if is_broken_state:
        return say("알겠습니다.", suffix="공개된 범위에서 더 돌려 말하지 않겠습니다.")
    if intent == "evidence" and (_has_matched_contradiction_refs(payload) or tone == "evidence_shock"):
        return say("잠깐만요.", suffix="그 증거가 그렇게 이어진다면 제 말이 흔들리는 건 인정합니다.")
    overlay_directives = " ".join(overlay.styleDirectives).lower() if overlay else ""
    overlay_pressed = bool(overlay and (overlay.tone in {"pressed", "tense", "critical"} or "short" in overlay_directives or "압박" in overlay_directives))
    if (
        intent == "pressure"
        or _recent_dialogue_pressure(payload)
        or overlay_pressed
        or tone in {"pressed", "nervous", "tense", "surprised", "angry", "broken"}
        or payload.suspect.pressureState in {"pressed", "broken"}
    ):
        suffix = "방금 말씀드린 범위를 넘겨 단정하라고 하시면 곤란합니다." if _recent_dialogue_pressure(payload) else "다만 같은 말을 반복하라는 식의 질문은 불편하군요."
        return say("그만하시죠. 지금 제 대답은 달라지지 않습니다.", suffix=suffix)
    if intent == "location_time":
        if tension_label == "high" or payload.suspect.pressureState == "pressed":
            return say("아까도 말했습니다.", suffix="그 시간만큼은 분명히 기억합니다.")
        if tension_label == "medium" or tone in {"defensive", "guarded_defensive"}:
            return say("잠깐만요, 시간을 흐리려는 게 아닙니다.", suffix="그 부분은 분명히 말씀드릴 수 있어요.")
        return say("22시요?", suffix="그 부분은 분명히 말씀드릴 수 있어요.")
    if intent == "evidence":
        focus = _question_focus(payload)
        if focus == "lipstick_wine":
            if _has_matched_evidence_refs(payload):
                suffix = "립스틱 자국은 공개된 단서와 대조해 보시죠." if _question_mentions_lipstick_mark(payload) else ""
                return say("그 와인잔 이야기를 제게 돌리지 마세요. 제가 직접 확인한 건 이 정도입니다.", suffix=suffix)
            return say("립스틱이나 와인잔 같은 단서는 제 말만으로 단정할 수는 없습니다. 제가 직접 확인해 드릴 수 있는 말은 이것뿐입니다.")
        if focus == "medical":
            if _has_matched_evidence_refs(payload):
                return say("의학적으로 단정하려면 공개된 기록부터 맞춰 봐야 합니다. 제가 지금 말할 수 있는 건 여기까지입니다.", suffix="처방이나 복용 약은 공개된 의료 단서와 대조해 보세요.")
            return say("의학 쪽 단서를 묻는 거라면, 제가 공개적으로 확인할 수 있는 범위는 제한적입니다. 제가 직접 확인해 드릴 수 있는 말은 이것뿐입니다.")
        if focus == "person_relation":
            return say("다른 사람을 특정하라는 질문이라면, 제가 공개적으로 확인할 수 있는 범위는 제한적입니다. 제가 직접 확인해 드릴 수 있는 말은 이것뿐입니다.")
        return say("그 단서 얘기를 제게 돌리셔도, 제가 직접 본 것 이상은 말할 수 없습니다.")
    if tone in {"calm_defensive", "defensive"}:
        return say("솔직히 말하면,") + " 더 보탤 말은 많지 않아요."
    if overlay and overlay.voice:
        safe_voice = _safe_short_text(overlay.voice, max_length=32)
        if safe_voice:
            return say(f"{safe_voice}. 제 기억은 그래요.")
    return say("제 기억은 그래요.")


class CharacterAgent:
    def run(
        self,
        agent_input: CharacterAgentInput,
        retrieved_context: object | None = None,
    ) -> DraftCharacterReply:
        payload = agent_input.payload
        seed = render_dialogue_seed(payload)
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

        try:
            prompt = DIALOGUE_SYSTEM_PROMPT + _knowledge_prompt_context(payload, retrieved_context)
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
