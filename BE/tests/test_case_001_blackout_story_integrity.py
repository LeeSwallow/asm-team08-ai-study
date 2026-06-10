from __future__ import annotations

import json
from pathlib import Path

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


def test_blackout_clue_path_links_public_blackout_to_scene_manipulation():
    case = json.loads(Path("data/cases/case_001.json").read_text(encoding="utf-8"))

    path = next(item for item in case["storyline"]["cluePaths"] if item["pathId"] == "path_blackout_scene_manipulation")
    step_ids = [item["id"] for item in path["steps"]]

    assert path["resolvesContradictionId"] == "con_watch_time_manipulated"
    assert step_ids == ["tl_blackout", "ev_storm_blackout", "ev_broken_watch", "ev_deleted_cctv"]
    assert "ev_deleted_cctv" in path["unlocks"]

    objective_rules = case["storyline"]["currentObjectiveRules"]
    scene_rule = next(item for item in objective_rules if item["actId"] == "scene_manipulation_review")
    final_rule = next(item for item in objective_rules if item["actId"] == "final_accusation")

    assert scene_rule["when"] == {
        "discoveredContradictionId": "con_inheritance_motive",
        "missingContradictionId": "con_watch_time_manipulated",
    }
    assert "정전" in scene_rule["objective"]
    assert final_rule["when"] == {"discoveredContradictionId": "con_watch_time_manipulated"}
