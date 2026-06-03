from typing import List

from app.domain.case_engine import apply_unlocks
from app.domain.interrogation_state import pressure_for_stage, stage_from_contradictions
from app.domain.models import Case, SessionState


class RuleEngine:
    def answer_question(self, session: SessionState, case: Case, question_id: str) -> dict:
        question = next((item for item in case.questions if item.questionId == question_id), None)
        if question is None:
            raise ValueError("QUESTION_NOT_FOUND")
        if question_id not in session.unlockedQuestionIds:
            raise ValueError("QUESTION_LOCKED")
        if session.remainingQuestions <= 0:
            raise ValueError("QUESTION_LIMIT_EXHAUSTED")

        previous_count = session.askedQuestionCounts.get(question_id, 0)
        repeated = previous_count > 0
        session.remainingQuestions -= 1
        session.askedQuestionCounts[question_id] = previous_count + 1
        session.selectedSuspectId = question.characterId
        newly_unlocked: List[str] = []
        if not repeated:
            unlock_ids = [
                *question.unlocksStatementIds,
                *question.unlocksEvidenceIds,
                *question.unlocksRecordIds,
                *question.unlocksRelationIds,
            ]
            newly_unlocked = apply_unlocks(session, case, unlock_ids)
        else:
            session.newlyUnlockedIds = []
        answer = question.answer
        if repeated:
            repeat_prefixes = (
                "이미 답한 질문입니다.",
                "같은 질문에 다시 답하자면,",
                "방금 확인한 내용과 같습니다.",
            )
            answer = f"{repeat_prefixes[(previous_count - 1) % len(repeat_prefixes)]} {question.answer}"
        return {
            "answer": answer,
            "newlyUnlockedIds": newly_unlocked,
            "repeated": repeated,
            "askCount": session.askedQuestionCounts[question_id],
        }

    def judge_contradiction(
        self,
        session: SessionState,
        case: Case,
        statement_ids: List[str],
        evidence_ids: List[str],
        suspect_id: str | None = None,
    ) -> dict:
        available_statements = set(session.unlockedStatementIds)
        available_evidence = set(session.unlockedEvidenceIds)
        submitted_statements = set(statement_ids)
        submitted_evidence = set(evidence_ids)

        best_partial = None
        best_insufficient = None
        for contradiction in case.contradictions:
            required_statements = set(contradiction.requiredStatementIds)
            required_evidence = set(contradiction.requiredEvidenceIds)
            if not required_statements.issubset(available_statements):
                continue
            if not required_evidence.issubset(available_evidence):
                continue

            statement_match = required_statements.issubset(submitted_statements)
            evidence_match = required_evidence.issubset(submitted_evidence)
            suspect_match = suspect_id in (None, contradiction.relatedCharacterId)

            if statement_match and evidence_match and suspect_match:
                newly_discovered = contradiction.contradictionId not in session.discoveredContradictionIds
                pressure_delta = 0
                if contradiction.contradictionId not in session.discoveredContradictionIds:
                    session.discoveredContradictionIds.append(contradiction.contradictionId)
                    current = session.pressureBySuspect.get(contradiction.relatedCharacterId, 0)
                    stage = stage_from_contradictions(case, session, contradiction.relatedCharacterId)
                    updated = max(current, pressure_for_stage(stage))
                    session.pressureBySuspect[contradiction.relatedCharacterId] = updated
                    pressure_delta = updated - current
                newly_unlocked = apply_unlocks(session, case, contradiction.unlockedIds)
                return {
                    "verdict": "correct",
                    "contradictionId": contradiction.contradictionId,
                    "reasonCode": contradiction.reasonCode,
                    "pressureDelta": pressure_delta,
                    "unlockedIds": newly_unlocked,
                    "newlyDiscovered": newly_discovered,
                    "statementIds": list(contradiction.requiredStatementIds),
                    "evidenceIds": list(contradiction.requiredEvidenceIds),
                    "message": contradiction.message,
                }

            overlap = submitted_statements.intersection(required_statements) or submitted_evidence.intersection(required_evidence)
            if overlap and suspect_match and best_partial is None:
                best_partial = contradiction
            elif suspect_id is not None and suspect_match and best_insufficient is None:
                best_insufficient = contradiction

        session.newlyUnlockedIds = []
        if best_partial:
            return {
                "verdict": "partial",
                "contradictionId": best_partial.contradictionId,
                "reasonCode": "related_but_incomplete",
                "pressureDelta": 0,
                "unlockedIds": [],
                "newlyDiscovered": False,
                "statementIds": list(submitted_statements),
                "evidenceIds": list(submitted_evidence),
                "message": "방향은 맞지만 필요한 진술과 증거가 모두 연결되지 않았습니다.",
            }

        if best_insufficient:
            return {
                "verdict": "insufficient",
                "contradictionId": best_insufficient.contradictionId,
                "reasonCode": "weak_connection",
                "pressureDelta": 0,
                "unlockedIds": [],
                "newlyDiscovered": False,
                "statementIds": list(submitted_statements),
                "evidenceIds": list(submitted_evidence),
                "message": "관련 인물은 맞지만 제시한 근거만으로는 모순을 입증하기 어렵습니다.",
            }

        return {
            "verdict": "wrong",
            "contradictionId": None,
            "reasonCode": "no_rule_match",
            "pressureDelta": 0,
            "unlockedIds": [],
            "newlyDiscovered": False,
            "statementIds": list(submitted_statements),
            "evidenceIds": list(submitted_evidence),
            "message": "제시한 조합에서는 판정 가능한 모순을 찾지 못했습니다.",
        }

    def judge_accusation(
        self,
        session: SessionState,
        case: Case,
        suspect_id: str,
        evidence_ids: List[str],
        contradiction_ids: List[str],
        statement_ids: List[str],
        motive: str | None = None,
        method: str | None = None,
    ) -> dict:
        solution = case.solution
        suspect_match = suspect_id == solution.culpritId
        required_evidence = set(solution.requiredEvidenceIds)
        required_contradictions = set(solution.requiredContradictionIds)
        required_statements = set(solution.requiredStatementIds)

        evidence_ok = required_evidence.issubset(set(evidence_ids))
        contradictions_ok = required_contradictions.issubset(set(contradiction_ids))
        statements_ok = required_statements.issubset(set(statement_ids))
        proof_complete = evidence_ok and contradictions_ok and statements_ok

        if suspect_match and proof_complete:
            verdict = "correct"
            session.phase = "solved"
            message = solution.endings["correct"]
        elif suspect_match:
            verdict = "partial"
            session.phase = "accusation"
            message = solution.endings["partial"]
        else:
            verdict = "wrong"
            session.phase = "failed"
            message = solution.endings["wrong"]

        result = {
            "verdict": verdict,
            "correct": verdict == "correct",
            "submittedMotive": motive,
            "submittedMethod": method,
            "message": message,
        }
        session.accusation = result
        session.selectedSuspectId = suspect_id
        session.newlyUnlockedIds = []
        return result


def _canonical_attempt_key(
    contradiction_id: str,
    suspect_id: str | None,
    statement_ids: List[str],
    evidence_ids: List[str],
) -> str:
    statements = ",".join(sorted(set(statement_ids)))
    evidence = ",".join(sorted(set(evidence_ids)))
    return f"{contradiction_id}|{suspect_id or ''}|s:{statements}|e:{evidence}"
