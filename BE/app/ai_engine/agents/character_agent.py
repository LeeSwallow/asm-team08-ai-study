from __future__ import annotations

import json
import re

from app.ai_engine.core.llm import ChainedLLM, deterministic_clip, get_llm, llm_status
from app.ai_engine.core.text_normalization import normalize_text
from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent
from app.ai_engine.prompts.character_dialogue_builder import build_character_dialogue_prompt
from app.ai_engine.schemas.agents import CharacterAgentInput, DialogueDirectorPlan, DraftCharacterReply
from app.ai_engine.schemas.dialogue import DialogueRequest
from app.ai_engine.schemas.prompts import LLMChatPrompt, PromptSection
from app.ai_engine.agents.character_persona import knowledge_persona, knowledge_speech_style, select_persona_overlay
from app.ai_engine.agents.character_seed import render_dialogue_seed
from app.ai_engine.agents.character_utils import _strip_outer_dialogue_quotes


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


_DRIFT_STOPWORDS = {
    "그날",
    "사건",
    "제가",
    "저는",
    "것이",
    "것은",
    "그건",
    "네",
    "아니",
    "정말",
}


def _salient_terms(text: str) -> set[str]:
    normalized = normalize_text(text)
    terms: set[str] = set()
    for raw in normalized.replace(".", " ").replace(",", " ").split():
        token = raw.strip("…!?·:;()[]{}\"'")
        if len(token) < 2 or token in _DRIFT_STOPWORDS:
            continue
        terms.add(token)
        if len(token) >= 4:
            terms.add(token[:3])
    return terms


_REF_TERM_LABELS = {
    "ev_lipstick_glass": "와인잔 립스틱 자국",
    "ev_wine_glass": "와인잔 립스틱",
    "ev_study_entry_log": "서재 출입 기록",
    "st_choiyuna_no_wine": "와인 와인잔 립스틱",
    "st_hanseoyeon_wine_deny": "와인 와인잔",
    "neutral_unmatched": "1층 식당 회장님 서재 와인 와인잔 립스틱 기록",
    "neutral_small_talk": "1층 식당 회장님 서재 와인 와인잔 립스틱 기록",
}


def _extract_final_line(raw_text: str) -> tuple[str, bool]:
    stripped = raw_text.strip()
    if not stripped:
        return raw_text, False
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        json_like = stripped[start : end + 1]
        try:
            parsed = json.loads(json_like)
        except json.JSONDecodeError:
            match = re.search(r'"(?:finalLine|final_line|answer|line|text)"\s*:\s*"([^"]{1,500})"', json_like)
            if match:
                return match.group(1).strip(), True
            return "", True
        final_line = None
        if isinstance(parsed, dict):
            final_line = parsed.get("finalLine")
        if isinstance(final_line, str) and final_line.strip():
            return final_line.strip(), False
        if isinstance(parsed, dict):
            for key in ("final_line", "answer", "line", "text"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip(), True
            output = parsed.get("output")
            if isinstance(output, dict):
                for key in ("finalLine", "final_line", "answer", "line", "text"):
                    value = output.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip(), True
        return "", True
    return raw_text, False


def _statement_scope_text(payload: DialogueRequest, plan: DialogueDirectorPlan | None = None) -> str:
    refs = payload.allowedStatement.sourceRefs
    labels = [payload.allowedStatement.text]
    for ref in [*refs.evidenceIds, *refs.statementIds, *refs.timelineIds, *refs.contradictionIds]:
        labels.append(_REF_TERM_LABELS.get(ref, ref.replace("_", " ")))
    if plan:
        for ref in plan.focusTerms:
            labels.append(_REF_TERM_LABELS.get(ref, ref.replace("_", " ")))
        function_call = plan.functionCall or {}
        raw_args = function_call.get("arguments") if isinstance(function_call, dict) else None
        args = raw_args if isinstance(raw_args, dict) else {}
        for ref in args.get("focusTerms") or []:
            ref_text = str(ref)
            labels.append(_REF_TERM_LABELS.get(ref_text, ref_text.replace("_", " ")))
    return " ".join(labels)


def _llm_answer_drifted_from_allowed_statement(
    payload: DialogueRequest,
    text: str,
    plan: DialogueDirectorPlan | None = None,
) -> bool:
    intent = classify_dialogue_intent(payload.question.text, payload.dialogueMode)
    if intent in {"greeting", "unmatched", "small_talk"}:
        allowed_terms = _salient_terms(_statement_scope_text(payload, plan))
        if not allowed_terms:
            return False
        player_terms = _salient_terms(payload.question.text)
        generated_terms = _salient_terms(text)
        dragged_terms = generated_terms & allowed_terms - player_terms
        return bool(dragged_terms)
    # For answerable case turns, do not require lexical overlap with the authored
    # statement. The LLM may phrase pressure, hesitation, and relationship texture
    # creatively as long as downstream safety guards catch hard canon/secret drift.
    # Fallback should be reserved for provider failure, secret/storyline violations,
    # or persona/momentum failure that can be regenerated with feedback.
    return False


def _character_group(payload: DialogueRequest) -> str:
    suspect_id = payload.suspect.id
    if "hanseoyeon" in suspect_id:
        return "niece"
    if "yoonjaeho" in suspect_id:
        return "butler"
    if "parkmingyu" in suspect_id:
        return "doctor"
    if "choiyuna" in suspect_id:
        return "secretary"
    return "unknown"


def _feedback_from_voice_contract(payload: DialogueRequest, text: str) -> list[str]:
    """Return retry feedback for persona/register failures, not fact-scope style drift."""
    feedback: list[str] = []
    normalized = normalize_text(text)
    speech_style = knowledge_speech_style(payload) or {}
    avoid = speech_style.get("avoid") or speech_style.get("avoidPhrases") or []
    if isinstance(avoid, list):
        hits = [str(item) for item in avoid if str(item or "").strip() and str(item) in text]
        if hits:
            feedback.append("금지된 말투/상투어를 사용했다: " + ", ".join(hits[:4]))
    register_blob = " ".join(
        str(value)
        for value in (
            speech_style.get("register"),
            speech_style.get("addressStyle"),
            speech_style.get("formality"),
        )
        if value
    )
    group = _character_group(payload)
    formal_endings = ("습니다", "습니까", "했어요", "해요", "예요", "이에요")
    if ("반말" in register_blob or group == "niece") and any(ending in normalized for ending in formal_endings):
        feedback.append("이 인물은 반말/날 선 말투가 핵심인데 존댓말·보고서 말투가 섞였다")
    if group in {"butler", "doctor", "secretary"} and any(term in normalized for term in ("똑바로", "싫어", "잖아", "아니야")):
        feedback.append("이 인물은 감정이 흔들려도 기본 존대/직업적 거리감을 유지해야 한다")
    if len(normalized) < 8:
        feedback.append("대사가 너무 짧아 플레이어 발화에 대한 캐릭터 반응이 없다")
    if any(marker in normalized for marker in ("finalLine", "speakerIntent", "json", "출력", "규칙", "시스템")):
        feedback.append("구조화 출력/규칙 메타가 말풍선 대사에 노출됐다")
    return feedback


def _with_retry_feedback(prompt: LLMChatPrompt, feedback: list[str], attempt: int) -> LLMChatPrompt:
    if not feedback:
        return prompt
    return prompt.model_copy(
        update={
            "sections": [
                *prompt.sections,
                PromptSection(
                    title=f"CharacterAgent Regeneration Feedback #{attempt}",
                    kind="constraint",
                    content={
                        "reason": "이전 후보는 사실 스코프가 아니라 캐릭터 어투/맥락 계약을 실패했다.",
                        "feedback": feedback,
                        "instruction": "같은 FACT ANCHOR 안에서 새 finalLine을 재생성하라. 금지된 말투를 제거하고, speechStyle/sample lines/register를 우선 적용하라.",
                    },
                ),
            ]
        }
    )


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
            text = deterministic_clip(text, max_length=payload.style.maxLength)
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
                    "speechStyle": knowledge_speech_style(payload),
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
                    "basePersona": knowledge_persona(payload),
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
            base_prompt = build_character_dialogue_prompt(
                payload,
                retrieved_context,
                agent_input.dialogueDirectorPlan,
            )
            llm = get_llm()
            prompt = base_prompt
            last_text = ""
            last_feedback: list[str] = []
            repaired_structure = False
            for attempt in range(1, 4):
                raw_text = llm.complete(prompt, seed_text=seed, max_length=max(payload.style.maxLength * 3, 600))
                text, repaired_structure = _extract_final_line(raw_text)
                if repaired_structure and not text:
                    last_text = ""
                    last_feedback = ["구조화 JSON에서 finalLine을 추출하지 못했다"]
                    prompt = _with_retry_feedback(base_prompt, last_feedback, attempt)
                    continue
                last_text = text
                if _llm_answer_drifted_from_allowed_statement(payload, text, agent_input.dialogueDirectorPlan):
                    return draft(
                        deterministic_clip(seed, max_length=payload.style.maxLength),
                        fallback_used=True,
                        degraded=False,
                        blocked_reason="provider_storyline_drift_repaired",
                        provider_name=provider,
                    )
                voice_feedback = _feedback_from_voice_contract(payload, text)
                if voice_feedback and attempt < 3:
                    last_feedback = voice_feedback
                    prompt = _with_retry_feedback(base_prompt, voice_feedback, attempt)
                    continue
                break
            text = last_text
            if repaired_structure and not text:
                return draft(
                    deterministic_clip(seed, max_length=payload.style.maxLength),
                    fallback_used=True,
                    degraded=False,
                    blocked_reason="structured_output_repaired_with_seed",
                    provider_name=provider,
                )
            if last_feedback and _feedback_from_voice_contract(payload, text):
                return draft(
                    deterministic_clip(seed, max_length=payload.style.maxLength),
                    fallback_used=True,
                    degraded=False,
                    blocked_reason="persona_feedback_retry_exhausted",
                    provider_name=provider,
                )
            if _llm_answer_drifted_from_allowed_statement(payload, text, agent_input.dialogueDirectorPlan):
                return draft(
                    deterministic_clip(seed, max_length=payload.style.maxLength),
                    fallback_used=True,
                    degraded=False,
                    blocked_reason="provider_storyline_drift_repaired",
                    provider_name=provider,
                )
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
