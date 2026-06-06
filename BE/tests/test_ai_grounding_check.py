from app.ai_engine.application.grounding_check_agent import GroundingCheckAgent
from app.ai_engine.schemas.agents import CheckedCharacterReply
from app.ai_engine.schemas.dialogue import DialogueRequest


def _payload(question: str, statement: str, dialogue_mode: str = "case_question") -> DialogueRequest:
    return DialogueRequest.model_validate(
        {
            "sessionId": "session_grounding",
            "caseId": "case_001",
            "dialogueMode": dialogue_mode,
            "suspect": {"id": "char_test", "name": "테스트"},
            "question": {"id": "q_test", "text": question},
            "allowedStatement": {
                "id": "st_test",
                "text": statement,
                "sourceRefs": {"statementIds": ["st_test"], "questionIds": ["q_test"]},
            },
            "allowedEventPolicy": {
                "relatedStatementIds": ["st_test"],
                "relatedQuestionIds": ["q_test"],
            },
        }
    )


def _reply(text: str) -> CheckedCharacterReply:
    return CheckedCharacterReply(
        finalText=text,
        provider="upstage",
        model="solar-pro",
        safetyFindings={"repaired": False, "blocked": False, "finalTextSource": "provider"},
    )


def test_grounding_check_repairs_missing_answer_and_unsupported_claim() -> None:
    payload = _payload(
        "피해자를 언제 발견했나요?",
        "22:10쯤 서재 문이 열려 있는 걸 보고 발견했습니다.",
    )

    result = GroundingCheckAgent().run(
        payload,
        _reply("서재 문은 평소처럼 닫혀 있어야 이상했죠."),
    )

    assert result.repaired is True
    assert result.checked_reply.finalText == payload.allowedStatement.text
    assert "required_anchor_claim_missing" in result.issues
    assert "claim:door_closed" in result.unsupported_facts


def test_grounding_check_repairs_new_concrete_actions_even_with_anchor_overlap() -> None:
    payload = _payload(
        "그 말이 납득된다고 생각합니까?",
        "22:10쯤 서재 문이 열려 있는 걸 보고 발견했습니다.",
        dialogue_mode="pressure_followup",
    )

    result = GroundingCheckAgent().run(
        payload,
        _reply("22시 10분께 서재에서 자료를 정리하다 문을 열어둔 채 자리를 비웠습니다."),
    )

    assert result.repaired is True
    assert {"claim:organize_materials", "claim:open_door", "claim:leave"} <= set(result.unsupported_facts)


def test_grounding_check_keeps_registered_false_alibi_and_emotional_flair() -> None:
    payload = _payload(
        "밤 10시쯤 어디 있었죠?",
        "저는 22:00에 제 방에 있었어요.",
        dialogue_mode="timeline_question",
    )
    answer = "사실은 그날 밤 10시쯤 제 방에 있었어요. 사업 실패 이후 잠도 제대로 못 잤고요."

    result = GroundingCheckAgent().run(payload, _reply(answer))

    assert result.checked is True
    assert result.repaired is False
    assert result.checked_reply.finalText == answer


def test_grounding_check_keeps_grounded_natural_paraphrase() -> None:
    payload = _payload(
        "피해자가 먹던 약은 언제 확인했죠?",
        "21:30 복용분까지 확인했고 이후에는 손대지 않았습니다.",
        dialogue_mode="evidence_question",
    )
    answer = "21시 30분까지 약을 확인했고, 그 뒤로는 손대지 않았습니다."

    result = GroundingCheckAgent().run(payload, _reply(answer))

    assert result.checked is True
    assert result.repaired is False
    assert result.checked_reply.finalText == answer


def test_grounding_check_does_not_treat_question_location_as_allowed_alibi() -> None:
    payload = _payload(
        "서재에 있었나요?",
        "네, 저는 그날 와인을 마시지 않았습니다.",
        dialogue_mode="evidence_question",
    )

    result = GroundingCheckAgent().run(payload, _reply("네, 그날 서재에 있었습니다."))

    assert result.repaired is True
    assert "location_claim:study" in result.unsupported_facts
    assert result.diagnostics()["basis"] == "allowed_statement_claim"
    assert result.diagnostics()["repairReason"] == "claim_grounding_repaired"
    assert result.diagnostics()["finalTextSource"] == "public_seed_after_claim_grounding"


def test_grounding_check_keeps_non_assertive_location_mention() -> None:
    payload = _payload(
        "서재의 와인잔을 알고 있나요?",
        "네, 저는 그날 와인을 마시지 않았습니다. 립스틱 색도 제 것이 아닙니다.",
        dialogue_mode="evidence_question",
    )
    answer = "서재의 와인잔 말씀이라면, 저는 그날 와인을 마시지 않았습니다. 립스틱 색도 제 것이 아닙니다."

    result = GroundingCheckAgent().run(payload, _reply(answer))

    assert result.checked is True
    assert result.repaired is False
    assert result.checked_reply.finalText == answer
