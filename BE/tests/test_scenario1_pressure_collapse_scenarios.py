from __future__ import annotations

import pytest

from app.core.leak_guard import assert_no_forbidden_refs
from tests.test_api_smoke import _client


ROBOTIC_DIALOGUE_MARKERS = (
    "표현을 바꾸면 이렇습니다",
    "그 얘기를 제게 돌리시려는 건가요",
    "쉽게 인정할 수는 없습니다",
    "그 단서와 제 진술을 어떻게 연결하시는지",
    "기록 기준으로는 같습니다",
    "의학적으로 다시 말씀드리면",
    "다시 확인드리면, 이미 답한 질문입니다",
)

VOICE_MARKERS_BY_SUSPECT = {
    "char_hanseoyeon": ("아니", "…", "웃기", "그게", "됐어", "뭘"),
    "char_yoonjaeho": ("회장님", "제가 본", "조심", "말씀", "집사", "그 시간"),
    "char_parkmingyu": ("기록", "처방", "의학", "소견", "책임", "약"),
    "char_choiyuna": ("일정", "기록", "확인", "회장님", "업무", "전화"),
}

BREAKDOWN_QUESTION_BY_SUSPECT = {
    "char_hanseoyeon": "q_hanseoyeon_breakdown",
    "char_yoonjaeho": "q_yoonjaeho_breakdown",
    "char_parkmingyu": "q_parkmingyu_breakdown",
    "char_choiyuna": "q_choiyuna_breakdown",
}

BREAKDOWN_MARKERS_BY_SUSPECT = {
    "char_hanseoyeon": ("무서웠", "거짓말", "회장님", "내가"),
    "char_yoonjaeho": ("숨겼", "회장님", "제가", "두려웠"),
    "char_parkmingyu": ("겁났", "기록", "책임", "제가"),
    "char_choiyuna": ("숨겼", "일정", "무서웠", "제가"),
}

BREAKDOWN_EVIDENCE_BY_SUSPECT = {
    "char_hanseoyeon": "ev_hanseoyeon_tremor_note",
    "char_yoonjaeho": "ev_yoonjaeho_folded_route_copy",
    "char_parkmingyu": "ev_parkmingyu_chart_backup",
    "char_choiyuna": "ev_choiyuna_shredded_schedule",
}


def _humanlike_flow_evaluation(transcript: list[dict]) -> dict:
    suspect_lines = [item for item in transcript if item["askedSuspect"] in VOICE_MARKERS_BY_SUSPECT]
    robotic_hits = [
        {"turn": item["turn"], "marker": marker, "answer": item["answer"]}
        for item in suspect_lines
        for marker in ROBOTIC_DIALOGUE_MARKERS
        if marker in item["answer"]
    ]
    exact_repeat_count = len(suspect_lines) - len({item["answer"] for item in suspect_lines})
    voice_hits = [
        item
        for item in suspect_lines
        if any(marker in item["answer"] for marker in VOICE_MARKERS_BY_SUSPECT[item["askedSuspect"]])
    ]
    pressure_reactions = [
        item
        for item in suspect_lines
        if item["targetStage"] in {"shaken", "resigned"}
        and any(token in item["answer"] for token in ("…", "잠깐", "그건", "하지만", "다만", "조심", "기록", "말"))
    ]
    return {
        "roboticHits": robotic_hits,
        "exactRepeatCount": exact_repeat_count,
        "voiceHitCount": len(voice_hits),
        "pressureReactionCount": len(pressure_reactions),
        "lineCount": len(suspect_lines),
        "passed": not robotic_hits
        and exact_repeat_count == 0
        and len(voice_hits) >= max(2, len(suspect_lines) // 2)
        and len(pressure_reactions) >= 2,
    }


SUSPECT_SCENARIOS = {
    "char_hanseoyeon": [
        ("char_hanseoyeon", "22:00에 어디 있었나요?"),
        ("char_hanseoyeon", "22시에 방에 있었다는 말은 서재 출입 기록과 모순입니다."),
        ("char_hanseoyeon", "그게 답이라고? 카드키 기록이 있는데 계속 회피하지 마."),
        ("char_hanseoyeon", "서재에 들어갔다면 무엇을 봤나요?"),
        ("char_yoonjaeho", "정전 당시 무엇을 했나요?"),
        ("char_hanseoyeon", "정전 기록과 부자연스러운 회중시계 파편은 현장 조작 가능성을 보여줍니다."),
        ("char_hanseoyeon", "그 시계랑 정전 이야기를 피하지 마. 네 말이 납득 안 돼."),
        ("char_hanseoyeon", "상속 문제로 다툰 적 있나요?"),
        ("char_hanseoyeon", "죽일 이유가 없다는 말은 찢어진 유언장과 모순입니다."),
        ("char_hanseoyeon", "유언장까지 나왔는데 아직 죽일 이유가 없다는 게 말이 된다고 생각해?"),
        ("char_hanseoyeon", "이제 버티지 말고, 서재에서 정말 숨긴 걸 말해."),
    ],
    "char_yoonjaeho": [
        ("char_yoonjaeho", "너는 22시 이후에 어디있었어?"),
        ("char_yoonjaeho", "22:10에 처음 봤다는 말은 집사 순찰 기록의 22:08 표시와 맞지 않습니다."),
        ("char_yoonjaeho", "그게 답이라고요? 순찰 기록 이야기를 회피하지 마세요."),
        ("char_yoonjaeho", "서재 열쇠 관리는 어떻게 됩니까?"),
        ("char_yoonjaeho", "서재 열쇠 진술은 열쇠 보관함 점검표의 22시 이후 반출 기록과 모순입니다."),
        ("char_yoonjaeho", "집사용 열쇠 반출 기록이 있는데 그 설명은 납득하기 어렵습니다."),
        ("char_yoonjaeho", "가족들 사이 분위기는 어땠나요?"),
        ("char_yoonjaeho", "가족 분위기를 모른 척했지만 가계 지출 메모에는 빚과 유언장 소문을 알고 있었다고 나옵니다."),
        ("char_yoonjaeho", "회장님을 모셨다면 더더욱 피하지 말고 숨긴 부분을 말해야 합니다."),
        ("char_yoonjaeho", "이제 회장님 일로 숨긴 걸 말해 주세요."),
    ],
    "char_parkmingyu": [
        ("char_parkmingyu", "22:00에 어디 있었나요?"),
        ("char_parkmingyu", "손님방 의료 기록은 21:45 이후 수정 흔적이 있는데 손님방에서 기록만 정리했다는 말과 모순입니다."),
        ("char_parkmingyu", "그게 답이라고요? 기록 수정 이야기를 계속 회피하지 마세요."),
        ("char_parkmingyu", "피해자의 약은 언제 확인했나요?"),
        ("char_parkmingyu", "약 상자는 21:30 복용분 이후 책임을 좁혀 말한 박민규의 진술과 맞지 않습니다."),
        ("char_parkmingyu", "약 기록과 책임 범위를 나눠 말하는 건 납득이 안 됩니다."),
        ("char_parkmingyu", "피해자와 다툼은 없었나요?"),
        ("char_parkmingyu", "처방 변경 메모는 다툼이 아니었다는 말과 모순입니다."),
        ("char_parkmingyu", "처방 변경 메모까지 있는데 아직 감정적 충돌이 아니었다는 게 말이 됩니까?"),
        ("char_parkmingyu", "이제 기록 뒤에 숨긴 책임을 말해 주세요."),
    ],
    "char_choiyuna": [
        ("char_choiyuna", "피해자와 마지막으로 연락한 때는?"),
        ("char_choiyuna", "통화 기록은 통화를 축소했다는 말과 모순입니다."),
        ("char_choiyuna", "그게 답인가요? 통화 내용을 줄여 말한 이유를 회피하지 마세요."),
        ("char_choiyuna", "비밀 일정이 있었나요?"),
        ("char_choiyuna", "비서 일정 메모에는 가족에게 보류하라는 내용이 있는데 단순 지시였다는 말과 맞지 않습니다."),
        ("char_choiyuna", "가족에게 숨기라는 일정까지 알고 있었는데 단순 지시였다는 건 납득이 안 됩니다."),
        ("char_choiyuna", "서재의 와인잔을 알고 있나요?"),
        ("char_choiyuna", "립스틱 케이스는 와인과 립스틱 색이 제 것이 아니라는 말과 모순입니다."),
        ("char_choiyuna", "일정, 통화, 립스틱 케이스가 이어지는데 계속 피하지 마세요."),
        ("char_choiyuna", "이제 일정과 서재 주변에서 숨긴 걸 말해 주세요."),
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
    target_turns = [item for item in transcript if item["askedSuspect"] == target_suspect_id]
    assert len(target_turns) >= 10, transcript
    final_target_turn = next(item for item in reversed(transcript) if item["askedSuspect"] == target_suspect_id)
    assert final_target_turn["matchedQuestionId"] == BREAKDOWN_QUESTION_BY_SUSPECT[target_suspect_id], transcript
    assert any(marker in final_target_turn["answer"] for marker in BREAKDOWN_MARKERS_BY_SUSPECT[target_suspect_id]), final_target_turn
    assert any(item["evidenceId"] == BREAKDOWN_EVIDENCE_BY_SUSPECT[target_suspect_id] for item in reloaded["evidence"])
    evaluation = _humanlike_flow_evaluation(transcript)
    print(f"\n[HUMANLIKE-EVAL] target={target_suspect_id} {evaluation}")
    assert evaluation["passed"], evaluation
    assert_no_forbidden_refs(reloaded, surface=f"collapse_probe_{target_suspect_id}")
