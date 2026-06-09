from __future__ import annotations

from app.ai_engine.core.llm import ChainedLLM, deterministic_clip, get_llm, llm_status
from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent
from app.ai_engine.prompts.character_dialogue_builder import build_character_dialogue_prompt
from app.ai_engine.schemas.agents import CharacterAgentInput, DialogueDirectorPlan, DraftCharacterReply
from app.ai_engine.schemas.dialogue import DialogueRequest
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

        if agent_input.dialogueDirectorPlan and (
            agent_input.dialogueDirectorPlan.seedText or agent_input.dialogueDirectorPlan.functionCall
        ):
            strategy = agent_input.dialogueDirectorPlan.strategy
            if strategy in {
                "defensive_pressure",
                "deflect_unmatched",
                "small_talk_boundary",
                "deflect_irrelevant",
                "reject_false_premise",
                "challenge_player_contradiction",
                "react_to_valid_pressure",
                "ask_clarification",
                "refuse_meta_or_private",
            }:
                return draft(
                    deterministic_clip(seed, max_length=payload.style.maxLength),
                    fallback_used=False,
                    degraded=False,
                    provider_name="dialogue-director",
                )

        try:
            prompt = build_character_dialogue_prompt(
                payload,
                retrieved_context,
                agent_input.dialogueDirectorPlan,
            )
            llm = get_llm()
            text = llm.complete(prompt, seed_text=seed, max_length=payload.style.maxLength)
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
