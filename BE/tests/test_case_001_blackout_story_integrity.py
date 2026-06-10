from __future__ import annotations

from tests.test_api_smoke import _client


def test_blackout_is_visible_as_core_evidence_and_main_timeline(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()

    evidence_ids = {item["evidenceId"] for item in session["evidence"]}
    visible_timeline_ids = {item["timelineId"] for item in session["visibleTimeline"]}
    case_file_timeline_ids = {item["timelineId"] for item in session["caseFile"]["visibleTimeline"]}

    assert "ev_storm_blackout" in evidence_ids
    assert "tl_blackout" in visible_timeline_ids
    assert "tl_blackout" in case_file_timeline_ids

    blackout_evidence = next(item for item in session["evidence"] if item["evidenceId"] == "ev_storm_blackout")
    blackout_timeline = next(item for item in session["visibleTimeline"] if item["timelineId"] == "tl_blackout")

    assert blackout_evidence["name"] == "정전 기록"
    assert "22:05~22:07" in blackout_evidence["description"]
    assert blackout_timeline["sourceId"] == "ev_storm_blackout"
    assert "정전" in blackout_timeline["title"]
