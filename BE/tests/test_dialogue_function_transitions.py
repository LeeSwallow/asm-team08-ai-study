from __future__ import annotations

from app.ai_engine.agents.character_agent import render_dialogue_seed
from app.ai_engine.agents.dialogue_director_agent import DialogueDirectorAgent
from app.ai_engine.schemas.agents import DialogueDirectorInput
from app.ai_engine.schemas.dialogue import DialogueRequest


def _dialogue_request(*, mode: str, message: str) -> DialogueRequest:
    return DialogueRequest.model_validate(
        {
            "requestId": "req_test",
            "sessionId": "sess_test",
            "caseId": "case_001",
            "dialogueMode": mode,
            "suspect": {
                "id": "char_hanseoyeon",
                "name": "한서연",
                "pressureState": "calm",
                "emotionalState": "neutral",
            },
            "question": {"id": f"player_{mode}", "text": message},
            "allowedStatement": {
                "id": f"neutral_{mode}",
                "text": "공개된 범위에서는 한서연의 당일 행적과 관계만 다룬다.",
                "sourceRefs": {"statementIds": [], "timelineIds": [], "evidenceIds": []},
            },
            "style": {"tone": "tense", "maxLength": 220},
            "revealAllowed": False,
        }
    )


def test_unmatched_turn_uses_function_transition_instead_of_static_fallback() -> None:
    payload = _dialogue_request(mode="unmatched", message="저택 밖 소문은 전부 사실인가요?")

    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))
    seed = render_dialogue_seed(payload, plan)

    assert plan.strategy == "deflect_unmatched"
    assert plan.functionCall is not None
    assert plan.functionCall["name"] == "deflect_unmatched_turn"
    assert plan.functionCall["transferTo"] == "CharacterAgent"
    assert seed != "그 질문에는 바로 답하기 어렵습니다."
    assert "단정" in seed or "진술" in seed or "확인" in seed


def test_small_talk_turn_has_persona_boundary_function_transition() -> None:
    payload = _dialogue_request(mode="small_talk", message="안녕하세요, 잠깐 얘기해도 되죠?")

    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))
    seed = render_dialogue_seed(payload, plan)

    assert plan.strategy == "small_talk_boundary"
    assert plan.functionCall is not None
    assert plan.functionCall["name"] == "handle_small_talk_boundary"
    assert seed != "저는 한서연입니다."
    assert "사건" in seed or "기억" in seed or "상황" in seed
