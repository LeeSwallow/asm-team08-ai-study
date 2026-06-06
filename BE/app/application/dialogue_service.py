import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.application.case_knowledge_service import CaseKnowledgeService
from app.application.ports import AIClientPort, CaseRepositoryPort, EventRepositoryPort, SessionRepositoryPort
from app.core.errors import bad_request, not_found, service_unavailable
from app.core.leak_guard import assert_no_forbidden_refs
from app.core.observability import RequestContext
from app.domain.case_engine import (
    character_public_timeline,
    current_story_progress,
    emotional_state,
    pressure_state,
    public_speech_style,
    public_storyline,
    tension_level,
    visible_timeline,
)
from app.domain.event_processor import EventProcessor, build_visual_state
from app.domain.event_types import EventType
from app.domain.interrogation_state import build_interrogation_snapshot, transition_interrogation_state
from app.domain.models import Case, DialogueEntry, EventEntry, SessionState
from app.domain.rule_engine import RuleEngine
from app.domain.text_matcher import evidence_is_mentioned
from app.domain.turn_interpreter import interpret_turn

logger = logging.getLogger(__name__)


@dataclass
class DialogueMatch:
    dialogue_mode: str
    question: Any | None = None
    consumed_question: bool = False
    allowed_statement: dict[str, Any] | None = None
    fallback_answer: str | None = None


@dataclass
class DialogueService:
    case_repo: CaseRepositoryPort
    session_repo: SessionRepositoryPort
    event_repo: EventRepositoryPort
    rule_engine: RuleEngine
    ai_client: AIClientPort
    knowledge_service: CaseKnowledgeService = field(default_factory=CaseKnowledgeService)

    async def submit(
        self,
        session_id: str,
        suspect_id: str,
        message: str,
        question_id: str | None,
        request_context: RequestContext,
    ) -> dict:
        started_at = time.perf_counter()
        session, case = self._load_session_and_case(session_id)
        previous_remaining_questions = session.remainingQuestions
        match = self._classify_dialogue(case, session, suspect_id, message, question_id)
        suspect = next(item for item in case.suspects if item.characterId == suspect_id)

        if match.consumed_question:
            question = match.question
            if question is None:
                raise bad_request("DIALOGUE_QUESTION_NOT_MATCHED")
            try:
                question_result = self.rule_engine.answer_question(session, case, question.questionId)
            except ValueError as exc:
                raise bad_request(str(exc))
            fallback_answer = question_result["answer"]
            allowed_statement = self._allowed_statement_for_question(case, question, fallback_answer)
        else:
            session.selectedSuspectId = suspect_id
            session.newlyUnlockedIds = []
            question_result = {"newlyUnlockedIds": [], "repeated": False, "askCount": 0}
            fallback_answer = match.fallback_answer or self._fallback_answer_for_intent(match.dialogue_mode, suspect, message)
            allowed_statement = match.allowed_statement or {
                "id": f"neutral_{match.dialogue_mode}",
                "text": self._neutral_allowed_statement(case, suspect),
                "sourceRefs": {"statementIds": [], "timelineIds": [], "evidenceIds": []},
            }

        story_progress = current_story_progress(session, case)
        allowed_event_policy = self._allowed_event_policy(case, session, suspect.characterId, match, allowed_statement, message)
        turn_interpretation = interpret_turn(
            case=case,
            session=session,
            suspect_id=suspect.characterId,
            player_message=message,
            dialogue_mode=match.dialogue_mode,
        )
        self._merge_turn_interpretation(allowed_event_policy, turn_interpretation.model_dump())
        contradiction_result = self._judge_turn_contradiction(
            session=session,
            case=case,
            suspect_id=suspect.characterId,
            message=message,
            dialogue_mode=match.dialogue_mode,
            allowed_event_policy=allowed_event_policy,
            turn_interpretation=turn_interpretation.model_dump(),
        )
        question_unlocked_ids = list(question_result["newlyUnlockedIds"])
        contradiction_unlocked_ids = list((contradiction_result or {}).get("unlockedIds") or [])
        combined_unlocked_ids = self._dedupe([*question_unlocked_ids, *contradiction_unlocked_ids])
        interrogation_transition = transition_interrogation_state(
            case=case,
            session=session,
            suspect_id=suspect.characterId,
            dialogue_mode=match.dialogue_mode,
            consumed_question=match.consumed_question,
            player_message=message,
            allowed_statement=allowed_statement,
            allowed_event_policy=allowed_event_policy,
        )
        self._merge_contradiction_result_into_transition(contradiction_result, interrogation_transition)
        self._augment_allowed_statement_for_transition(case, allowed_statement, interrogation_transition.model_dump())
        decisive_pressure_hit = interrogation_transition.decisive_evidence
        interrogation_snapshot = build_interrogation_snapshot(session, suspect.characterId, case)
        visual_state = build_visual_state(session, case, suspect.characterId)
        character_knowledge_pack = self.knowledge_service.character_pack(case, session, suspect.characterId)
        ai_payload = {
            "requestId": request_context.request_id,
            "correlationId": request_context.request_id,
            "caseId": case.caseId,
            "sessionId": session.sessionId,
            "currentActId": story_progress["currentActId"],
            "currentObjective": story_progress["currentObjective"],
            "dialogueMode": match.dialogue_mode,
            "intent": match.dialogue_mode,
            "consumedQuestion": match.consumed_question,
            "suspect": {
                "id": suspect.characterId,
                "name": suspect.name,
                "role": suspect.role,
                "publicProfile": suspect.publicProfile,
                "speechStyle": public_speech_style(suspect.characterId) | (suspect.speechStyle or {}),
                "publicTimeline": character_public_timeline(case, session, suspect.characterId),
                "pressure": session.pressureBySuspect.get(suspect.characterId, 0),
                "pressureState": interrogation_snapshot["pressureState"],
                "tensionLevel": interrogation_snapshot["tensionLevel"],
                "tensionScore": session.pressureBySuspect.get(suspect.characterId, 0),
                "emotionalState": interrogation_snapshot["emotionalState"],
                "expression": visual_state["expression"],
            },
            "message": message,
            "question": self._ai_question_payload(match, message),
            "allowedStatement": allowed_statement,
            "characterKnowledgePack": character_knowledge_pack,
            "storyline": self._storyline_context(case, session, story_progress),
            "characterTimeline": self._character_timeline_context(case, session, suspect.characterId),
            "visibleFacts": self._visible_facts(case, session),
            "dialogueHistorySummary": self._dialogue_history_summary(session),
            "visualState": visual_state,
            "style": {
                "tone": self._dialogue_tone(interrogation_transition.model_dump()),
                "maxLength": 220,
            },
            "revealAllowed": False,
            "allowedEventPolicy": allowed_event_policy,
            "turnInterpretation": turn_interpretation.model_dump(),
            "interrogationState": interrogation_snapshot,
            "interrogationTransition": interrogation_transition.model_dump(),
        }
        self._assert_public_surface(ai_payload, "ai_payload")
        ai_result = await self.ai_client.dialogue_response_info(ai_payload, fallback_answer)
        ai_result = self._safe_ai_result_or_fallback(
            ai_result=ai_result,
            fallback_answer=fallback_answer,
            request_context=request_context,
            session=session,
            case=case,
            suspect_id=suspect.characterId,
            started_at=started_at,
        )
        answer = self._polish_answer(ai_result["answer"], suspect.name)
        answer = self._differentiate_repeated_reply(session, suspect.characterId, match.dialogue_mode, question_result, answer)
        question_id_for_log = match.question.questionId if match.question is not None else None
        npc_entry = self._append_dialogue_entries(session, suspect.characterId, question_id_for_log, suspect.name, message, answer)
        session.newlyUnlockedIds = combined_unlocked_ids

        processor = EventProcessor(start_index=self.event_repo.next_index(session.sessionId))
        ai_proposed_events = list(ai_result["proposedEvents"])
        be_proposed_events = self._contradiction_candidate_events(case, session, message, suspect.characterId, match.dialogue_mode)
        state_proposed_events = [
            *self._contradiction_note_events_from_result(contradiction_result),
            *self._contradiction_note_events_from_transition(interrogation_transition.model_dump()),
        ]
        proposed_events = [
            *ai_proposed_events,
            *state_proposed_events,
            *be_proposed_events,
        ]
        applied_events = processor.process_dialogue_events(
            session=session,
            case=case,
            suspect_id=suspect.characterId,
            player_message=message,
            answer=answer,
            proposed_events=proposed_events,
            allow_implicit_note=False,
            allowed_event_types=set(allowed_event_policy["allowedTypes"]),
            allowed_event_policy=allowed_event_policy,
        )
        applied_events.extend(
            self._deterministic_contradiction_events(
                session=session,
                case=case,
                suspect_id=suspect.characterId,
                contradiction_result=contradiction_result,
                start_index=self.event_repo.next_index(session.sessionId) + len(applied_events),
            )
        )
        self._assert_public_surface([event.model_dump(mode="json") for event in applied_events], "applied_events")
        self.event_repo.append_many(applied_events)
        public_safety = self._public_safety(ai_result["safety"])
        ai_runtime_diagnostics = ai_result.get("runtimeDiagnostics") or {}
        dialogue_result = {
            "messageId": npc_entry.id,
            "suspectId": suspect.characterId,
            "dialogueMode": match.dialogue_mode,
            "intent": match.dialogue_mode,
            "matchedQuestionId": question_id_for_log,
            "matchedIntentId": question_id_for_log or match.dialogue_mode,
            "repeated": question_result["repeated"],
            "askCount": question_result["askCount"],
            "remainingQuestions": session.remainingQuestions,
            "previousRemainingQuestions": previous_remaining_questions,
            "remainingQuestionsDelta": session.remainingQuestions - previous_remaining_questions,
            "unlockedIds": question_result["newlyUnlockedIds"],
            "consumedQuestion": match.consumed_question,
            "fallbackUsed": ai_result["fallbackUsed"],
            "provider": ai_result["provider"],
            "model": ai_result.get("model"),
            "safety": public_safety,
            "matchedRefs": self._matched_refs(allowed_statement, allowed_event_policy),
            "diagnosticReason": self._diagnostic_reason(match, allowed_event_policy),
            "aiIntent": ai_result.get("intent"),
            "aiDialogueMode": ai_result.get("dialogueMode"),
            "emotionalState": emotional_state(session.pressureBySuspect.get(suspect.characterId, 0)),
            "tensionLevel": tension_level(session.pressureBySuspect.get(suspect.characterId, 0)),
            "decisiveEvidencePressure": decisive_pressure_hit,
            "turnInterpretation": turn_interpretation.model_dump(),
            "interrogationTransition": interrogation_transition.model_dump(),
            "contradictionResult": contradiction_result,
            "aiRuntimeDiagnostics": ai_runtime_diagnostics,
            "proposedEventsCount": len(ai_proposed_events),
            "beProposedEventsCount": len(be_proposed_events),
            "stateProposedEventsCount": len(state_proposed_events),
            "totalProposedEventsCount": len(proposed_events),
            "appliedEventsCount": len(applied_events),
            "appliedEvents": [event.model_dump(mode="json") for event in applied_events],
        }
        runtime_diagnostics = {
            "intent": match.dialogue_mode,
            "dialogueMode": match.dialogue_mode,
            "matchedQuestionId": question_id_for_log,
            "matchedRefs": self._matched_refs(allowed_statement, allowed_event_policy),
            "provider": ai_result["provider"],
            "model": ai_result.get("model"),
            "safety": public_safety,
            "aiIntent": ai_result.get("intent"),
            "aiDialogueMode": ai_result.get("dialogueMode"),
            "proposedEventsCount": len(ai_proposed_events),
            "beProposedEventsCount": len(be_proposed_events),
            "stateProposedEventsCount": len(state_proposed_events),
            "totalProposedEventsCount": len(proposed_events),
            "appliedEventsCount": len(applied_events),
            "reason": self._diagnostic_reason(match, allowed_event_policy),
            "turnInterpretation": turn_interpretation.model_dump(),
            "contradictionResult": contradiction_result,
            "aiRuntimeDiagnostics": ai_runtime_diagnostics,
        }
        session.lastDialogueResult = self._last_dialogue_summary(dialogue_result)
        session.lastRuntimeDiagnostics = self._last_runtime_diagnostics(runtime_diagnostics)
        self._assert_public_surface(
            {
                "lastDialogueResult": session.lastDialogueResult,
                "lastRuntimeDiagnostics": session.lastRuntimeDiagnostics,
            },
            "last_dialogue_session_state",
        )
        self.session_repo.save(session)

        if ai_result["fallbackUsed"]:
            self._log_ai_fallback(request_context, session, case, suspect.characterId, started_at)
        self._log_dialogue(
            request_context,
            session,
            case,
            suspect.characterId,
            started_at,
            ai_result["fallbackUsed"],
            match.dialogue_mode,
        )
        return {
            "answer": answer,
            "dialogueResult": dialogue_result,
            "questionResult": {
                "questionId": question_id_for_log,
                "repeated": question_result["repeated"],
                "askCount": question_result["askCount"],
                "remainingQuestions": session.remainingQuestions,
                "unlockedIds": question_result["newlyUnlockedIds"],
            } if match.consumed_question else None,
            "fallbackUsed": ai_result["fallbackUsed"],
            "provider": ai_result["provider"],
            "model": ai_result.get("model"),
            "safety": public_safety,
            "runtimeDiagnostics": runtime_diagnostics,
            "contradictionResult": contradiction_result,
            "proposedEventsCount": len(ai_proposed_events),
            "beProposedEventsCount": len(be_proposed_events),
            "stateProposedEventsCount": len(state_proposed_events),
            "totalProposedEventsCount": len(proposed_events),
            "appliedEventsCount": len(applied_events),
            "proposedEventsApplied": [event.id for event in applied_events],
            "visualState": build_visual_state(session, case, suspect.characterId),
            "session": session,
            "case": case,
        }

    def _safe_ai_result_or_fallback(
        self,
        *,
        ai_result: dict[str, Any],
        fallback_answer: str,
        request_context: RequestContext,
        session: SessionState,
        case: Case,
        suspect_id: str,
        started_at: float,
    ) -> dict[str, Any]:
        """Keep the deterministic BE turn authoritative when AI is degraded or unsafe.

        A provider/policy failure should not bounce back to FE as a repeated API failure:
        the turn has already been classified and, for matched questions, the 12-turn
        budget has already been consumed by RuleEngine. Return a public BE fallback,
        mark diagnostics honestly, and continue saving the updated session.
        """
        reason = str(ai_result.get("degradedReason") or "ai_service_unavailable")
        safety = dict(ai_result.get("safety") or {})
        fallback_used = bool(ai_result.get("fallbackUsed"))
        degraded = bool(ai_result.get("degraded"))
        repair_reason: str | None = None

        try:
            assert_no_forbidden_refs(
                {
                    "answer": ai_result.get("answer"),
                    "proposedEvents": ai_result.get("proposedEvents") or [],
                },
                surface="ai_result",
            )
        except ValueError:
            repair_reason = "public_safety_repair"
            logger.warning(
                "ai result replaced with backend fallback after public safety repair",
                extra={
                    "service": "backend",
                    "request_id": request_context.request_id,
                    "session_id": session.sessionId,
                    "case_id": case.caseId,
                    "route": request_context.route,
                    "suspect_id": suspect_id,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "fallback_used": True,
                    "reason": repair_reason,
                },
            )

        if degraded:
            logger.warning(
                "ai degraded; continuing dialogue turn with backend fallback",
                extra={
                    "service": "backend",
                    "request_id": request_context.request_id,
                    "session_id": session.sessionId,
                    "case_id": case.caseId,
                    "route": request_context.route,
                    "suspect_id": suspect_id,
                    "duration_ms": int((time.perf_counter() - started_at) * 1000),
                    "fallback_used": True,
                    "reason": reason,
                },
            )

        if degraded or repair_reason:
            safety.update(
                {
                    "status": "degraded" if degraded and not repair_reason else "repaired",
                    "fallbackUsed": True,
                    "degraded": degraded,
                    "repaired": bool(repair_reason),
                    "blockedReason": repair_reason or reason,
                }
            )
            return {
                **ai_result,
                "answer": fallback_answer,
                "proposedEvents": [],
                "fallbackUsed": True,
                "degraded": degraded,
                "provider": ai_result.get("provider") or "backend-rule-engine",
                "model": ai_result.get("model"),
                "safety": safety,
            }

        return {
            **ai_result,
            "answer": ai_result.get("answer") or fallback_answer,
            "proposedEvents": ai_result.get("proposedEvents") or [],
            "fallbackUsed": fallback_used,
            "degraded": degraded,
            "safety": safety or {"status": "checked", "fallbackUsed": fallback_used},
        }

    def _assert_public_surface(self, value: Any, surface: str) -> None:
        try:
            assert_no_forbidden_refs(value, surface=surface)
        except ValueError as exc:
            logger.warning("forbidden ref rejected", extra={"service": "backend", "surface": surface, "fallback_used": False})
            raise service_unavailable(
                "AI_RESPONSE_FORBIDDEN_REF",
                {"surface": surface, "fallbackUsed": False, "degradedReason": str(exc).split(":", 2)[0]},
            )

    def _load_session_and_case(self, session_id: str) -> tuple[SessionState, Case]:
        session = self.session_repo.get(session_id)
        if session is None:
            raise not_found("Session not found")
        case = self.case_repo.get_case(session.caseId)
        if case is None:
            raise not_found("Case not found")
        return session, case

    def _public_safety(self, safety: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": safety.get("status", "checked"),
            "fallbackUsed": bool(safety.get("fallbackUsed", False)),
            "degraded": bool(safety.get("degraded", False)),
            "repaired": bool(safety.get("repaired", False)),
            "blocked": bool(safety.get("blockedReason")),
            "provider": safety.get("provider"),
            "model": safety.get("model"),
        }

    def _last_dialogue_summary(self, dialogue_result: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "messageId",
            "suspectId",
            "dialogueMode",
            "intent",
            "matchedQuestionId",
            "matchedIntentId",
            "repeated",
            "askCount",
            "remainingQuestions",
            "previousRemainingQuestions",
            "remainingQuestionsDelta",
            "consumedQuestion",
            "fallbackUsed",
            "provider",
            "model",
            "safety",
            "matchedRefs",
            "diagnosticReason",
            "aiIntent",
            "aiDialogueMode",
            "emotionalState",
            "tensionLevel",
            "contradictionResult",
            "proposedEventsCount",
            "beProposedEventsCount",
            "stateProposedEventsCount",
            "totalProposedEventsCount",
            "appliedEventsCount",
        )
        return {key: dialogue_result.get(key) for key in keys}

    def _last_runtime_diagnostics(self, runtime_diagnostics: dict[str, Any]) -> dict[str, Any]:
        keys = (
            "intent",
            "dialogueMode",
            "matchedQuestionId",
            "matchedRefs",
            "provider",
            "model",
            "safety",
            "aiIntent",
            "aiDialogueMode",
            "proposedEventsCount",
            "beProposedEventsCount",
            "stateProposedEventsCount",
            "totalProposedEventsCount",
            "appliedEventsCount",
            "reason",
            "contradictionResult",
        )
        return {key: runtime_diagnostics.get(key) for key in keys}

    def _judge_turn_contradiction(
        self,
        *,
        session: SessionState,
        case: Case,
        suspect_id: str,
        message: str,
        dialogue_mode: str,
        allowed_event_policy: dict[str, Any],
        turn_interpretation: dict[str, Any],
    ) -> dict[str, Any] | None:
        if dialogue_mode in {"small_talk", "unmatched"}:
            return None
        related_contradiction_ids = list(allowed_event_policy.get("relatedContradictionIds") or [])
        if not related_contradiction_ids:
            return None
        statement_ids = list(allowed_event_policy.get("relatedStatementIds") or [])
        evidence_ids = list(allowed_event_policy.get("relatedEvidenceIds") or [])
        contradiction_terms = ("모순", "안 맞", "안맞", "거짓", "이상", "충돌", "입증", "증명")
        normalized = self._normalize_text(message)
        explicit_challenge = any(term in normalized for term in contradiction_terms)
        if not evidence_ids and not explicit_challenge:
            return None
        result = self.rule_engine.judge_contradiction(
            session,
            case,
            statement_ids=statement_ids,
            evidence_ids=evidence_ids,
            suspect_id=suspect_id,
        )
        result["source"] = "dialogue"
        result["suspectId"] = suspect_id
        result["mentionedEvidenceIds"] = list(turn_interpretation.get("mentionedEvidenceIds") or [])
        result["mentionedStatementIds"] = list(turn_interpretation.get("mentionedStatementIds") or [])
        return result

    def _contradiction_note_events_from_result(self, result: dict[str, Any] | None) -> list[dict]:
        if not result or result.get("verdict") != "correct" or result.get("newlyDiscovered") is not True:
            return []
        contradiction_id = result.get("contradictionId")
        if not contradiction_id:
            return []
        return [
            {
                "type": EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value,
                "payload": {
                    "contradictionId": contradiction_id,
                    "statementIds": list(result.get("statementIds") or []),
                    "evidenceIds": list(result.get("evidenceIds") or []),
                },
            }
        ]

    def _merge_contradiction_result_into_transition(self, result: dict[str, Any] | None, transition) -> None:
        if not result or result.get("verdict") != "correct" or not result.get("contradictionId"):
            return
        contradiction_id = str(result["contradictionId"])
        if contradiction_id not in transition.contradiction_ids:
            transition.contradiction_ids.append(contradiction_id)
        if result.get("newlyDiscovered") is True and contradiction_id not in transition.newly_discovered_contradiction_ids:
            transition.newly_discovered_contradiction_ids.append(contradiction_id)
        transition.decisive_evidence = True
        transition.reason = "dialogue_rule_engine_validated"

    def _deterministic_contradiction_events(
        self,
        *,
        session: SessionState,
        case: Case,
        suspect_id: str,
        contradiction_result: dict[str, Any] | None,
        start_index: int,
    ) -> list[EventEntry]:
        if not contradiction_result:
            return []
        if contradiction_result.get("verdict") != "correct" or contradiction_result.get("newlyDiscovered") is not True:
            return []
        pressure = session.pressureBySuspect.get(suspect_id, 0)
        return [
            EventEntry(
                id=f"evt_{start_index:06d}",
                sessionId=session.sessionId,
                caseId=case.caseId,
                type=EventType.TENSION_CHANGED.value,
                payload={
                    "suspectId": suspect_id,
                    "pressure": pressure,
                    "pressureState": pressure_state(pressure),
                    "tensionLevel": tension_level(pressure),
                    "tensionScore": pressure,
                    "source": "dialogue_rule_engine",
                    "contradictionId": contradiction_result.get("contradictionId"),
                },
            )
        ]

    def _classify_dialogue(
        self,
        case: Case,
        session: SessionState,
        suspect_id: str,
        message: str,
        question_id: str | None,
    ) -> DialogueMatch:
        suspect_ids = {suspect.characterId for suspect in case.suspects}
        if suspect_id not in suspect_ids:
            raise bad_request("SUSPECT_NOT_FOUND")
        candidates = [
            item
            for item in case.questions
            if item.characterId == suspect_id and item.questionId in session.unlockedQuestionIds
        ]
        if question_id:
            question = next((item for item in candidates if item.questionId == question_id), None)
            if question is None:
                raise bad_request("DIALOGUE_QUESTION_NOT_MATCHED")
            return DialogueMatch(dialogue_mode="case_question", question=question, consumed_question=True)

        normalized_message = self._normalize_text(message)
        if self._is_small_talk(normalized_message):
            return DialogueMatch(dialogue_mode="small_talk", fallback_answer=self._fallback_answer_for_intent("small_talk", self._suspect(case, suspect_id), message))

        if self._is_meta_pressure_followup(session, suspect_id, normalized_message):
            return DialogueMatch(
                dialogue_mode="pressure_followup",
                allowed_statement=self._recent_context_statement(case, session, suspect_id, message),
                fallback_answer=self._fallback_answer_for_intent("pressure_followup", self._suspect(case, suspect_id), message),
            )

        if self._is_repeat_detail_followup(session, suspect_id, normalized_message):
            return DialogueMatch(
                dialogue_mode="pressure_followup",
                allowed_statement=self._recent_context_statement(case, session, suspect_id, message),
                fallback_answer=self._fallback_answer_for_intent("pressure_followup", self._suspect(case, suspect_id), message),
            )

        if self._mentions_non_active_character_only(case, suspect_id, normalized_message):
            return DialogueMatch(
                dialogue_mode="unmatched",
                fallback_answer=self._fallback_answer_for_intent("unmatched", self._suspect(case, suspect_id), message),
            )

        exact = next((item for item in candidates if self._normalize_text(item.text) == normalized_message), None)
        if exact:
            return DialogueMatch(dialogue_mode="case_question", question=exact, consumed_question=True)

        evidence_context = self._visible_evidence_context(case, session, normalized_message)
        if evidence_context is not None and self._looks_like_contradiction_challenge(normalized_message):
            return DialogueMatch(
                dialogue_mode="evidence_question",
                allowed_statement=evidence_context,
                fallback_answer=self._fallback_answer_for_intent("evidence_question", self._suspect(case, suspect_id), message),
            )

        broad_alibi = self._broad_time_alibi_question(candidates, normalized_message)
        if broad_alibi is not None:
            return DialogueMatch(dialogue_mode="timeline_question", question=broad_alibi, consumed_question=True)

        scored = sorted(
            ((self._question_match_score(case, item, normalized_message), item) for item in candidates),
            key=lambda pair: pair[0],
            reverse=True,
        )
        if scored and scored[0][0] >= 2:
            mode = "evidence_question" if self._looks_like_evidence_question(case, session, normalized_message) else "case_question"
            return DialogueMatch(dialogue_mode=mode, question=scored[0][1], consumed_question=True)

        if evidence_context is not None:
            return DialogueMatch(
                dialogue_mode="evidence_question",
                allowed_statement=evidence_context,
                fallback_answer=self._fallback_answer_for_intent("evidence_question", self._suspect(case, suspect_id), message),
            )
        if self._looks_like_evidence_question(case, session, normalized_message):
            return DialogueMatch(
                dialogue_mode="evidence_question",
                fallback_answer=self._fallback_answer_for_intent("evidence_question", self._suspect(case, suspect_id), message),
            )

        return DialogueMatch(
            dialogue_mode="unmatched",
            fallback_answer=self._fallback_answer_for_intent("unmatched", self._suspect(case, suspect_id), message),
        )

    def _suspect(self, case: Case, suspect_id: str):
        return next(item for item in case.suspects if item.characterId == suspect_id)

    def _mentions_non_active_character_only(self, case: Case, suspect_id: str, normalized_message: str) -> bool:
        compact = normalized_message.replace(" ", "")
        active = self._suspect(case, suspect_id)
        active_names = {self._normalize_text(active.name).replace(" ", ""), suspect_id.lower()}
        active_mentioned = any(name and name in compact for name in active_names)
        victim_name = self._normalize_text(case.victimName).replace(" ", "")
        if victim_name and victim_name in compact:
            return not active_mentioned
        for suspect in case.suspects:
            if suspect.characterId == suspect_id:
                continue
            names = {self._normalize_text(suspect.name).replace(" ", ""), suspect.characterId.lower()}
            if any(name and name in compact for name in names):
                return not active_mentioned
        return False

    def _ai_question_payload(self, match: DialogueMatch, message: str) -> dict[str, str]:
        if match.question is not None:
            return {"id": match.question.questionId, "text": match.question.text}
        return {"id": f"player_{match.dialogue_mode}", "text": message}

    def _append_dialogue_entries(
        self,
        session: SessionState,
        suspect_id: str,
        question_id: str | None,
        suspect_name: str,
        player_message: str,
        answer: str,
    ) -> DialogueEntry:
        player_entry = DialogueEntry(
            id=f"dlg_{uuid4().hex}",
            suspectId=suspect_id,
            questionId=question_id,
            speaker="player",
            text=player_message,
        )
        npc_entry = DialogueEntry(
            id=f"dlg_{uuid4().hex}",
            suspectId=suspect_id,
            questionId=question_id,
            speaker=suspect_name,
            text=answer,
        )
        session.dialogueLog.extend([player_entry, npc_entry])
        return npc_entry

    def _polish_answer(self, answer: str, suspect_name: str) -> str:
        polished = answer.strip()
        polished = self._strip_dialogue_quotes(polished)
        polished = re.sub(r"\([^)]{1,50}\)|（[^）]{1,50}）|\[[^\]]{1,50}\]", "", polished)
        role_artifacts = (
            "조카로서 조심스럽게 말씀드리면",
            "조카로서 말씀드리자면",
            f"{suspect_name}로서 말씀드리자면",
        )
        for artifact in role_artifacts:
            polished = polished.replace(f"{artifact} ", "")
            polished = polished.replace(artifact, "")
        replacements = {
            "것이오": "겁니다",
            "하오": "해요",
            "하소": "하세요",
            "했소": "했습니다",
            "계셨지": "계셨습니다",
            "걷고 계셨지": "악화되고 있었습니다",
            "그대": "형사님",
        }
        for old, new in replacements.items():
            polished = polished.replace(old, new)
        polished = re.sub(r"(?<![가-힣])소([.?!,]|$)", r"습니다\1", polished)
        polished = self._strip_dialogue_quotes(polished)
        polished = re.sub(r"\s{2,}", " ", polished).strip()
        return polished or answer

    def _strip_dialogue_quotes(self, text: str) -> str:
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

    def _differentiate_repeated_reply(
        self,
        session: SessionState,
        suspect_id: str,
        dialogue_mode: str,
        question_result: dict[str, Any],
        answer: str,
    ) -> str:
        prior_answers = [
            entry.text
            for entry in session.dialogueLog[-12:]
            if entry.suspectId == suspect_id and entry.speaker != "player"
        ]
        if question_result.get("repeated") is True:
            prefixes = (
                "다시 정리하면,",
                "앞서 말한 내용과 같지만,",
                "한 번 더 확인하자면,",
            )
            ask_count = int(question_result.get("askCount") or 2)
            return f"{prefixes[(ask_count - 2) % len(prefixes)]} {answer}"
        evidence_template = "제 말이 흔들린다는 건 알겠습니다"
        if dialogue_mode == "evidence_question" and evidence_template in answer and any(evidence_template in item for item in prior_answers):
            return answer.replace(
                "그래도 그걸 곧바로 인정하라는 건 무리예요. 제가 설명해야 할 부분이 있다는 것까지만 말하겠습니다.",
                "하지만 그 기록 하나로 제 행동 전체가 단정되는 건 받아들일 수 없어요. 확인할 수 있는 부분부터 다시 짚겠습니다.",
            )
        if answer not in prior_answers:
            return answer
        variants = {
            "unmatched": (
                "그 질문은 지금 제게 확인할 수 있는 범위를 벗어납니다.",
                "그건 제가 바로 답할 수 있는 질문이 아닙니다.",
                "그 부분은 제 진술과 직접 연결해서 물어봐 주세요.",
            ),
            "small_talk": (
                "인사보다 사건 이야기를 하시죠.",
                "짧게 하겠습니다. 사건과 관련된 걸 물어보세요.",
                "지금은 잡담할 상황이 아닙니다.",
            ),
        }
        options = variants.get(dialogue_mode)
        if not options:
            options = (
                "표현을 바꾸면 이렇습니다.",
                "같은 취지로 말하겠습니다.",
                "다시 말하자면 이렇습니다.",
            )
        repeat_count = prior_answers.count(answer)
        return f"{options[(repeat_count - 1) % len(options)]} {answer}"

    def _allowed_statement_for_question(self, case: Case, question, fallback_answer: str) -> dict[str, Any]:
        for statement_id in question.unlocksStatementIds:
            statement = next((item for item in case.statements if item.statementId == statement_id), None)
            if statement is not None:
                return {
                    "id": statement.statementId,
                    "text": statement.text,
                    "sourceRefs": {
                        "statementIds": [statement.statementId],
                        "timelineIds": self._timeline_ids_for_source(case, statement.statementId),
                        "evidenceIds": [],
                    },
                }
        matching_statement = next(
            (
                item
                for item in case.statements
                if item.characterId == question.characterId and item.questionText == question.text
            ),
            None,
        )
        if matching_statement is not None:
            return {
                "id": matching_statement.statementId,
                "text": matching_statement.text,
                "sourceRefs": {
                    "statementIds": [matching_statement.statementId],
                    "timelineIds": self._timeline_ids_for_source(case, matching_statement.statementId),
                    "evidenceIds": [],
                },
            }
        return {
            "id": f"answer_{question.questionId}",
            "text": fallback_answer,
            "sourceRefs": {"statementIds": [], "timelineIds": [], "evidenceIds": []},
        }

    def _question_match_score(self, case: Case, question, normalized_message: str) -> int:
        compact = normalized_message.replace(" ", "")
        question_text = self._normalize_text(question.text)
        question_compact = question_text.replace(" ", "")

        score = 0
        if question.questionId.endswith("alibi") and (
            "알리바이" in compact
            or (
                self._mentions_time(normalized_message)
                and any(term in compact for term in ("어디", "방", "있었", "뭐했", "무엇", "무얼", "동선", "행적"))
            )
        ):
            score += 4
        if question_compact and question_compact in compact:
            score += 4
        if any(term in compact for term in ("약", "복용", "처방", "수면제")) and any(
            term in question_compact for term in ("약", "복용", "처방", "수면제")
        ):
            score += 3

        search_texts = [question.text]
        search_texts.extend(
            statement.text
            for statement in case.statements
            if statement.characterId == question.characterId and statement.questionText == question.text
        )
        search_texts.extend(
            getattr(statement, "location", "")
            for statement in case.statements
            if statement.characterId == question.characterId and statement.questionText == question.text
        )
        search_texts.extend(
            f"{evidence.name} {evidence.description} {evidence.foundAt} {evidence.timeWindow or ''}"
            for evidence in case.evidence
            if evidence.evidenceId in question.unlocksEvidenceIds
        )
        search_texts.extend(
            f"{record.name} {record.description} {record.timeWindow or ''}"
            for record in case.records
            if record.recordId in question.unlocksRecordIds
        )
        if any(term in compact for term in ("립스틱", "와인잔", "와인")) and any(
            term in self._normalize_text(" ".join(search_texts)).replace(" ", "")
            for term in ("립스틱", "와인잔", "와인")
        ):
            score += 3
        overlap = max(
            (self._overlap_score(normalized_message, self._normalize_text(text)) for text in search_texts if text),
            default=0,
        )
        return score + overlap

    def _is_small_talk(self, normalized_message: str) -> bool:
        compact = normalized_message.replace(" ", "")
        greeting_terms = ("안녕", "반갑", "처음뵙", "고맙", "감사", "실례")
        case_terms = ("22", "사건", "피해자", "서재", "상속", "유언", "와인", "립스틱", "약", "복용", "증거", "기록", "알리바이", "복도", "정전")
        return any(term in compact for term in greeting_terms) and not any(term in compact for term in case_terms)

    def _broad_time_alibi_question(self, candidates: list, normalized_message: str):
        compact = normalized_message.replace(" ", "")
        if not self._mentions_time(normalized_message):
            return None
        if not any(term in compact for term in ("뭐했", "무엇", "무얼", "어디", "있었", "동선", "행적", "알리바이")):
            return None
        if not (
            re.search(r"\d{1,2}시?(부터|에서|~|-)?\d{1,2}시?(까지|사이|전후)?", compact)
            or any(term in compact for term in ("그시간", "그때", "밤10시", "열시", "22시까지"))
        ):
            return None
        return next((item for item in candidates if item.questionId.endswith("alibi")), None)

    def _is_meta_pressure_followup(self, session: SessionState, suspect_id: str, normalized_message: str) -> bool:
        compact = normalized_message.replace(" ", "")
        if not any(entry.suspectId == suspect_id for entry in session.dialogueLog[-4:]):
            return False
        return any(
            term in compact
            for term in (
                "왜답변",
                "왜대답",
                "답변못",
                "대답못",
                "말이돼",
                "말이된다고",
                "회피",
                "피하지",
                "납득",
                "이상하",
                "말장난",
                "그게답",
            )
        )

    def _is_repeat_detail_followup(self, session: SessionState, suspect_id: str, normalized_message: str) -> bool:
        compact = normalized_message.replace(" ", "")
        if not any(entry.suspectId == suspect_id for entry in session.dialogueLog[-4:]):
            return False
        if not any(term in compact for term in ("방금", "아까", "다시", "자세히", "구체적", "설명")):
            return False
        return any(term in compact for term in ("22시", "열시", "그시간", "그때", "행적", "동선", "어디", "알리바이"))

    def _recent_context_statement(self, case: Case, session: SessionState, suspect_id: str, message: str) -> dict[str, Any]:
        alibi_statement = next(
            (
                item
                for item in case.statements
                if item.characterId == suspect_id and item.statementId in session.unlockedStatementIds and item.timeWindow
            ),
            None,
        )
        statement_ids = [alibi_statement.statementId] if alibi_statement is not None else []
        timeline_ids = self._timeline_ids_for_source(case, alibi_statement.statementId) if alibi_statement is not None else []
        compact = self._normalize_text(message).replace(" ", "")
        if any(term in compact for term in ("말이돼", "말이된다고", "납득", "이상하")):
            context_text = "말이 안 된다고 해도 제가 이미 말씀드린 내용은 같습니다."
        else:
            context_text = "답이 부족했다면 회피하려는 뜻은 아닙니다. 기억나는 범위를 말하고 있습니다."
        if alibi_statement is not None:
            context_text = f"{context_text} {alibi_statement.text}".strip()
        return {
            "id": f"recent_pressure_{suspect_id}",
            "text": context_text or f"플레이어가 직전 답변을 압박하고 있다: {message}",
            "sourceRefs": {"statementIds": statement_ids, "timelineIds": timeline_ids, "evidenceIds": []},
        }

    def _looks_like_evidence_question(self, case: Case, session: SessionState, normalized_message: str) -> bool:
        if self._visible_evidence_context(case, session, normalized_message) is not None:
            return True
        compact = normalized_message.replace(" ", "")
        return any(term in compact for term in ("증거", "단서", "기록", "흔적", "복용", "약", "립스틱", "와인잔", "와인"))

    def _looks_like_contradiction_challenge(self, normalized_message: str) -> bool:
        compact = normalized_message.replace(" ", "")
        return any(term in compact for term in ("모순", "충돌", "안맞", "말이안", "거짓", "입증", "증명"))

    def _visible_evidence_context(self, case: Case, session: SessionState, normalized_message: str) -> dict[str, Any] | None:
        visible_items = []
        visible_items.extend(
            (item.evidenceId, item.name, item.description, item)
            for item in case.evidence
            if item.evidenceId in session.unlockedEvidenceIds
        )
        visible_items.extend(
            (item.recordId, item.name, item.description, item)
            for item in case.records
            if item.recordId in session.unlockedRecordIds
        )
        for item_id, name, description, item in visible_items:
            name_score = self._overlap_score(normalized_message, self._normalize_text(name))
            description_score = self._overlap_score(normalized_message, self._normalize_text(description))
            compact_message = normalized_message.replace(" ", "")
            compact_name = self._normalize_text(name).replace(" ", "")
            if compact_name and compact_name in compact_message:
                name_score += 2
            if item_id.startswith("ev_") and not evidence_is_mentioned(normalized_message, item):
                continue
            if item_id.startswith("ev_") or name_score >= 2 or description_score >= 2:
                return {
                    "id": item_id,
                    "text": f"{name}. {description}",
                    "sourceRefs": {
                        "statementIds": [],
                        "timelineIds": self._timeline_ids_for_source(case, item_id),
                        "evidenceIds": [item_id] if item_id.startswith("ev_") else [],
                    },
                }
        return None

    def _fallback_answer_for_intent(self, dialogue_mode: str, suspect, message: str) -> str:
        if dialogue_mode == "small_talk":
            return "인사는 됐어요. 정말 묻고 싶은 게 있잖아요."
        if dialogue_mode == "evidence_question":
            return "그 얘기를 제게 돌리시려는 건가요. 쉽게 인정할 수는 없습니다."
        if dialogue_mode == "pressure_followup":
            compact = self._normalize_text(message).replace(" ", "")
            if any(term in compact for term in ("말이돼", "말이된다고", "납득", "이상하")):
                return "말이 안 된다고 몰아붙이셔도 제가 이미 말씀드린 내용은 같습니다."
            return "피하려는 게 아닙니다. 기억나는 범위는 이미 말씀드렸습니다."
        if dialogue_mode == "timeline_question":
            return "그 시간대라면 저는 제 방에 있었어요. 폭풍 때문에 방 밖으로 오래 나갈 상황도 아니었습니다."
        return "그 질문은 너무 넓어요. 그렇게 몰아가듯 묻지 마세요."

    def _neutral_allowed_statement(self, case: Case, suspect) -> str:
        return f"{case.summary} {suspect.name}은(는) {suspect.role}이며 공개 프로필은 다음과 같다: {suspect.publicProfile}"

    def _mentions_time(self, normalized_message: str) -> bool:
        compact = normalized_message.replace(" ", "")
        return bool(re.search(r"\d{1,2}", compact)) or any(term in compact for term in ("열시", "열한시", "자정", "밤", "시각", "시간"))

    def _pressure_state(self, session: SessionState, suspect_id: str) -> str:
        return pressure_state(session.pressureBySuspect.get(suspect_id, 0))

    def _contradiction_candidate_events(
        self,
        case: Case,
        session: SessionState,
        message: str,
        suspect_id: str,
        dialogue_mode: str,
    ) -> list[dict]:
        if dialogue_mode not in {"case_question", "evidence_question"}:
            return []
        normalized_message = self._normalize_text(message)
        events = []
        for contradiction in case.contradictions:
            if contradiction.relatedCharacterId != suspect_id:
                continue
            if not set(contradiction.requiredStatementIds).issubset(set(session.unlockedStatementIds)):
                continue
            if not set(contradiction.requiredEvidenceIds).issubset(set(session.unlockedEvidenceIds)):
                continue
            evidence_mentions = any(
                self._source_mentioned(normalized_message, evidence.name, evidence.description)
                for evidence in case.evidence
                if evidence.evidenceId in contradiction.requiredEvidenceIds
            )
            statement_mentions = any(
                self._source_mentioned(normalized_message, statement.questionText, statement.text)
                for statement in case.statements
                if statement.statementId in contradiction.requiredStatementIds
            )
            if evidence_mentions and (statement_mentions or dialogue_mode == "evidence_question"):
                events.append(
                    {
                        "type": "NOTE_CONTRADICTION_CANDIDATE_ADDED",
                        "payload": {"contradictionId": contradiction.contradictionId},
                    }
                )
        return events

    def _contradiction_note_events_from_transition(self, transition: dict[str, Any]) -> list[dict]:
        events = []
        for contradiction_id in transition.get("newlyDiscoveredContradictionIds") or []:
            events.append(
                {
                    "type": EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value,
                    "payload": {
                        "contradictionId": contradiction_id,
                        "statementIds": list(transition.get("statementIds") or []),
                        "evidenceIds": list(transition.get("evidenceIds") or []),
                    },
                }
            )
        return events

    def _source_mentioned(self, normalized_message: str, *texts: str | None) -> bool:
        compact_message = normalized_message.replace(" ", "")
        for text in texts:
            normalized = self._normalize_text(text or "")
            compact_text = normalized.replace(" ", "")
            if compact_text and compact_text in compact_message:
                return True
            if self._overlap_score(normalized_message, normalized) >= 2:
                return True
        return False

    def _visible_facts(self, case: Case, session: SessionState) -> dict:
        return {
            "statementIds": list(session.unlockedStatementIds),
            "evidenceIds": list(session.unlockedEvidenceIds),
            "recordIds": list(session.unlockedRecordIds),
            "discoveredContradictionIds": list(session.discoveredContradictionIds),
            "statements": [
                {"id": item.statementId, "characterId": item.characterId, "text": item.text, "timeWindow": item.timeWindow, "location": item.location}
                for item in case.statements
                if item.statementId in session.unlockedStatementIds
            ],
            "evidence": [
                {"id": item.evidenceId, "name": item.name, "description": item.description, "timeWindow": item.timeWindow}
                for item in case.evidence
                if item.evidenceId in session.unlockedEvidenceIds
            ],
            "records": [
                {"id": item.recordId, "name": item.name, "description": item.description, "timeWindow": item.timeWindow}
                for item in case.records
                if item.recordId in session.unlockedRecordIds
            ],
        }

    def _storyline_context(self, case: Case, session: SessionState, story_progress: dict[str, str]) -> dict:
        storyline = public_storyline(case, session) or {}
        return {
            "publicPremise": storyline.get("publicPremise"),
            "currentActId": story_progress["currentActId"],
            "currentObjective": story_progress["currentObjective"],
            "visibleTimeline": visible_timeline(case, session),
        }

    def _character_timeline_context(self, case: Case, session: SessionState, suspect_id: str) -> dict:
        suspect = self._suspect(case, suspect_id)
        events = []
        for item in character_public_timeline(case, session, suspect_id):
            events.append(
                {
                    "timelineId": item.get("timelineId") or item.get("sourceId"),
                    "time": item.get("time"),
                    "title": item.get("title"),
                    "summary": item.get("description"),
                    "sourceType": item.get("sourceType"),
                    "sourceId": item.get("sourceId"),
                    "claimedLocation": item.get("claimedLocation"),
                    "claimedAction": item.get("claimedAction"),
                    "relatedStatementIds": list(item.get("relatedStatementIds") or []),
                    "relatedEvidenceIds": list(item.get("relatedEvidenceIds") or []),
                    "public": True,
                }
            )
        return {
            "suspectId": suspect_id,
            "publicPersona": (suspect.speechStyle or public_speech_style(suspect_id)).get("persona", suspect.publicProfile),
            "events": events,
        }

    def _allowed_event_policy(
        self,
        case: Case,
        session: SessionState,
        suspect_id: str,
        match: DialogueMatch,
        allowed_statement: dict[str, Any],
        player_message: str,
    ) -> dict:
        source_refs = allowed_statement.get("sourceRefs") if isinstance(allowed_statement, dict) else {}
        statement_ids = list(source_refs.get("statementIds") or [])
        evidence_ids = list(source_refs.get("evidenceIds") or [])
        if match.question is not None:
            statement_ids.extend(match.question.unlocksStatementIds)
            evidence_ids.extend(match.question.unlocksEvidenceIds)
        if match.dialogue_mode == "evidence_question":
            evidence_ids.extend(self._visible_evidence_ids_mentioned(case, session, player_message))
            context = self._visible_contradiction_context(case, session, suspect_id, match, player_message)
            statement_ids.extend(context["statementIds"])
            evidence_ids.extend(context["evidenceIds"])
            source_refs.setdefault("timelineIds", [])
            source_refs["timelineIds"] = [*source_refs["timelineIds"], *context["timelineIds"]]
        statement_ids = self._dedupe_visible(statement_ids, session.unlockedStatementIds)
        evidence_ids = self._dedupe_visible(evidence_ids, session.unlockedEvidenceIds)
        related_contradictions = self._related_visible_contradiction_ids(case, session, suspect_id, statement_ids, evidence_ids)
        allowed_types = [
            EventType.BOOKMARK_SUGGESTED.value,
        ]
        if match.consumed_question or match.dialogue_mode == "evidence_question":
            allowed_types.extend([EventType.NOTE_FACT_ADDED.value, EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value])
        return {
            "allowedTypes": allowed_types,
            "relatedEvidenceIds": evidence_ids,
            "relatedTimelineEventIds": list(source_refs.get("timelineIds") or []),
            "relatedStatementIds": statement_ids,
            "relatedQuestionIds": [match.question.questionId] if match.question is not None else [],
            "relatedContradictionIds": related_contradictions,
        }

    def _merge_turn_interpretation(self, allowed_event_policy: dict[str, Any], interpretation: dict[str, Any]) -> None:
        allowed_event_policy["relatedEvidenceIds"] = self._dedupe(
            [
                *(allowed_event_policy.get("relatedEvidenceIds") or []),
                *(interpretation.get("mentionedEvidenceIds") or []),
            ]
        )
        allowed_event_policy["relatedStatementIds"] = self._dedupe(
            [
                *(allowed_event_policy.get("relatedStatementIds") or []),
                *(interpretation.get("mentionedStatementIds") or []),
            ]
        )
        allowed_event_policy["relatedTimelineEventIds"] = self._dedupe(
            [
                *(allowed_event_policy.get("relatedTimelineEventIds") or []),
                *(interpretation.get("matchedTimelineIds") or []),
            ]
        )
        allowed_event_policy["relatedContradictionIds"] = self._dedupe(
            [
                *(allowed_event_policy.get("relatedContradictionIds") or []),
                *(interpretation.get("candidateContradictionIds") or []),
            ]
        )

    def _augment_allowed_statement_for_transition(
        self,
        case: Case,
        allowed_statement: dict[str, Any],
        transition: dict[str, Any],
    ) -> None:
        if not transition.get("decisiveEvidence") and not transition.get("contradictionIds"):
            return
        refs = allowed_statement.get("sourceRefs") or {}
        statement_ids = set(refs.get("statementIds") or transition.get("statementIds") or [])
        evidence_ids = set(refs.get("evidenceIds") or transition.get("evidenceIds") or [])
        contradiction_ids = set(refs.get("contradictionIds") or transition.get("contradictionIds") or [])
        source_facts: list[str] = []
        for statement in case.statements:
            if statement.statementId in statement_ids:
                source_facts.append(statement.text)
        for evidence in case.evidence:
            if evidence.evidenceId in evidence_ids:
                source_facts.append(f"{evidence.name}: {evidence.description}")
        if source_facts:
            allowed_statement["sourceFacts"] = self._dedupe(
                [*(allowed_statement.get("sourceFacts") or []), *source_facts]
            )
        if contradiction_ids:
            refs.setdefault("contradictionIds", [])
            refs["contradictionIds"] = self._dedupe([*refs["contradictionIds"], *contradiction_ids])
        refs.setdefault("statementIds", [])
        refs.setdefault("evidenceIds", [])
        refs["statementIds"] = self._dedupe([*refs["statementIds"], *statement_ids])
        refs["evidenceIds"] = self._dedupe([*refs["evidenceIds"], *evidence_ids])
        allowed_statement["sourceRefs"] = refs

    def _visible_contradiction_context(
        self,
        case: Case,
        session: SessionState,
        suspect_id: str,
        match: DialogueMatch,
        player_message: str,
    ) -> dict[str, list[str]]:
        source_texts = [player_message]
        if match.question is not None:
            source_texts.append(match.question.text)
        if match.allowed_statement is not None:
            source_texts.append(str(match.allowed_statement.get("text") or ""))
        normalized = self._normalize_text(" ".join(source_texts))
        statement_ids: list[str] = []
        evidence_ids: list[str] = []
        timeline_ids: list[str] = []
        for contradiction in case.contradictions:
            if contradiction.relatedCharacterId != suspect_id:
                continue
            if not set(contradiction.requiredStatementIds).issubset(set(session.unlockedStatementIds)):
                continue
            if not set(contradiction.requiredEvidenceIds).issubset(set(session.unlockedEvidenceIds)):
                continue
            evidence_mentioned = any(
                self._source_mentioned(normalized, evidence.name)
                for evidence in case.evidence
                if evidence.evidenceId in contradiction.requiredEvidenceIds
            )
            if not evidence_mentioned:
                continue
            statement_ids.extend(contradiction.requiredStatementIds)
            evidence_ids.extend(contradiction.requiredEvidenceIds)
            for source_id in [*contradiction.requiredStatementIds, *contradiction.requiredEvidenceIds]:
                timeline_ids.extend(self._timeline_ids_for_source(case, source_id))
        return {
            "statementIds": self._dedupe(statement_ids),
            "evidenceIds": self._dedupe(evidence_ids),
            "timelineIds": self._dedupe(timeline_ids),
        }

    def _visible_evidence_ids_mentioned(self, case: Case, session: SessionState, player_message: str) -> list[str]:
        normalized = self._normalize_text(player_message)
        evidence_ids: list[str] = []
        for evidence in case.evidence:
            if evidence.evidenceId not in session.unlockedEvidenceIds:
                continue
            if evidence_is_mentioned(normalized, evidence):
                evidence_ids.append(evidence.evidenceId)
        return self._dedupe(evidence_ids)

    def _related_visible_contradiction_ids(
        self,
        case: Case,
        session: SessionState,
        suspect_id: str,
        statement_ids: list[str],
        evidence_ids: list[str],
    ) -> list[str]:
        related = []
        statement_set = set(statement_ids)
        evidence_set = set(evidence_ids)
        for contradiction in case.contradictions:
            if contradiction.relatedCharacterId != suspect_id:
                continue
            if not set(contradiction.requiredStatementIds).issubset(set(session.unlockedStatementIds)):
                continue
            if not set(contradiction.requiredEvidenceIds).issubset(set(session.unlockedEvidenceIds)):
                continue
            if statement_set & set(contradiction.requiredStatementIds) or evidence_set & set(contradiction.requiredEvidenceIds):
                related.append(contradiction.contradictionId)
        return related

    def _dedupe_visible(self, values: list[str], visible_values: list[str]) -> list[str]:
        visible = set(visible_values)
        deduped = []
        for value in values:
            if value in visible and value not in deduped:
                deduped.append(value)
        return deduped

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        return deduped

    def _timeline_ids_for_source(self, case: Case, source_id: str) -> list[str]:
        if not case.storyline:
            return []
        ids = []
        for item in case.storyline.timeline:
            if item.hidden or item.sourceId != source_id:
                continue
            ids.append(str(getattr(item, "timelineId", None) or item.sourceId))
        return ids

    def _dialogue_history_summary(self, session: SessionState) -> list[dict[str, str | None]]:
        return [
            {"speaker": item.speaker, "suspectId": item.suspectId, "questionId": item.questionId, "text": item.text}
            for item in session.dialogueLog[-8:]
        ]

    def _dialogue_tone(self, transition: dict[str, Any]) -> str:
        if transition.get("decisiveEvidence"):
            return "evidence_shock"
        if transition.get("pressureState") == "broken":
            return "broken"
        if transition.get("composure") in {"breaking", "rattled"}:
            return "pressed"
        if transition.get("move") == "repeat_pressure":
            return "defensive"
        return "calm_defensive"

    def _log_ai_fallback(
        self,
        request_context: RequestContext,
        session: SessionState,
        case: Case,
        suspect_id: str,
        started_at: float,
    ) -> None:
        logger.warning(
            "dialogue ai service degraded",
            extra={
                "service": "backend",
                "request_id": request_context.request_id,
                "session_id": session.sessionId,
                "case_id": case.caseId,
                "route": request_context.route,
                "suspect_id": suspect_id,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "fallback_used": False,
            },
        )

    def _raise_ai_degraded(
        self,
        request_context: RequestContext,
        session: SessionState,
        case: Case,
        suspect_id: str,
        started_at: float,
        reason: str,
    ) -> None:
        logger.warning(
            "dialogue rejected because ai service is degraded",
            extra={
                "service": "backend",
                "request_id": request_context.request_id,
                "session_id": session.sessionId,
                "case_id": case.caseId,
                "route": request_context.route,
                "suspect_id": suspect_id,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "fallback_used": False,
                "reason": reason,
            },
        )
        raise service_unavailable(
            "AI_SERVICE_DEGRADED",
            {
                "sessionId": session.sessionId,
                "caseId": case.caseId,
                "suspectId": suspect_id,
                "fallbackUsed": False,
                "degradedReason": reason,
            },
        )

    def _log_dialogue(
        self,
        request_context: RequestContext,
        session: SessionState,
        case: Case,
        suspect_id: str,
        started_at: float,
        fallback_used: bool,
        dialogue_mode: str,
    ) -> None:
        logger.info(
            "dialogue accepted",
            extra={
                "service": "backend",
                "request_id": request_context.request_id,
                "session_id": session.sessionId,
                "case_id": case.caseId,
                "route": request_context.route,
                "suspect_id": suspect_id,
                "dialogue_mode": dialogue_mode,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "fallback_used": fallback_used,
            },
        )

    def _normalize_text(self, value: str) -> str:
        normalized = "".join(ch for ch in value.lower() if ch.isalnum() or ch.isspace()).strip()
        replacements = {
            "파해자": "피해자",
            "피헤자": "피해자",
            "복용 한": "복용한",
            "와인 잔": "와인잔",
            "약 상자": "약상자",
        }
        for wrong, right in replacements.items():
            normalized = normalized.replace(wrong, right)
        return normalized

    def _matched_refs(self, allowed_statement: dict[str, Any], allowed_event_policy: dict[str, Any]) -> dict[str, list[str]]:
        refs = allowed_statement.get("sourceRefs") if isinstance(allowed_statement, dict) else {}
        return {
            "statementIds": list(refs.get("statementIds") or allowed_event_policy.get("relatedStatementIds") or []),
            "evidenceIds": list(refs.get("evidenceIds") or allowed_event_policy.get("relatedEvidenceIds") or []),
            "timelineIds": list(refs.get("timelineIds") or allowed_event_policy.get("relatedTimelineEventIds") or []),
            "contradictionIds": list(allowed_event_policy.get("relatedContradictionIds") or []),
            "questionIds": list(allowed_event_policy.get("relatedQuestionIds") or []),
        }

    def _diagnostic_reason(self, match: DialogueMatch, allowed_event_policy: dict[str, Any]) -> str:
        if match.dialogue_mode == "unmatched":
            return "insufficient_public_ref"
        if match.question is not None:
            return "matched_public_question"
        if allowed_event_policy.get("relatedEvidenceIds") or allowed_event_policy.get("relatedStatementIds"):
            return "matched_public_ref"
        return "no_progress_public_context"

    def _overlap_score(self, left: str, right: str) -> int:
        left_tokens = {token for token in left.split() if token}
        right_tokens = {token for token in right.split() if token}
        return len(left_tokens & right_tokens)
