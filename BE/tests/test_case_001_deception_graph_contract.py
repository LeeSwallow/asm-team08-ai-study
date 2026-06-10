from __future__ import annotations

import json
from pathlib import Path

from tests.test_api_smoke import _client


CASE_PATH = Path("data/cases/case_001.json")
MIGRATION_PATH = Path("scripts/migrate_case_to_neo4j.py")


def _case() -> dict:
    return json.loads(CASE_PATH.read_text(encoding="utf-8"))


def test_case_001_models_each_suspect_as_a_deception_arc() -> None:
    case = _case()
    evidence_ids = {item["evidenceId"] for item in case["evidence"]}
    statement_ids = {item["statementId"] for item in case["statements"]}
    question_ids = {item["questionId"] for item in case["questions"]}
    contradiction_ids = {item["contradictionId"] for item in case["contradictions"]}
    relation_ids = {item["relationshipId"] for item in case.get("relations", [])}
    suspect_ids = {item["characterId"] for item in case["suspects"]}

    arcs = case.get("deceptionGraph", {}).get("suspectArcs", [])
    assert {arc["suspectId"] for arc in arcs} == suspect_ids

    for arc in arcs:
        assert arc["arcId"].startswith("arc_")
        assert arc["suspectId"] in suspect_ids
        assert arc["lieGoal"]
        assert arc["publicLie"]
        assert arc["concealedTruth"]
        assert arc["collapseDisclosure"]
        assert arc["collapseQuestionId"] in question_ids
        assert set(arc["evidenceIds"]).issubset(evidence_ids)
        assert set(arc["statementIds"]).issubset(statement_ids)
        assert set(arc["contradictionIds"]).issubset(contradiction_ids)
        assert len(arc["stages"]) >= 4
        orders = [stage["order"] for stage in arc["stages"]]
        assert orders == sorted(orders)
        assert arc["stages"][-1]["state"] in {"broken", "culprit_confession"}
        for stage in arc["stages"]:
            assert stage["state"]
            assert stage["defenseLine"]
            assert set(stage.get("requiresEvidenceIds", [])).issubset(evidence_ids)
            assert set(stage.get("requiresContradictionIds", [])).issubset(contradiction_ids)
            assert set(stage.get("unlocks", [])).issubset(evidence_ids | statement_ids | question_ids | contradiction_ids | relation_ids)


def test_case_001_yoonjaeho_arc_conceals_witness_truth_until_collapse() -> None:
    case = _case()
    arcs = {arc["suspectId"]: arc for arc in case["deceptionGraph"]["suspectArcs"]}
    yoon = arcs["char_yoonjaeho"]

    assert yoon["lieGoal"] == "한서연 목격과 순찰 기록 조작을 숨겨 한서연을 보호한다."
    assert "ev_yoon_route_log" in yoon["evidenceIds"]
    assert "ev_yoonjaeho_folded_route_copy" in yoon["evidenceIds"]
    assert "ev_childhood_photo" in yoon["evidenceIds"]
    assert "con_yoon_route_gap" in yoon["contradictionIds"]
    assert "con_yoon_witness_guilt" in yoon["contradictionIds"]
    assert yoon["collapseQuestionId"] == "q_yoonjaeho_breakdown"

    pre_collapse_lines = " ".join(stage["defenseLine"] for stage in yoon["stages"][:-1])
    assert "한서연을 봤" not in pre_collapse_lines
    assert "한서연 씨를 봤" in yoon["stages"][-1]["defenseLine"]


def test_yoonjaeho_route_gap_followups_keep_butler_lie_context(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    session_id = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()["sessionId"]

    client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_yoonjaeho", "message": "피해자를 언제 발견했나요?"},
    )
    route_gap = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_yoonjaeho", "message": "22:10 발견 진술은 집사 순찰 기록의 22:08 2층 복도 확인 표시와 모순입니다."},
    ).json()
    assert route_gap["dialogueResult"]["dialogueMode"] == "evidence_question"
    assert route_gap["contradictionResult"]["contradictionId"] == "con_yoon_route_gap"

    why = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_yoonjaeho", "message": "어떤 이유?"},
    ).json()
    assert why["dialogueResult"]["dialogueMode"] == "pressure_followup"
    assert "정확히 말씀" not in why["answer"]
    assert "집사로서 할 일을 했을 뿐" not in why["answer"]
    assert any(term in why["answer"] for term in ("22:08", "순찰", "기록", "정전", "보고"))
    assert "한서연 씨를 봤" not in why["answer"]

    hidden_reason = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_yoonjaeho", "message": "너가 말한 숨긴 이유가 뭐지?"},
    ).json()
    assert hidden_reason["dialogueResult"]["dialogueMode"] == "pressure_followup"
    assert "집사로서 할 일을 했을 뿐" not in hidden_reason["answer"]
    assert "한서연 씨를 봤" not in hidden_reason["answer"]

    record = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_yoonjaeho", "message": "집사 순찰 기록은 뭐야?"},
    ).json()
    assert record["dialogueResult"]["dialogueMode"] == "evidence_question"
    assert "22:08" in record["answer"] or "2층 복도" in record["answer"]


def test_hanseoyeon_answers_public_yoonjaeho_relationship_even_with_typo(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    session_id = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "윤채호님에 대해 아는 점 있어요?"},
    ).json()

    assert response["dialogueResult"]["dialogueMode"] == "case_question"
    assert response["dialogueResult"]["matchedQuestionId"] == "q_hanseoyeon_yoonjaeho_relation"
    assert "처음 들어" not in response["answer"]
    assert "집사" in response["answer"]
    assert "어릴 때" in response["answer"] or "오래" in response["answer"]


def test_parkmingyu_can_share_basic_condition_and_medicine_without_collapse(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    session_id = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()["sessionId"]

    condition = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_parkmingyu", "message": "피해자가 어떤 병을 가지고 있었나요?"},
    ).json()
    assert condition["dialogueResult"]["matchedQuestionId"] == "q_parkmingyu_diagnosis"
    assert "췌장암" in condition["answer"]
    assert "일반적인 건강" not in condition["answer"]


def test_parkmingyu_medicine_followup_keeps_answer_specific(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    session_id = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()["sessionId"]

    first = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_parkmingyu", "message": "어떤 약을 먹고 있었나요?"},
    ).json()
    assert first["dialogueResult"]["matchedQuestionId"] == "q_parkmingyu_medicine"
    assert "약" in first["answer"]

    second = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_parkmingyu", "message": "그러니까 무슨 약일까요??"},
    ).json()
    assert second["dialogueResult"]["matchedQuestionId"] == "q_parkmingyu_medicine"
    assert second["dialogueResult"]["dialogueMode"] in {"case_question", "evidence_question"}
    assert any(term in second["answer"] for term in ("모르핀", "수면 보조제", "통증", "진통제", "제 확인"))
    assert "기록만으로 사인을 단정" not in second["answer"]


def test_neo4j_migration_materializes_deception_graph_nodes_and_edges() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "DeceptionArc" in source
    assert "HAS_DECEPTION_ARC" in source
    assert "CONCEALS" in source
    assert "SUPPORTED_BY" in source
    assert "PRESSURED_BY" in source
    assert "COLLAPSES_VIA" in source
