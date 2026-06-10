import json
from pathlib import Path

from app.core.leak_guard import assert_no_forbidden_refs
from app.domain.case_engine import initial_session_state, public_disclosure_ladders, public_helper_suggestion, visible_session_payload
from app.domain.models import Case, DialogueEntry


def _case():
    payload = json.loads(Path("data/cases/case_001.json").read_text(encoding="utf-8"))
    return Case.model_validate(payload)


def test_scenario1_public_disclosure_ladders_cover_every_suspect_and_resigned_stage():
    case = _case()
    session = initial_session_state(case, "test_session")
    ladders = public_disclosure_ladders(case, session)

    assert {item["suspectId"] for item in ladders} == {suspect.characterId for suspect in case.suspects}
    for ladder in ladders:
        assert ladder["currentStage"] == "guarded"
        assert [stage["stage"] for stage in ladder["stages"]] == ["guarded"]
        assert all("isCulprit" not in str(stage) and "secret" not in str(stage).lower() for stage in ladder["stages"])

    for suspect in case.suspects:
        session.pressureBySuspect[suspect.characterId] = 85
    resigned_ladders = public_disclosure_ladders(case, session)
    assert all(ladder["currentStage"] == "resigned" for ladder in resigned_ladders)
    assert all([stage["stage"] for stage in ladder["stages"]] == ["guarded", "defensive", "shaken", "resigned"] for ladder in resigned_ladders)
    serialized = str(resigned_ladders)
    semantic_leak_terms = ["정전", "조작", "최종 고발", "레드헤링", "살해", "범인 후보"]
    assert all(term not in serialized for term in semantic_leak_terms)


def test_visible_session_payload_exposes_public_pressure_gates_and_silent_helper_contract():
    case = _case()
    session = initial_session_state(case, "test_session")

    payload = visible_session_payload(session, case)

    assert payload["disclosureLadders"]
    assert payload["pressureGates"]["stages"] == ["guarded", "defensive", "shaken", "resigned"]
    assert "thresholds" not in payload["pressureGates"]
    assert "범인" not in str(payload["pressureGates"])
    assert payload["helperSuggestion"]["helperRoute"] == "silent"
    assert payload["helperSuggestion"]["suggestedActions"] == []
    assert_no_forbidden_refs(payload, surface="scenario1_public_session_payload")


def test_helper_suggestion_nudges_after_repeated_stuck_reaction_routes_without_private_leaks():
    case = _case()
    session = initial_session_state(case, "test_session")
    session.selectedSuspectId = "char_hanseoyeon"
    session.remainingQuestions = 9
    session.lastRuntimeDiagnostics = {
        "characterReactionRoute": "ask_clarification",
        "characterReaction": {
            "reactionRoute": "ask_clarification",
            "playerFacingReason": "질문이 모호해 더 구체적인 단서를 요청합니다.",
        },
    }
    session.dialogueLog = []
    for index in range(3):
        session.dialogueLog.append(
            DialogueEntry(id=f"p{index}", speaker="player", suspectId="char_hanseoyeon", text="그거 말이야")
        )
        session.dialogueLog.append(
            DialogueEntry(id=f"n{index}", speaker="한서연", suspectId="char_hanseoyeon", text="무엇을 말하는 건가요?")
        )

    suggestion = public_helper_suggestion(case, session)

    assert suggestion["helperRoute"] in {"nudge_evidence", "nudge_contradiction", "nudge_switch_suspect"}
    assert suggestion["tone"] == "noir_assistant"
    assert suggestion["message"]
    assert suggestion["suggestedActions"]
    serialized = str(suggestion)
    assert "isCulprit" not in serialized
    assert "secret" not in serialized.lower()


def test_helper_suggestion_stays_silent_when_low_questions_but_not_stuck():
    case = _case()
    session = initial_session_state(case, "test_session")
    session.remainingQuestions = 3
    session.lastRuntimeDiagnostics = {"characterReactionRoute": "answer_relevant"}

    suggestion = public_helper_suggestion(case, session)

    assert suggestion["helperRoute"] == "silent"
    assert suggestion["suggestedActions"] == []
