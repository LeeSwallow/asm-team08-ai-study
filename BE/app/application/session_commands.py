import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import uuid4

from app.core.errors import bad_request, not_found, service_unavailable
from app.core.leak_guard import assert_no_forbidden_refs
from app.core.observability import RequestContext
from app.domain.case_engine import apply_unlocks, initial_session_state, pressure_state
from app.domain.event_processor import target_is_visible
from app.domain.models import BookmarkEntry, Case, DialogueEntry, NoteEntry, SessionState
from app.domain.rule_engine import RuleEngine
from app.infra.local_ai_client import LocalAIClient as AIClient
from app.infra.case_repository import CaseRepository
from app.infra.session_repository import SessionRepository

logger = logging.getLogger(__name__)


@dataclass
class SessionCommands:
    case_repo: CaseRepository
    session_repo: SessionRepository
    rule_engine: RuleEngine
    ai_client: AIClient

    def create_session(self, case_id: str) -> tuple[SessionState, Case]:
        case = self.case_repo.get_case(case_id)
        if case is None:
            raise not_found("Case not found")
        session = initial_session_state(case, f"sess_{uuid4().hex}")
        self.session_repo.save(session)
        return session, case

    def load_session_and_case(self, session_id: str) -> tuple[SessionState, Case]:
        session = self.session_repo.get(session_id)
        if session is None:
            raise not_found("Session not found")
        case = self.case_repo.get_case(session.caseId)
        if case is None:
            raise not_found("Case not found")
        return session, case

    async def ask_question(self, session_id: str, question_id: str, suspect_id: str | None) -> dict:
        session, case = self.load_session_and_case(session_id)
        question = next((item for item in case.questions if item.questionId == question_id), None)
        if question is None:
            raise bad_request("QUESTION_NOT_FOUND")
        if suspect_id is not None and suspect_id != question.characterId:
            raise bad_request("QUESTION_SUSPECT_MISMATCH")
        try:
            question_result = self.rule_engine.answer_question(session, case, question_id)
        except ValueError as exc:
            raise bad_request(str(exc))

        fallback_answer = question_result["answer"]
        suspect = next(item for item in case.suspects if item.characterId == question.characterId)
        ai_result = await self.ai_client.dialogue_response_info(
            {
                "caseId": case.caseId,
                "sessionId": session.sessionId,
                "suspect": {
                    "id": suspect.characterId,
                    "name": suspect.name,
                    "role": suspect.role,
                    "pressureState": pressure_state(session.pressureBySuspect.get(suspect.characterId, 0)),
                },
                "question": {"id": question.questionId, "text": question.text},
                "allowedStatement": self._allowed_statement_for_question(case, question, fallback_answer),
                "style": {
                    "tone": self._dialogue_tone(session, suspect.characterId),
                    "maxLength": 220,
                },
                "revealAllowed": False,
            },
            fallback_answer,
        )
        if ai_result.get("degraded"):
            logger.warning(
                "question rejected because ai service is degraded",
                extra={
                    "service": "backend",
                    "session_id": session.sessionId,
                    "case_id": case.caseId,
                    "route": "/sessions/{session_id}/questions",
                    "suspect_id": suspect.characterId,
                    "fallback_used": False,
                    "reason": ai_result.get("degradedReason"),
                },
            )
            raise service_unavailable(
                "AI_SERVICE_DEGRADED",
                {
                    "sessionId": session.sessionId,
                    "caseId": case.caseId,
                    "suspectId": suspect.characterId,
                    "fallbackUsed": False,
                    "degradedReason": ai_result.get("degradedReason") or "ai_service_unavailable",
                },
            )
        answer = ai_result["answer"]
        session.dialogueLog.extend(
            [
                DialogueEntry(
                    id=f"dlg_{uuid4().hex}",
                    suspectId=question.characterId,
                    questionId=question.questionId,
                    speaker="player",
                    text=question.text,
                ),
                DialogueEntry(
                    id=f"dlg_{uuid4().hex}",
                    suspectId=question.characterId,
                    questionId=question.questionId,
                    speaker=suspect.name,
                    text=answer,
                ),
            ]
        )
        session.newlyUnlockedIds = question_result["newlyUnlockedIds"]
        self.session_repo.save(session)
        return {
            "session": session,
            "case": case,
            "answer": answer,
            "questionResult": {
                "questionId": question.questionId,
                "repeated": question_result["repeated"],
                "askCount": question_result["askCount"],
                "remainingQuestions": session.remainingQuestions,
                "unlockedIds": question_result["newlyUnlockedIds"],
            },
        }

    def judge_contradiction(
        self,
        session_id: str,
        suspect_id: str | None,
        statement_ids: list[str],
        evidence_ids: list[str],
        request_context: RequestContext,
    ) -> dict:
        started_at = time.perf_counter()
        session, case = self.load_session_and_case(session_id)
        result = self.rule_engine.judge_contradiction(
            session,
            case,
            statement_ids=statement_ids,
            evidence_ids=evidence_ids,
            suspect_id=suspect_id,
        )
        session.dialogueLog.append(
            DialogueEntry(
                id=f"dlg_{uuid4().hex}",
                suspectId=suspect_id,
                speaker="rule_engine",
                text=result["message"],
            )
        )
        self.session_repo.save(session)
        self._log_verdict("contradiction judged", request_context, session, case, suspect_id, result["verdict"], started_at)
        return {"session": session, "case": case, "contradictionResult": result}

    def judge_accusation(
        self,
        session_id: str,
        suspect_id: str,
        evidence_ids: list[str],
        contradiction_ids: list[str],
        statement_ids: list[str],
        motive: str | None,
        method: str | None,
        request_context: RequestContext,
    ) -> dict:
        started_at = time.perf_counter()
        session, case = self.load_session_and_case(session_id)
        self._assert_public_user_accusation_text(motive, method)

        # Snapshot all fields mutated by rule_engine.judge_accusation so we can
        # fully roll back if the backend-derived result contains forbidden refs.
        original_accusation = session.accusation
        original_phase = session.phase
        original_selected_suspect_id = session.selectedSuspectId
        original_newly_unlocked_ids = list(session.newlyUnlockedIds)

        result = self.rule_engine.judge_accusation(
            session,
            case,
            suspect_id=suspect_id,
            evidence_ids=evidence_ids,
            contradiction_ids=contradiction_ids,
            statement_ids=statement_ids,
            motive=motive,
            method=method,
        )

        # Validate ALL public accusation fields that will appear in SSE/response
        # BEFORE any persistence. This covers backend-derived data (message,
        # missingEvidenceIds, missingContradictionIds, missingStatementIds)
        # that could contain forbidden tokens from case JSON.
        accusation_public_fields = {
            "verdict": result.get("verdict"),
            "message": result.get("message"),
            "missingEvidenceIds": result.get("missingEvidenceIds", []),
            "missingContradictionIds": result.get("missingContradictionIds", []),
            "missingStatementIds": result.get("missingStatementIds", []),
        }
        try:
            assert_no_forbidden_refs(accusation_public_fields, surface="accusation_public_result")
        except ValueError as exc:
            session.accusation = original_accusation
            session.phase = original_phase
            session.selectedSuspectId = original_selected_suspect_id
            session.newlyUnlockedIds = original_newly_unlocked_ids
            logger.error(
                "accusation public result contains forbidden ref; rolled back",
                extra={"service": "backend", "session_id": session_id, "fallback_used": False},
            )
            raise service_unavailable(
                "ACCUSATION_RESULT_FORBIDDEN_REF",
                {"degradedReason": str(exc).split(":", 2)[0], "fallbackUsed": False},
            )

        session.dialogueLog.append(
            DialogueEntry(
                id=f"dlg_{uuid4().hex}",
                suspectId=suspect_id,
                speaker="rule_engine",
                text=result["message"],
            )
        )
        self.session_repo.save(session)
        self._log_verdict("accusation judged", request_context, session, case, suspect_id, result["verdict"], started_at)
        return {"session": session, "case": case, "accusationResult": result}

    def _assert_public_user_accusation_text(self, motive: str | None, method: str | None) -> None:
        try:
            assert_no_forbidden_refs(
                {"submittedMotive": motive or "", "submittedMethod": method or ""},
                surface="accusation_request",
            )
        except ValueError as exc:
            raise bad_request(f"FORBIDDEN_REF_IN_ACCUSATION:{str(exc).split(':', 2)[0]}")

    def create_note(
        self,
        session_id: str,
        text: str,
        tags: list[str],
        linked_statement_ids: list[str],
        linked_evidence_ids: list[str],
        linked_record_ids: list[str],
    ) -> dict:
        if not text.strip():
            raise bad_request("NOTE_TEXT_REQUIRED")
        # Validate text AND tags BEFORE any session mutation or persistence.
        try:
            assert_no_forbidden_refs({"text": text, "tags": tags}, surface="note_fields")
        except ValueError as exc:
            raise bad_request(f"NOTE_TEXT_FORBIDDEN_REF:{str(exc).split(':', 2)[0]}")
        session, case = self.load_session_and_case(session_id)
        self._validate_note_links(session, linked_statement_ids, linked_evidence_ids, linked_record_ids)
        note = NoteEntry(
            id=f"note_{uuid4().hex}",
            text=text.strip(),
            tags=tags,
            linkedStatementIds=linked_statement_ids,
            linkedEvidenceIds=linked_evidence_ids,
            linkedRecordIds=linked_record_ids,
        )
        session.notes.append(note)
        self.session_repo.save(session)
        return {"session": session, "case": case, "note": _dump(note)}

    def update_note(
        self,
        session_id: str,
        note_id: str,
        text: str | None,
        tags: list[str] | None,
        linked_statement_ids: list[str] | None,
        linked_evidence_ids: list[str] | None,
        linked_record_ids: list[str] | None,
    ) -> dict:
        session, case = self.load_session_and_case(session_id)
        note = next((item for item in session.notes if item.id == note_id), None)
        if note is None:
            raise not_found("Note not found")
        next_statement_ids = note.linkedStatementIds if linked_statement_ids is None else linked_statement_ids
        next_evidence_ids = note.linkedEvidenceIds if linked_evidence_ids is None else linked_evidence_ids
        next_record_ids = note.linkedRecordIds if linked_record_ids is None else linked_record_ids
        self._validate_note_links(session, next_statement_ids, next_evidence_ids, next_record_ids)

        # Validate ALL user-supplied public fields BEFORE any mutation or persistence.
        if text is not None and not text.strip():
            raise bad_request("NOTE_TEXT_REQUIRED")
        fields_to_validate: dict = {}
        if text is not None:
            fields_to_validate["text"] = text
        if tags is not None:
            fields_to_validate["tags"] = tags
        if fields_to_validate:
            try:
                assert_no_forbidden_refs(fields_to_validate, surface="note_fields")
            except ValueError as exc:
                raise bad_request(f"NOTE_TEXT_FORBIDDEN_REF:{str(exc).split(':', 2)[0]}")

        if text is not None:
            note.text = text.strip()
        if tags is not None:
            note.tags = tags
        if linked_statement_ids is not None:
            note.linkedStatementIds = linked_statement_ids
        if linked_evidence_ids is not None:
            note.linkedEvidenceIds = linked_evidence_ids
        if linked_record_ids is not None:
            note.linkedRecordIds = linked_record_ids
        note.updatedAt = datetime.utcnow()
        self.session_repo.save(session)
        return {"session": session, "case": case, "note": _dump(note)}

    def delete_note(self, session_id: str, note_id: str) -> dict:
        session, case = self.load_session_and_case(session_id)
        before = len(session.notes)
        session.notes = [item for item in session.notes if item.id != note_id]
        if len(session.notes) == before:
            raise not_found("Note not found")
        self.session_repo.save(session)
        return {"session": session, "case": case, "deletedNoteId": note_id}

    def debug_set_pressure(self, session_id: str, suspect_id: str, pressure: int, request_context: RequestContext) -> dict:
        started_at = time.perf_counter()
        session, case = self.load_session_and_case(session_id)
        if suspect_id not in {suspect.characterId for suspect in case.suspects}:
            raise bad_request("DEBUG_SUSPECT_NOT_FOUND")
        session.pressureBySuspect[suspect_id] = max(0, min(100, pressure))
        session.newlyUnlockedIds = []
        self.session_repo.save(session)
        self._log_debug_action("debug pressure set", request_context, session, case, "pressure", started_at)
        return {
            "session": session,
            "case": case,
            "debugResult": {
                "action": "set_pressure",
                "suspectId": suspect_id,
                "pressure": session.pressureBySuspect[suspect_id],
            },
        }

    def debug_unlock(self, session_id: str, target: str, request_context: RequestContext) -> dict:
        started_at = time.perf_counter()
        session, case = self.load_session_and_case(session_id)
        unlock_ids: list[str] = []
        if target in {"evidence", "timeline", "all"}:
            unlock_ids.extend(item.evidenceId for item in case.evidence)
        if target in {"timeline", "all"}:
            unlock_ids.extend(item.recordId for item in case.records)
            unlock_ids.extend(item.statementId for item in case.statements)
            unlock_ids.extend(item.questionId for item in case.questions)
        if target in {"relations", "all"}:
            unlock_ids.extend(item.relationshipId for item in case.relations)

        newly_unlocked = apply_unlocks(session, case, unlock_ids)
        note_id = None
        if target in {"notes", "all"}:
            note = NoteEntry(
                id=f"note_{uuid4().hex}",
                text="DEBUG: 현재 공개된 사건 파일, 증거, 관계도, 타임라인을 BE 세션 기준으로 다시 동기화했습니다.",
                tags=["debug-only"],
                linkedStatementIds=[item for item in session.unlockedStatementIds[:3]],
                linkedEvidenceIds=[item for item in session.unlockedEvidenceIds[:3]],
                linkedRecordIds=[item for item in session.unlockedRecordIds[:3]],
            )
            session.notes.append(note)
            note_id = note.id
        self.session_repo.save(session)
        self._log_debug_action("debug unlock applied", request_context, session, case, target, started_at)
        return {
            "session": session,
            "case": case,
            "debugResult": {
                "action": "unlock",
                "target": target,
                "unlockedIds": newly_unlocked,
                "noteId": note_id,
            },
        }

    def _validate_note_links(
        self,
        session: SessionState,
        linked_statement_ids: list[str],
        linked_evidence_ids: list[str],
        linked_record_ids: list[str],
    ) -> None:
        for statement_id in linked_statement_ids:
            if not target_is_visible(session, "statement", statement_id):
                raise bad_request("NOTE_LINK_TARGET_NOT_VISIBLE")
        for evidence_id in linked_evidence_ids:
            if not target_is_visible(session, "evidence", evidence_id):
                raise bad_request("NOTE_LINK_TARGET_NOT_VISIBLE")
        for record_id in linked_record_ids:
            if not target_is_visible(session, "record", record_id):
                raise bad_request("NOTE_LINK_TARGET_NOT_VISIBLE")

    def create_bookmark(self, session_id: str, target_type: str, target_id: str, note_text: str | None) -> dict:
        session, case = self.load_session_and_case(session_id)
        if not target_is_visible(session, target_type, target_id):
            raise bad_request("BOOKMARK_TARGET_NOT_VISIBLE")
        target_type_literal = cast(Literal["dialogue", "statement", "evidence", "record", "relation"], target_type)
        bookmark = BookmarkEntry(id=f"bm_{uuid4().hex}", targetType=target_type_literal, targetId=target_id, note=note_text)
        session.bookmarks.append(bookmark)
        self.session_repo.save(session)
        return {"session": session, "case": case, "bookmark": _dump(bookmark)}

    async def summarize_notes(self, session_id: str, note: str) -> dict:
        session, case = self.load_session_and_case(session_id)
        recent_log = "\n".join(f"{entry.speaker}: {entry.text}" for entry in session.dialogueLog[-8:])
        fallback = note.strip() or recent_log or "아직 요약할 조사 기록이 없습니다."
        summary = await self.ai_client.notes_summary(
            {
                "caseId": case.caseId,
                "sessionId": session.sessionId,
                "note": note,
                "dialogueLog": [_dump(item) for item in session.dialogueLog],
                "notes": [_dump(item) for item in session.notes],
            },
            fallback,
        )
        return {"sessionId": session.sessionId, "caseId": case.caseId, "summary": summary}

    async def get_summary(self, session_id: str) -> dict:
        session, case = self.load_session_and_case(session_id)
        notes_text = "\n".join(note.text for note in session.notes[-8:])
        fallback = notes_text or "\n".join(f"{entry.speaker}: {entry.text}" for entry in session.dialogueLog[-8:])
        if not fallback:
            fallback = "아직 정리할 조사 내용이 없습니다."
        summary = await self.ai_client.notes_summary(
            {"caseId": case.caseId, "sessionId": session.sessionId, "notes": [_dump(item) for item in session.notes]},
            fallback,
        )
        return {"sessionId": session.sessionId, "caseId": case.caseId, "summary": summary}

    async def get_hint(self, session_id: str) -> dict:
        session, case = self.load_session_and_case(session_id)
        fallback = self._static_hint(session, case)
        hint = await self.ai_client.hint(
            {
                "caseId": case.caseId,
                "sessionId": session.sessionId,
                "remainingQuestions": session.remainingQuestions,
                "discoveredContradictionIds": session.discoveredContradictionIds,
            },
            fallback,
        )
        return {"sessionId": session.sessionId, "caseId": case.caseId, "hint": hint}

    async def get_ending(self, session_id: str) -> dict:
        session, case = self.load_session_and_case(session_id)
        verdict = session.accusation["verdict"] if session.accusation else "incomplete"
        fallback = session.accusation["message"] if session.accusation else "아직 최종 지목이 제출되지 않았습니다."
        ending = await self.ai_client.ending(
            {
                "caseId": case.caseId,
                "sessionId": session.sessionId,
                "accusation": session.accusation,
                "usedQuestions": case.questionLimit - session.remainingQuestions,
            },
            fallback,
        )
        return {
            "sessionId": session.sessionId,
            "caseId": case.caseId,
            "verdict": verdict,
            "ending": ending,
            "accusation": session.accusation,
            "usedQuestions": case.questionLimit - session.remainingQuestions,
            "discoveredContradictionIds": session.discoveredContradictionIds,
        }

    def _allowed_statement_for_question(self, case: Case, question, fallback_answer: str) -> dict[str, str]:
        for statement_id in question.unlocksStatementIds:
            statement = next((item for item in case.statements if item.statementId == statement_id), None)
            if statement is not None:
                return {"id": statement.statementId, "text": statement.text}
        matching_statement = next(
            (
                item
                for item in case.statements
                if item.characterId == question.characterId and item.questionText == question.text
            ),
            None,
        )
        if matching_statement is not None:
            return {"id": matching_statement.statementId, "text": matching_statement.text}
        return {"id": f"answer_{question.questionId}", "text": fallback_answer}

    def _dialogue_tone(self, session: SessionState, suspect_id: str) -> str:
        state = pressure_state(session.pressureBySuspect.get(suspect_id, 0))
        if state == "broken":
            return "nervous"
        if state == "pressed":
            return "pressed"
        return "calm_defensive"

    def _static_hint(self, session: SessionState, case: Case) -> str:
        solution_ids = set(case.solution.requiredContradictionIds)
        missing = solution_ids.difference(session.discoveredContradictionIds)
        if "con_room_claim_vs_entry_log" in missing:
            return "한서연의 22:00 알리바이와 22:02 서재 출입 기록을 같은 시간대 단서로 비교해 보세요."
        if "con_inheritance_motive" in missing:
            return "상속 문제를 부인한 진술과 유언장 관련 물증을 연결하면 동기가 선명해집니다."
        return "필수 모순은 찾았습니다. 최종 지목에는 범인, 핵심 모순, 진술, 증거를 함께 제출하세요."

    def _log_verdict(
        self,
        message: str,
        request_context: RequestContext,
        session: SessionState,
        case: Case,
        suspect_id: str | None,
        verdict: str,
        started_at: float,
    ) -> None:
        logger.info(
            message,
            extra={
                "service": "backend",
                "request_id": request_context.request_id,
                "session_id": session.sessionId,
                "case_id": case.caseId,
                "route": request_context.route,
                "suspect_id": suspect_id,
                "verdict": verdict,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "fallback_used": False,
            },
        )

    def _log_debug_action(
        self,
        message: str,
        request_context: RequestContext,
        session: SessionState,
        case: Case,
        action: str,
        started_at: float,
    ) -> None:
        logger.info(
            message,
            extra={
                "service": "backend",
                "request_id": request_context.request_id,
                "session_id": session.sessionId,
                "case_id": case.caseId,
                "route": request_context.route,
                "event_type": "DEBUG_SESSION_UPDATED",
                "verdict": action,
                "duration_ms": int((time.perf_counter() - started_at) * 1000),
                "fallback_used": False,
            },
        )


def _dump(item) -> dict:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return item.dict()
