import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.application.case_knowledge_service import CaseKnowledgeService
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
from app.domain.models import Case, DialogueEntry, SessionState
from app.domain.rule_engine import RuleEngine
from app.infra.local_ai_client import LocalAIClient as AIClient
from app.infra.case_repository import CaseRepository
from app.infra.event_repository import EventRepository
from app.infra.session_repository import SessionRepository

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
    case_repo: CaseRepository
    session_repo: SessionRepository
    event_repo: EventRepository
    rule_engine: RuleEngine
    ai_client: AIClient
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
        allowed_event_policy = self._allowed_event_policy(case, session, match, allowed_statement, message)
        decisive_pressure_hit = self._apply_decisive_evidence_pressure(
            case=case,
            session=session,
            suspect_id=suspect.characterId,
            match=match,
            player_message=message,
            allowed_statement=allowed_statement,
            allowed_event_policy=allowed_event_policy,
        )
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
                "speechStyle": public_speech_style(suspect.characterId),
                "publicTimeline": character_public_timeline(case, session, suspect.characterId),
                "pressure": session.pressureBySuspect.get(suspect.characterId, 0),
                "pressureState": self._pressure_state(session, suspect.characterId),
                "tensionLevel": tension_level(session.pressureBySuspect.get(suspect.characterId, 0)),
                "tensionScore": session.pressureBySuspect.get(suspect.characterId, 0),
                "emotionalState": emotional_state(session.pressureBySuspect.get(suspect.characterId, 0)),
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
                "tone": "evidence_shock" if decisive_pressure_hit else self._dialogue_tone(session, suspect.characterId),
                "maxLength": 220,
            },
            "revealAllowed": False,
            "allowedEventPolicy": allowed_event_policy,
        }
        self._assert_public_surface(ai_payload, "ai_payload")
        ai_result = await self.ai_client.dialogue_response_info(ai_payload, fallback_answer)
        if ai_result.get("degraded"):
            self._raise_ai_degraded(
                request_context=request_context,
                session=session,
                case=case,
                suspect_id=suspect.characterId,
                started_at=started_at,
                reason=str(ai_result.get("degradedReason") or "ai_service_unavailable"),
            )
        self._assert_public_surface(
            {
                "answer": ai_result.get("answer"),
                "proposedEvents": ai_result.get("proposedEvents") or [],
            },
            "ai_result",
        )
        answer = self._polish_answer(ai_result["answer"], suspect.name)
        question_id_for_log = match.question.questionId if match.question is not None else None
        npc_entry = self._append_dialogue_entries(session, suspect.characterId, question_id_for_log, suspect.name, message, answer)
        session.newlyUnlockedIds = question_result["newlyUnlockedIds"]

        processor = EventProcessor(start_index=self.event_repo.next_index(session.sessionId))
        ai_proposed_events = list(ai_result["proposedEvents"])
        be_proposed_events = self._contradiction_candidate_events(case, session, message, suspect.characterId, match.dialogue_mode)
        proposed_events = [
            *ai_proposed_events,
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
        self._assert_public_surface([event.model_dump(mode="json") for event in applied_events], "applied_events")
        self.event_repo.append_many(applied_events)
        self.session_repo.save(session)

        public_safety = self._public_safety(ai_result["safety"])
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
            "dialogueResult": {
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
                "proposedEventsCount": len(ai_proposed_events),
                "beProposedEventsCount": len(be_proposed_events),
                "totalProposedEventsCount": len(proposed_events),
                "appliedEventsCount": len(applied_events),
                "appliedEvents": [event.model_dump(mode="json") for event in applied_events],
            },
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
            "runtimeDiagnostics": {
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
                "totalProposedEventsCount": len(proposed_events),
                "appliedEventsCount": len(applied_events),
                "reason": self._diagnostic_reason(match, allowed_event_policy),
            },
            "proposedEventsCount": len(ai_proposed_events),
            "beProposedEventsCount": len(be_proposed_events),
            "totalProposedEventsCount": len(proposed_events),
            "appliedEventsCount": len(applied_events),
            "proposedEventsApplied": [event.id for event in applied_events],
            "visualState": build_visual_state(session, case, suspect.characterId),
            "session": session,
            "case": case,
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

        exact = next((item for item in candidates if self._normalize_text(item.text) == normalized_message), None)
        if exact:
            return DialogueMatch(dialogue_mode="case_question", question=exact, consumed_question=True)

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

        evidence_context = self._visible_evidence_context(case, session, normalized_message)
        if evidence_context is not None:
            return DialogueMatch(
                dialogue_mode="evidence_question",
                allowed_statement=evidence_context,
                fallback_answer=self._fallback_answer_for_intent("evidence_question", self._suspect(case, suspect_id), message),
            )

        return DialogueMatch(
            dialogue_mode="unmatched",
            fallback_answer=self._fallback_answer_for_intent("unmatched", self._suspect(case, suspect_id), message),
        )

    def _suspect(self, case: Case, suspect_id: str):
        return next(item for item in case.suspects if item.characterId == suspect_id)

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
        if "study_entry" in question.questionId and "서재" in compact and any(term in compact for term in ("출입", "기록", "들어")):
            score += 5
        if "parkmingyu_medicine" in question.questionId and any(term in compact for term in ("약", "복용", "약물", "처방", "주치의", "의사")):
            score += 5
        if "choiyuna_wine" in question.questionId and any(term in compact for term in ("와인", "와인잔", "립스틱", "잔", "자국")):
            score += 5
        if "choiyuna_last_call" in question.questionId and any(term in compact for term in ("통화", "전화", "연락", "휴대폰")):
            score += 5
        if "inheritance" in question.questionId and any(term in compact for term in ("상속", "유언장", "다툰")):
            score += 5
        if question_compact and question_compact in compact:
            score += 4

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
            context_text = "말이 안 된다고 해도 제 기억은 같습니다. 저는 방에 있었다고 기억합니다."
        else:
            context_text = "답이 부족했다면 회피하려는 뜻은 아닙니다. 기억나는 범위를 말하고 있습니다."
        if alibi_statement is not None:
            context_text = f"{context_text} 공개 알리바이: {alibi_statement.text}".strip()
        return {
            "id": f"recent_pressure_{suspect_id}",
            "text": context_text or f"플레이어가 직전 답변을 압박하고 있다: {message}",
            "sourceRefs": {"statementIds": statement_ids, "timelineIds": timeline_ids, "evidenceIds": []},
        }

    def _looks_like_evidence_question(self, case: Case, session: SessionState, normalized_message: str) -> bool:
        if self._visible_evidence_context(case, session, normalized_message) is not None:
            return True
        compact = normalized_message.replace(" ", "")
        return any(term in compact for term in ("증거", "기록", "흔적", "와인잔", "와인", "립스틱", "회중시계", "약상자", "약", "복용", "통화기록"))

    def _visible_evidence_context(self, case: Case, session: SessionState, normalized_message: str) -> dict[str, Any] | None:
        visible_items = []
        visible_items.extend(
            (item.evidenceId, item.name, item.description)
            for item in case.evidence
            if item.evidenceId in session.unlockedEvidenceIds
        )
        visible_items.extend(
            (item.recordId, item.name, item.description)
            for item in case.records
            if item.recordId in session.unlockedRecordIds
        )
        for item_id, name, description in visible_items:
            name_score = self._overlap_score(normalized_message, self._normalize_text(name))
            description_score = self._overlap_score(normalized_message, self._normalize_text(description))
            compact_message = normalized_message.replace(" ", "")
            compact_name = self._normalize_text(name).replace(" ", "")
            if compact_name and compact_name in compact_message:
                name_score += 2
            if item_id == "ev_wine_glass" and any(term in compact_message for term in ("립스틱", "와인", "와인잔", "잔자국")):
                name_score += 4
            if item_id == "ev_medicine_box" and any(term in compact_message for term in ("약", "복용", "약물", "처방")):
                name_score += 4
            if name_score >= 2 or description_score >= 2:
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
            return f"{suspect.name}은 잠시 시선을 피했다. \"인사는 됐어요. 형사님이 정말 묻고 싶은 게 뭔지 말해 주세요.\""
        if dialogue_mode == "evidence_question":
            return f"{suspect.name}은 질문을 곱씹었다. \"그 단서만으로 저를 몰아가긴 어렵지 않나요. 정확히 어떤 부분을 묻는 건지 짚어 주세요.\""
        if dialogue_mode == "pressure_followup":
            compact = self._normalize_text(message).replace(" ", "")
            if any(term in compact for term in ("말이돼", "말이된다고", "납득", "이상하")):
                return f"{suspect.name}이 표정을 굳혔다. \"말이 안 된다고 몰아붙이셔도 제 기억은 같아요. 저는 22시쯤 방에 있었고, 다른 단서가 있다면 그걸 보여 주세요.\""
            return f"{suspect.name}이 숨을 고르며 말했다. \"방금 말한 건 피하려는 게 아니에요. 저는 그 시간에 제 방에 있었다고 기억합니다. 의심할 근거가 있다면 그걸 놓고 물어보세요.\""
        if dialogue_mode == "timeline_question":
            return f"{suspect.name}이 고개를 들었다. \"그 시간대라면 저는 제 방에 있었다고 말씀드릴 수 있어요. 폭풍 때문에 방 밖으로 오래 나갈 상황도 아니었습니다.\""
        return f"{suspect.name}은 경계심을 숨기지 않았다. \"그 질문은 너무 넓어요. 시간, 장소, 단서 중 무엇을 확인하려는 건지 분명히 말해 주세요.\""

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

    def _source_mentioned(self, normalized_message: str, *texts: str | None) -> bool:
        return any(self._overlap_score(normalized_message, self._normalize_text(text or "")) >= 1 for text in texts)

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
            "publicPersona": public_speech_style(suspect_id).get("persona", suspect.publicProfile),
            "events": events,
        }

    def _allowed_event_policy(
        self,
        case: Case,
        session: SessionState,
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
            context = self._visible_contradiction_context(case, session, match, player_message)
            statement_ids.extend(context["statementIds"])
            evidence_ids.extend(context["evidenceIds"])
            source_refs.setdefault("timelineIds", [])
            source_refs["timelineIds"] = [*source_refs["timelineIds"], *context["timelineIds"]]
        statement_ids = self._dedupe_visible(statement_ids, session.unlockedStatementIds)
        evidence_ids = self._dedupe_visible(evidence_ids, session.unlockedEvidenceIds)
        related_contradictions = self._related_visible_contradiction_ids(case, session, statement_ids, evidence_ids)
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

    def _visible_contradiction_context(
        self,
        case: Case,
        session: SessionState,
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
            if not set(contradiction.requiredStatementIds).issubset(set(session.unlockedStatementIds)):
                continue
            if not set(contradiction.requiredEvidenceIds).issubset(set(session.unlockedEvidenceIds)):
                continue
            evidence_mentioned = any(
                self._source_mentioned(normalized, evidence.name, evidence.description)
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
        compact = normalized.replace(" ", "")
        evidence_ids: list[str] = []
        for evidence in case.evidence:
            if evidence.evidenceId not in session.unlockedEvidenceIds:
                continue
            compact_name = self._normalize_text(evidence.name).replace(" ", "")
            if compact_name and compact_name in compact:
                evidence_ids.append(evidence.evidenceId)
                continue
            if evidence.evidenceId == "ev_wine_glass" and any(term in compact for term in ("립스틱", "와인", "와인잔", "잔자국")):
                evidence_ids.append(evidence.evidenceId)
            elif evidence.evidenceId == "ev_medicine_box" and any(term in compact for term in ("약", "복용", "약물", "처방")):
                evidence_ids.append(evidence.evidenceId)
        return self._dedupe(evidence_ids)

    def _related_visible_contradiction_ids(self, case: Case, session: SessionState, statement_ids: list[str], evidence_ids: list[str]) -> list[str]:
        related = []
        statement_set = set(statement_ids)
        evidence_set = set(evidence_ids)
        for contradiction in case.contradictions:
            if not set(contradiction.requiredStatementIds).issubset(set(session.unlockedStatementIds)):
                continue
            if not set(contradiction.requiredEvidenceIds).issubset(set(session.unlockedEvidenceIds)):
                continue
            if statement_set & set(contradiction.requiredStatementIds) or evidence_set & set(contradiction.requiredEvidenceIds):
                related.append(contradiction.contradictionId)
        return related

    def _apply_decisive_evidence_pressure(
        self,
        case: Case,
        session: SessionState,
        suspect_id: str,
        match: DialogueMatch,
        player_message: str,
        allowed_statement: dict[str, Any],
        allowed_event_policy: dict,
    ) -> bool:
        if match.dialogue_mode != "evidence_question":
            return False
        related_ids = set(allowed_event_policy.get("relatedContradictionIds") or [])
        if not related_ids:
            return False
        normalized = self._normalize_text(player_message)
        visible_statements = set(session.unlockedStatementIds)
        visible_evidence = set(session.unlockedEvidenceIds)
        for contradiction in case.contradictions:
            if contradiction.contradictionId not in related_ids:
                continue
            if contradiction.relatedCharacterId != suspect_id:
                continue
            if not set(contradiction.requiredStatementIds).issubset(visible_statements):
                continue
            if not set(contradiction.requiredEvidenceIds).issubset(visible_evidence):
                continue
            evidence_was_presented = any(
                self._source_mentioned(normalized, evidence.name, evidence.description)
                for evidence in case.evidence
                if evidence.evidenceId in contradiction.requiredEvidenceIds
            )
            if not evidence_was_presented:
                continue
            refs = allowed_statement.setdefault("sourceRefs", {})
            refs["contradictionIds"] = self._dedupe([*(refs.get("contradictionIds") or []), contradiction.contradictionId])
            if contradiction.contradictionId not in session.discoveredContradictionIds:
                session.discoveredContradictionIds.append(contradiction.contradictionId)
                current = session.pressureBySuspect.get(suspect_id, 0)
                severity_floor = {"minor": 45, "major": 55, "core": 70}.get(contradiction.severity, 45)
                session.pressureBySuspect[suspect_id] = min(100, current + max(contradiction.pressureDelta, severity_floor))
            return True
        return False

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

    def _dialogue_tone(self, session: SessionState, suspect_id: str) -> str:
        state = self._pressure_state(session, suspect_id)
        if state == "broken":
            return "nervous"
        if state == "pressed":
            return "pressed"
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
