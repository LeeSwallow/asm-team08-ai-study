from __future__ import annotations

import pytest

from app.core.leak_guard import assert_no_forbidden_refs
from tests.test_api_smoke import _client


SUSPECT_SCENARIOS = {
    "char_hanseoyeon": [
        ("char_hanseoyeon", "22:00에 어디 있었나요?"),
        ("char_hanseoyeon", "22시에 방에 있었다는 말은 서재 출입 기록과 모순입니다."),
        ("char_hanseoyeon", "서재에 들어갔다면 무엇을 봤나요?"),
        ("char_yoonjaeho", "정전 당시 무엇을 했나요?"),
        ("char_hanseoyeon", "정전 기록과 부자연스러운 회중시계 파편은 현장 조작 가능성을 보여줍니다."),
        ("char_hanseoyeon", "상속 문제로 다툰 적 있나요?"),
        ("char_hanseoyeon", "죽일 이유가 없다는 말은 찢어진 유언장과 모순입니다."),
    ],
    "char_yoonjaeho": [
        ("char_yoonjaeho", "너는 22시 이후에 어디있었어?"),
        ("char_yoonjaeho", "22:10에 처음 봤다는 말은 집사 순찰 기록의 22:08 표시와 맞지 않습니다."),
        ("char_yoonjaeho", "서재 열쇠 관리는 어떻게 됩니까?"),
        ("char_yoonjaeho", "서재 열쇠 진술은 열쇠 보관함 점검표의 22시 이후 반출 기록과 모순입니다."),
        ("char_yoonjaeho", "가족들 사이 분위기는 어땠나요?"),
        ("char_yoonjaeho", "가족 분위기를 모른 척했지만 가계 지출 메모에는 빚과 유언장 소문을 알고 있었다고 나옵니다."),
    ],
    "char_parkmingyu": [
        ("char_parkmingyu", "22:00에 어디 있었나요?"),
        ("char_parkmingyu", "손님방 의료 기록은 21:45 이후 수정 흔적이 있는데 손님방에서 기록만 정리했다는 말과 모순입니다."),
        ("char_parkmingyu", "피해자의 약은 언제 확인했나요?"),
        ("char_parkmingyu", "약 상자는 21:30 복용분 이후 책임을 좁혀 말한 박민규의 진술과 맞지 않습니다."),
        ("char_parkmingyu", "피해자와 다툼은 없었나요?"),
        ("char_parkmingyu", "처방 변경 메모는 다툼이 아니었다는 말과 모순입니다."),
    ],
    "char_choiyuna": [
        ("char_choiyuna", "피해자와 마지막으로 연락한 때는?"),
        ("char_choiyuna", "통화 기록은 통화를 축소했다는 말과 모순입니다."),
        ("char_choiyuna", "비밀 일정이 있었나요?"),
        ("char_choiyuna", "비서 일정 메모에는 가족에게 보류하라는 내용이 있는데 단순 지시였다는 말과 맞지 않습니다."),
        ("char_choiyuna", "서재의 와인잔을 알고 있나요?"),
        ("char_choiyuna", "립스틱 케이스는 와인과 립스틱 색이 제 것이 아니라는 말과 모순입니다."),
    ],
}


@pytest.mark.parametrize("target_suspect_id", sorted(SUSPECT_SCENARIOS))
def test_scenario1_user_pressure_script_can_break_each_suspect_to_resigned_stage(
    tmp_path,
    monkeypatch,
    target_suspect_id: str,
):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]
    transcript = []
    latest = session

    for turn, (suspect_id, message) in enumerate(SUSPECT_SCENARIOS[target_suspect_id], start=1):
        response = client.post(
            f"/api/v1/sessions/{session_id}/dialogue",
            json={"suspectId": suspect_id, "message": message},
        )
        assert response.status_code == 200, response.text
        latest = response.json()
        dialogue = latest["dialogueResult"]
        target_ladder = next(item for item in latest["disclosureLadders"] if item["suspectId"] == target_suspect_id)
        event_types = [event["type"] for event in latest.get("appliedEvents", [])]
        transcript.append(
            {
                "turn": turn,
                "askedSuspect": suspect_id,
                "message": message,
                "answer": latest["answer"],
                "mode": dialogue["dialogueMode"],
                "matchedQuestionId": dialogue["matchedQuestionId"],
                "contradiction": (latest.get("contradictionResult") or {}).get("contradictionId"),
                "events": event_types,
                "targetPressure": latest["pressureBySuspect"].get(target_suspect_id),
                "targetStage": target_ladder["currentStage"],
                "remaining": latest["remainingQuestions"],
            }
        )
        print(f"\n[COLLAPSE-PROBE] target={target_suspect_id} turn={turn} stage={target_ladder['currentStage']} pressure={latest['pressureBySuspect'].get(target_suspect_id)}")
        print(f"  player->{suspect_id}: {message}")
        print(f"  answer: {latest['answer']}")

    reloaded = client.get(f"/api/v1/sessions/{session_id}").json()
    final_ladder = next(item for item in reloaded["disclosureLadders"] if item["suspectId"] == target_suspect_id)

    assert final_ladder["currentStage"] == "resigned", transcript
    assert reloaded["pressureBySuspect"][target_suspect_id] >= 80
    assert [stage["stage"] for stage in final_ladder["stages"]] == ["guarded", "defensive", "shaken", "resigned"]
    assert_no_forbidden_refs(reloaded, surface=f"collapse_probe_{target_suspect_id}")
