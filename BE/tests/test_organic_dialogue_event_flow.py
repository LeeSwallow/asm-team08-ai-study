from __future__ import annotations

import pytest

from app.application.dialogue_service import DialogueService
from app.domain.event_types import EventType
from tests.test_api_smoke import _client


SUSPECT_DIALOGUE_MESSAGES = {
    "char_hanseoyeon": [
        "22:00에 어디 있었나요?",
        "상속 문제로 다툰 적 있나요?",
        "서재의 와인잔을 알고 있나요?",
        "22:02 서재 출입 기록을 설명해 주세요.",
    ],
    "char_yoonjaeho": [
        "피해자를 언제 발견했나요?",
        "정전 당시 무엇을 했나요?",
        "유언장 변경 사실을 알고 있었나요?",
        "서재 열쇠 관리는 어떻게 됩니까?",
        "가족들 사이 분위기는 어땠나요?",
    ],
    "char_parkmingyu": [
        "22:00에 어디 있었나요?",
        "피해자의 약은 언제 확인했나요?",
        "피해자와 다툼은 없었나요?",
    ],
    "char_choiyuna": [
        "피해자와 마지막으로 연락한 때는?",
        "비밀 일정이 있었나요?",
        "서재의 와인잔을 알고 있나요?",
    ],
}

SUSPECT_NAMES = {
    "char_hanseoyeon": "한서연",
    "char_yoonjaeho": "윤재호",
    "char_parkmingyu": "박민규",
    "char_choiyuna": "최윤아",
}


def _post_dialogue(client, session_id: str, suspect_id: str, message: str):
    return client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": suspect_id, "message": message},
    )


def test_hanseoyeon_polish_keeps_generated_dialogue_in_banmal():
    service = DialogueService.__new__(DialogueService)

    polished = service._polish_answer("아니… 제 방에 있었습니다. 그게 왜 문제죠?", "한서연")

    assert polished == "아니… 제 방에 있어. 그게 왜 문제야?"
    assert "습니다" not in polished
    assert "죠" not in polished


def test_yoonjaeho_free_text_relationship_and_after_22_questions_are_contextual(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    relationship = _post_dialogue(client, session_id, "char_yoonjaeho", "너랑 회장님이랑 어떤 관계지?").json()
    print("\n[YOO-FREETEXT] relationship:", relationship["answer"])
    assert relationship["dialogueResult"]["consumedQuestion"] is True
    assert relationship["dialogueResult"]["matchedQuestionId"] == "q_yoonjaeho_victim_relation"
    assert "30년" in relationship["answer"] or "모신" in relationship["answer"]
    assert "사건과 관련된 것만" not in relationship["answer"]
    assert any(item["relationshipId"] == "rel_yoonjaeho_loyalty" for item in relationship["relations"])

    vague = _post_dialogue(client, session_id, "char_yoonjaeho", "뭐야?").json()
    print("[YOO-FREETEXT] vague:", vague["answer"])
    assert vague["dialogueResult"]["consumedQuestion"] is False
    assert vague["dialogueResult"]["matchedQuestionId"] is None
    assert vague["remainingQuestions"] == relationship["remainingQuestions"]
    assert "어떤 시간을" not in vague["answer"]
    assert "어떤 증거" not in vague["answer"]

    after_22 = _post_dialogue(client, session_id, "char_yoonjaeho", "너는 22시 이후에 어디있었어?").json()
    print("[YOO-FREETEXT] after_22:", after_22["answer"])
    assert after_22["dialogueResult"]["consumedQuestion"] is True
    assert after_22["dialogueResult"]["matchedQuestionId"] == "q_yoonjaeho_discovery"
    assert "22:10" in after_22["answer"] or "서재" in after_22["answer"]
    assert "그런 이야기를 나눌 상황" not in after_22["answer"]


@pytest.mark.parametrize("suspect_id", sorted(SUSPECT_DIALOGUE_MESSAGES))
def test_each_suspect_has_a_stable_12_turn_dialogue_budget_and_exhaustion_nudge(
    tmp_path,
    monkeypatch,
    suspect_id: str,
):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]
    messages = SUSPECT_DIALOGUE_MESSAGES[suspect_id]

    print(f"\n[DIALOGUE-PROBE] suspect={SUSPECT_NAMES[suspect_id]}({suspect_id})")

    for turn in range(1, 13):
        player_message = messages[(turn - 1) % len(messages)]
        response = _post_dialogue(client, session_id, suspect_id, player_message)
        assert response.status_code == 200, response.text
        payload = response.json()
        dialogue = payload["dialogueResult"]
        event_types = [event["type"] for event in payload.get("appliedEvents", [])]
        print(
            f"  turn={turn:02d} remaining={payload['remainingQuestions']:02d} "
            f"mode={dialogue['dialogueMode']} helper={payload['helperSuggestion']['helperRoute']} events={event_types}\n"
            f"    player: {player_message}\n"
            f"    {SUSPECT_NAMES[suspect_id]}: {payload['answer']}"
        )
        assert dialogue["consumedQuestion"] is True
        assert dialogue["previousRemainingQuestions"] == 13 - turn
        assert dialogue["remainingQuestions"] == 12 - turn
        assert dialogue["remainingQuestionsDelta"] == -1
        assert payload["remainingQuestions"] == 12 - turn
        assert len(payload["dialogueLog"]) == turn * 2
        assert payload["answer"].strip()
        expected_helper_route = "silent" if turn < 12 else "nudge_accusation_ready"
        assert payload["helperSuggestion"]["helperRoute"] == expected_helper_route
        if suspect_id == "char_hanseoyeon":
            assert "습니다" not in payload["answer"]
            assert "어요" not in payload["answer"]
        assert "다시 정리하면, 이미 답한 질문입니다" not in payload["answer"]
        assert "앞서 말한 내용과 같지만, 같은 질문에 다시 답하자면" not in payload["answer"]

    exhausted = _post_dialogue(client, session_id, suspect_id, messages[0])
    assert exhausted.status_code == 400
    assert exhausted.json()["detail"] == "QUESTION_LIMIT_EXHAUSTED"

    reloaded = client.get(f"/api/v1/sessions/{session_id}").json()
    assert reloaded["remainingQuestions"] == 0
    assert reloaded["helperSuggestion"]["helperRoute"] == "nudge_accusation_ready"
    assert reloaded["helperSuggestion"]["suggestedActions"]


def test_dialogue_events_progress_organically_from_statement_to_unlock_to_contradiction_and_tension(
    tmp_path,
    monkeypatch,
):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    first = _post_dialogue(client, session_id, "char_hanseoyeon", "22:00에 어디 있었나요?").json()
    first_types = {event["type"] for event in first["appliedEvents"]}
    assert EventType.NOTE_FACT_ADDED.value in first_types
    assert EventType.VISUAL_STATE_CHANGED.value in first_types
    assert first["dialogueResult"]["matchedRefs"]["statementIds"] == ["st_hanseoyeon_room_2200"]

    yoon = _post_dialogue(client, session_id, "char_yoonjaeho", "정전 당시 무엇을 했나요?").json()
    yoon_types = {event["type"] for event in yoon["appliedEvents"]}
    assert EventType.NOTE_FACT_ADDED.value in yoon_types
    assert EventType.EVIDENCE_UNLOCKED.value not in yoon_types
    assert any(item["evidenceId"] == "ev_storm_blackout" for item in yoon["evidence"])

    secretary = _post_dialogue(client, session_id, "char_choiyuna", "피해자와 마지막으로 연락한 때는?").json()
    secretary_types = {event["type"] for event in secretary["appliedEvents"]}
    assert EventType.EVIDENCE_UNLOCKED.value in secretary_types
    assert EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value not in secretary_types
    assert EventType.TENSION_CHANGED.value not in secretary_types
    assert secretary["contradictionResult"] is None

    pressure = _post_dialogue(
        client,
        session_id,
        "char_hanseoyeon",
        "22시에 방에 있었다는 말은 서재 출입 기록과 모순입니다.",
    ).json()
    pressure_types = {event["type"] for event in pressure["appliedEvents"]}
    assert EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value in pressure_types
    assert EventType.TENSION_CHANGED.value in pressure_types
    assert EventType.VISUAL_STATE_CHANGED.value in pressure_types
    assert pressure["contradictionResult"]["contradictionId"] == "con_room_claim_vs_entry_log"
    assert pressure["pressureBySuspect"]["char_hanseoyeon"] >= 20
    assert pressure["disclosureLadders"]
    han_ladder = next(item for item in pressure["disclosureLadders"] if item["suspectId"] == "char_hanseoyeon")
    assert han_ladder["currentStage"] in {"defensive", "shaken", "resigned"}

    with client.stream("GET", f"/api/v1/sessions/{session_id}/events?once=true") as stream:
        sse_text = stream.read().decode()
    for event_name in [
        EventType.NOTE_FACT_ADDED.value,
        EventType.EVIDENCE_UNLOCKED.value,
        EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value,
        EventType.TENSION_CHANGED.value,
        EventType.VISUAL_STATE_CHANGED.value,
    ]:
        assert event_name in sse_text
