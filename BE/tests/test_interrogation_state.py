from app.domain.interrogation_state import transition_interrogation_state, pressure_for_stage
from app.domain.models import Case, Character, Evidence, SessionState, Solution, Statement, Question


def _minimal_case() -> Case:
    return Case(
        caseId="case_test",
        sceneId="scene_test",
        title="test",
        summary="test",
        victimId="victim",
        victimName="피해자",
        incidentTime="22:00",
        incidentLocation="서재",
        questionLimit=30,
        suspects=[
            Character(
                characterId="char_hanseoyeon",
                name="한서연",
                role="용의자",
                publicProfile="공개 프로필",
            )
        ],
        evidence=[
            Evidence(
                evidenceId="ev_study_entry_log",
                name="서재 출입 기록",
                type="record",
                description="22:02에 한서연의 카드키 출입 기록이 남아 있다.",
                foundAt="보안 시스템",
                timeWindow="22:02",
                reliability=0.95,
                initiallyVisible=True,
            )
        ],
        statements=[
            Statement(
                statementId="st_hanseoyeon_room_2200",
                characterId="char_hanseoyeon",
                questionText="22:00에 어디 있었나요?",
                text="22:00에는 방에 있었어.",
                initiallyVisible=True,
            )
        ],
        questions=[
            Question(
                questionId="q_hanseoyeon_study_entry",
                characterId="char_hanseoyeon",
                text="22:02 서재 출입 기록을 설명해 주세요.",
                answer="전산 오류일 수도 있어.",
                initiallyUnlocked=True,
            )
        ],
        contradictions=[],
        solution=Solution(
            culpritId="char_hanseoyeon",
            motive="test",
            method="test",
            requiredContradictionIds=[],
            requiredEvidenceIds=[],
            requiredStatementIds=[],
            endings={"correct":"ok","partial":"partial","wrong":"wrong"},
        ),
    )


def test_authored_case_question_that_mentions_visible_evidence_raises_deflection_pressure():
    case = _minimal_case()
    session = SessionState(
        sessionId="sess_test",
        caseId=case.caseId,
        remainingQuestions=30,
        selectedSuspectId="char_hanseoyeon",
        unlockedEvidenceIds=["ev_study_entry_log"],
        unlockedStatementIds=["st_hanseoyeon_room_2200"],
        unlockedQuestionIds=["q_hanseoyeon_study_entry"],
        pressureBySuspect={"char_hanseoyeon": 0},
    )

    transition = transition_interrogation_state(
        case=case,
        session=session,
        suspect_id="char_hanseoyeon",
        dialogue_mode="case_question",
        consumed_question=True,
        player_message="22:02 서재 출입 기록을 설명해 주세요.",
        allowed_statement={"id": "answer_q_hanseoyeon_study_entry", "text": "전산 오류일 수도 있어.", "sourceRefs": {}},
        allowed_event_policy={"relatedContradictionIds": [], "relatedStatementIds": [], "relatedEvidenceIds": []},
    )

    assert transition.move == "present_evidence"
    assert transition.evidence_ids == ["ev_study_entry_log"]
    assert transition.reason == "non_decisive_evidence_presented"
    assert transition.pressure_delta == pressure_for_stage("deflection")
    assert session.pressureBySuspect["char_hanseoyeon"] == pressure_for_stage("deflection")
