import json
import logging
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import deps
from app.core.config import get_settings
from app.domain.event_processor import EventProcessor
from app.domain.event_types import EventType
from app.infra.case_repository import CaseRepository
from app.infra.case_orm import CaseRecord
from app.infra.db import Base, ensure_schema, get_engine, get_session_factory
from app.domain.case_engine import initial_session_state
from app.main import app


class ContractTestAIClient:
    async def dialogue_response_info(self, payload, fallback):
        mode = payload.get("dialogueMode")
        proposed_events = []
        if mode == "evidence_question" and "ev_study_entry_log" in payload.get("allowedEventPolicy", {}).get("relatedEvidenceIds", []):
            proposed_events.append(
                {
                    "type": EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value,
                    "payload": {"contradictionId": "con_room_claim_vs_entry_log"},
                }
            )
        elif payload.get("consumedQuestion") and payload.get("allowedStatement", {}).get("id", "").startswith("st_"):
            proposed_events.append(
                {
                    "type": EventType.NOTE_FACT_ADDED.value,
                    "payload": {"sourceType": "statement", "sourceId": payload["allowedStatement"]["id"]},
                }
            )
        return {
            "answer": fallback,
            "proposedEvents": proposed_events,
            "fallbackUsed": False,
            "degraded": False,
            "provider": "contract-test-ai",
            "model": "contract-model",
            "intent": mode,
            "dialogueMode": mode,
            "safety": {"status": "checked", "fallbackUsed": False},
        }

    async def dialogue_response(self, payload, fallback):
        return (await self.dialogue_response_info(payload, fallback))["answer"]

    async def notes_summary(self, payload, fallback):
        return fallback

    async def hint(self, payload, fallback):
        return fallback

    async def ending(self, payload, fallback):
        return fallback

    async def health(self):
        return {"ok": True, "status": "ok", "provider": "contract-test-ai"}


def _seed_case_database(tmp_path, monkeypatch):
    monkeypatch.setenv("BE_DATABASE_URL", f"sqlite:///{tmp_path / 'cases.db'}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    ensure_schema.cache_clear()
    deps.get_case_repository.cache_clear()

    engine = get_engine()
    session_factory = get_session_factory()
    assert engine is not None
    assert session_factory is not None

    Base.metadata.create_all(engine)
    with session_factory() as db:
        for path in sorted((Path("data/cases")).glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            db.merge(CaseRecord(case_id=str(payload["caseId"]), payload=payload))
        db.commit()


def _client(tmp_path, monkeypatch, debug_tools: bool = False):
    data_dir = tmp_path / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    monkeypatch.setenv("BE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("BE_DEBUG_TOOLS_ENABLED", "true" if debug_tools else "false")
    _seed_case_database(tmp_path, monkeypatch)
    get_settings.cache_clear()
    deps.get_case_repository.cache_clear()
    deps.get_session_repository.cache_clear()
    if hasattr(deps, "get_event_repository"):
        deps.get_event_repository.cache_clear()
    monkeypatch.setattr(deps, "get_ai_client", lambda: ContractTestAIClient())
    return TestClient(app)


def test_mvp_flow_persists_and_solves_case(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    ready = client.get("/api/v1/ready").json()
    assert ready["status"] == "ok"
    assert ready["ai"]["ok"] is True

    cases = client.get("/api/v1/cases").json()
    assert cases[0]["caseId"] == "case_001"

    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]
    assert session["remainingQuestions"] == 12
    assert session["selectedSuspectId"] is not None
    assert len(session["suspects"]) >= 4
    assert len(session["evidence"]) >= 4

    asked = client.post(
        f"/api/v1/sessions/{session_id}/questions",
        json={"questionId": "q_hanseoyeon_alibi", "suspectId": "char_hanseoyeon"},
    ).json()
    assert asked["remainingQuestions"] == 11
    assert asked["questionResult"]["repeated"] is False
    assert len(asked["dialogueLog"]) == 2

    repeated = client.post(
        f"/api/v1/sessions/{session_id}/questions",
        json={"questionId": "q_hanseoyeon_alibi"},
    ).json()
    assert repeated["remainingQuestions"] == 10
    assert repeated["questionResult"]["repeated"] is True
    assert repeated["questionResult"]["askCount"] == 2

    removed = client.post(
        f"/api/v1/sessions/{session_id}/contradictions",
        json={"suspectId": "char_hanseoyeon", "statementIds": ["st_hanseoyeon_room_2200"], "evidenceIds": ["ev_study_entry_log"]},
    )
    assert removed.status_code == 404

    correct = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "22시에 방에 있었다는 진술은 서재 출입 기록의 22:02 카드키 기록과 모순입니다.",
        },
    ).json()
    result = correct["contradictionResult"]
    assert result["verdict"] == "correct"
    assert result["contradictionId"] == "con_room_claim_vs_entry_log"
    assert "q_hanseoyeon_after_pressure" in correct["unlockedQuestionIds"]
    assert correct["pressureStates"]["char_hanseoyeon"] == "pressed"

    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    assert loaded["remainingQuestions"] == 10
    assert loaded["discoveredContradictionIds"] == ["con_room_claim_vs_entry_log"]

    partial = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "상속 문제는 없었다는 진술만으로 모순인가요?"},
    ).json()
    assert partial["contradictionResult"] is None

    client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "상속 문제는 없었다는 말은 찢어진 유언장 내용과 모순입니다."},
    )
    accusation = client.post(
        f"/api/v1/sessions/{session_id}/accusation",
        json={
            "suspectId": "char_hanseoyeon",
            "motive": "상속 비율 변경 때문에 피해자와 갈등했다.",
            "method": "서재에 들어간 뒤 정전 시간을 이용해 현장을 조작했다.",
            "evidenceIds": ["ev_study_entry_log", "ev_torn_will"],
            "contradictionIds": ["con_room_claim_vs_entry_log", "con_inheritance_motive"],
            "statementIds": ["st_hanseoyeon_room_2200", "st_hanseoyeon_no_reason"],
        },
    ).json()
    assert accusation["accusationResult"]["verdict"] == "correct"
    assert accusation["accusationResult"]["correct"] is True
    assert "culpritCorrect" not in accusation["accusationResult"]
    assert "suspectMatch" not in accusation["accusationResult"]
    assert accusation["accusationResult"]["submittedMotive"] == "상속 비율 변경 때문에 피해자와 갈등했다."
    assert accusation["accusation"]["submittedMethod"] == "서재에 들어간 뒤 정전 시간을 이용해 현장을 조작했다."
    assert "culpritCorrect" not in accusation["accusation"]
    assert _forbidden_token_hits(accusation) == []
    assert accusation["phase"] == "solved"
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: ACCUSATION_RESOLVED" in events_body
    assert "culpritCorrect" not in events_body

    saved_session = deps.get_session_repository().get(session_id)
    assert saved_session is not None
    assert saved_session.phase == "solved"
    assert saved_session.accusation is not None
    assert saved_session.accusation["submittedMotive"]


def test_case_001_progression_can_unlock_all_suspects_relations_and_evidence_within_limit(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    assert session["questionLimit"] == 12
    assert session["remainingQuestions"] == 12
    assert session["visibleEvidenceCount"] == 5
    assert session["totalEvidenceCount"] == 13
    assert {item["characterId"] for item in session["suspects"]} == {
        "char_hanseoyeon",
        "char_yoonjaeho",
        "char_parkmingyu",
        "char_choiyuna",
    }
    initial_evidence_ids = {item["evidenceId"] for item in session["evidence"]}
    assert initial_evidence_ids == {
        "ev_broken_watch",
        "ev_wine_glass",
        "ev_study_entry_log",
        "ev_servant_log",
        "ev_window_bolt",
    }
    assert "ev_torn_will" not in initial_evidence_ids
    assert "ev_ring_near_victim" not in initial_evidence_ids
    assert "ev_prescription_dispute_note" not in initial_evidence_ids

    def ask(question_id: str):
        return client.post(f"/api/v1/sessions/{session_id}/questions", json={"questionId": question_id}).json()

    def challenge(suspect_id: str, message: str):
        return client.post(
            f"/api/v1/sessions/{session_id}/dialogue",
            json={"suspectId": suspect_id, "message": message},
        ).json()

    # Question-selected side routes should open every non-core suspect's useful evidence/relation leads.
    session = ask("q_yoonjaeho_blackout")
    session = ask("q_yoonjaeho_family_tension")
    session = ask("q_parkmingyu_medicine")
    session = ask("q_parkmingyu_argument")
    session = ask("q_choiyuna_last_call")
    session = ask("q_choiyuna_schedule")
    session = ask("q_choiyuna_wine")

    # Core contradiction opens the gated motive/scene evidence and follow-up questions.
    session = challenge(
        "char_hanseoyeon",
        "22시에 방에 있었다는 진술은 22:02 서재 출입 기록과 모순입니다.",
    )
    assert session["contradictionResult"]["contradictionId"] == "con_room_claim_vs_entry_log"
    assert "q_hanseoyeon_after_pressure" in session["unlockedQuestionIds"]
    assert "q_hanseoyeon_ring_missing" in session["unlockedQuestionIds"]
    assert "ev_torn_will" in {item["evidenceId"] for item in session["evidence"]}
    assert "ev_ring_near_victim" in {item["evidenceId"] for item in session["evidence"]}

    session = ask("q_hanseoyeon_ring_missing")
    assert "st_hanseoyeon_ring_missing" in {item["statementId"] for item in session["statements"]}
    session = challenge(
        "char_hanseoyeon",
        "반지가 어디서 사라졌는지 모른다는 말은 현장 발견 반지와 모순입니다.",
    )
    assert session["contradictionResult"]["contradictionId"] == "con_ring_vs_no_entry"
    assert "rec_ring_ownership" in {item["recordId"] for item in session["records"]}

    session = ask("q_hanseoyeon_after_pressure")
    session = challenge(
        "char_hanseoyeon",
        "정전 기록과 깨진 회중시계 파편 방향이 맞지 않습니다. 정전 중 현장 조작이라서 모순입니다.",
    )
    assert session["contradictionResult"]["contradictionId"] == "con_watch_time_manipulated"

    all_evidence_ids = {
        "ev_broken_watch",
        "ev_wine_glass",
        "ev_study_entry_log",
        "ev_servant_log",
        "ev_torn_will",
        "ev_phone_call",
        "ev_medicine_box",
        "ev_storm_blackout",
        "ev_ring_near_victim",
        "ev_lipstick_tube",
        "ev_window_bolt",
        "ev_deleted_cctv",
        "ev_prescription_dispute_note",
    }
    assert {item["evidenceId"] for item in session["evidence"]} == all_evidence_ids
    assert session["visibleEvidenceCount"] == session["totalEvidenceCount"] == len(all_evidence_ids)
    assert all(edge["unlocked"] for edge in session["relationMap"]["edges"])
    assert session["remainingQuestions"] >= 0


def test_accusation_cannot_be_solved_with_undiscovered_internal_ids(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    accusation = client.post(
        f"/api/v1/sessions/{session_id}/accusation",
        json={
            "suspectId": "char_hanseoyeon",
            "motive": "공개 단서 기준 동기 추정",
            "method": "공개 단서 기준 방법 추정",
            "evidenceIds": ["ev_study_entry_log", "ev_torn_will"],
            "contradictionIds": ["con_room_claim_vs_entry_log", "con_inheritance_motive"],
            "statementIds": ["st_hanseoyeon_room_2200", "st_hanseoyeon_no_reason"],
        },
    ).json()

    assert accusation["accusationResult"]["verdict"] == "partial"
    assert accusation["accusationResult"]["correct"] is False
    assert accusation["phase"] == "accusation"


def test_investigation_read_models_include_case_file_notebook_and_contradiction_details(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    assert session["caseFile"]["title"]
    assert session["caseFile"]["opening"]["objective"]
    assert session["notebook"]["caseFile"]["currentObjective"] == session["currentObjective"]
    evidence = next(item for item in session["notebook"]["evidence"] if item["evidenceId"] == "ev_study_entry_log")
    assert evidence["description"]
    assert evidence["foundAt"]
    assert evidence["timeWindow"]
    assert evidence["reliability"] is not None
    assert "sourceRefs" in evidence
    assert "char_hanseoyeon" in session["notebook"]["statementsBySuspect"]
    assert session["notebook"]["contradictions"]["candidates"]

    note = client.post(
        f"/api/v1/sessions/{session_id}/notes",
        json={"text": "서재 출입 기록과 알리바이를 비교한다.", "linkedEvidenceIds": ["ev_study_entry_log"]},
    ).json()
    assert note["notebook"]["notes"][-1]["text"] == "서재 출입 기록과 알리바이를 비교한다."

    correct = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "22시에 방에 있었다는 진술은 서재 출입 기록의 22:02 카드키 기록과 모순입니다.",
        },
    ).json()
    discovered = correct["contradictions"]["discovered"][0]
    assert discovered["contradictionId"] == "con_room_claim_vs_entry_log"
    assert discovered["statementIds"] == ["st_hanseoyeon_room_2200"]
    assert discovered["evidenceIds"] == ["ev_study_entry_log"]
    assert discovered["displayText"]
    assert correct["notebook"]["contradictions"]["discovered"][0]["submitEligible"] is True

    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_CONTRADICTION_CANDIDATE_ADDED" in events_body
    assert "event: TENSION_CHANGED" in events_body
    assert "con_room_claim_vs_entry_log" in events_body


def test_natural_dialogue_contradictions_create_notebook_proof_and_readiness(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch, debug_tools=True)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    client.post(f"/api/v1/sessions/{session_id}/debug/unlock", json={"target": "all"})

    room = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "22시에 방에 있었다고 했는데 서재 출입 기록에는 22:02 카드키가 찍혀 있어요. 모순 아닌가요?",
        },
    ).json()
    room_transition = room["dialogueResult"]["interrogationTransition"]
    assert room_transition["newlyDiscoveredContradictionIds"] == ["con_room_claim_vs_entry_log"]
    assert room["accusationReadiness"]["eligible"] is False

    will = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "상속 때문에 다툰 적 없다고 했는데 찢어진 유언장에는 한서연 몫이 줄어드는 변경 흔적이 있네요.",
        },
    ).json()
    will_transition = will["dialogueResult"]["interrogationTransition"]
    assert will_transition["newlyDiscoveredContradictionIds"] == ["con_inheritance_motive"]
    assert will["accusationReadiness"]["eligible"] is True

    contradiction_notes = [
        note
        for note in will["notes"]
        if EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value.lower() in note["tags"]
    ]
    note_ids = {item["linkedContradictionIds"][0] for item in contradiction_notes}
    assert {"con_room_claim_vs_entry_log", "con_inheritance_motive"}.issubset(note_ids)

    proof_evidence_ids = sorted({item for note in contradiction_notes for item in note["linkedEvidenceIds"]})
    proof_statement_ids = sorted({item for note in contradiction_notes for item in note["linkedStatementIds"]})
    accusation = client.post(
        f"/api/v1/sessions/{session_id}/accusation",
        json={
            "suspectId": "char_hanseoyeon",
            "motive": "상속 비율 변경 때문에 피해자와 갈등했다.",
            "method": "서재 출입 기록과 유언장 흔적을 근거로 최종 지목한다.",
            "evidenceIds": proof_evidence_ids,
            "contradictionIds": will["discoveredContradictionIds"],
            "statementIds": proof_statement_ids,
        },
    ).json()
    assert accusation["accusationResult"]["verdict"] == "correct"
    assert accusation["accusationResult"]["correct"] is True


def test_tension_policy_only_changes_on_new_validated_contradiction(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    dialogue = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "22시 이후 어디에 있었나요?"},
    ).json()
    assert dialogue["pressureBySuspect"]["char_hanseoyeon"] == 0
    events_after_unlock = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: TENSION_CHANGED" not in events_after_unlock

    first = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "22시에 방에 있었다는 진술은 서재 출입 기록의 22:02 카드키 기록과 모순입니다.",
        },
    ).json()
    assert first["contradictionResult"]["verdict"] == "correct"
    assert first["contradictionResult"]["newlyDiscovered"] is True
    assert first["contradictionResult"]["pressureDelta"] == 62
    assert first["pressureBySuspect"]["char_hanseoyeon"] == 62

    duplicate = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "다시 말하지만 방에 있었다는 진술은 서재 출입 기록과 모순입니다.",
        },
    ).json()
    assert duplicate["contradictionResult"]["verdict"] == "correct"
    assert duplicate["contradictionResult"]["newlyDiscovered"] is False
    assert duplicate["contradictionResult"]["pressureDelta"] == 0
    assert duplicate["pressureBySuspect"]["char_hanseoyeon"] == 62

    events = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert events.count("event: TENSION_CHANGED") == 1


def test_partial_or_unlock_flow_does_not_raise_tension(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    partial = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "방에 있었다는 진술만으로 모순인가요?"},
    ).json()

    assert partial["contradictionResult"] is None
    events = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: TENSION_CHANGED" not in events


def test_relationship_map_and_notes_crud_are_be_backed(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    relation_map = session["relationMap"]
    assert relation_map["centerCharacterId"] == "victim_kangdojun"
    assert any(node["characterId"] == "char_hanseoyeon" for node in relation_map["nodes"])
    visible_edge = next(edge for edge in relation_map["edges"] if edge["relationshipId"] == "rel_hanseoyeon_inheritance")
    assert visible_edge["sourceCharacterId"] == "victim_kangdojun"
    assert visible_edge["targetCharacterId"] == "char_hanseoyeon"
    assert visible_edge["unlocked"] is True
    assert visible_edge["label"]
    locked_edge = next(edge for edge in relation_map["edges"] if edge["relationshipId"] == "rel_yoonjaeho_loyalty")
    assert locked_edge["unlocked"] is False
    assert locked_edge["conflict"] == ""
    assert "유언장 변경" not in json.dumps(locked_edge, ensure_ascii=False)

    created = client.post(
        f"/api/v1/sessions/{session_id}/notes",
        json={"text": "관계도에서 조카-피해자 갈등 확인", "linkedEvidenceIds": ["ev_study_entry_log"]},
    ).json()
    note_id = created["note"]["id"]
    assert created["notebook"]["notes"][-1]["id"] == note_id
    listed = client.get(f"/api/v1/sessions/{session_id}/notes").json()
    assert listed["notes"][0]["id"] == note_id

    updated = client.put(
        f"/api/v1/sessions/{session_id}/notes/{note_id}",
        json={"text": "관계도와 출입기록을 함께 확인", "tags": ["relationship", "evidence"]},
    ).json()
    assert updated["note"]["text"] == "관계도와 출입기록을 함께 확인"
    assert updated["notebook"]["notes"][0]["tags"] == ["relationship", "evidence"]

    deleted = client.delete(f"/api/v1/sessions/{session_id}/notes/{note_id}").json()
    assert deleted["deletedNoteId"] == note_id
    assert deleted["notebook"]["notes"] == []

    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_CREATED" in events_body
    assert "event: NOTE_UPDATED" in events_body
    assert "event: NOTE_DELETED" in events_body


def test_debug_endpoints_are_dev_gated_and_emit_public_session_updates(tmp_path, monkeypatch):
    disabled_client = _client(tmp_path, monkeypatch)
    disabled_session = disabled_client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    disabled = disabled_client.post(
        f"/api/v1/sessions/{disabled_session['sessionId']}/debug/pressure",
        json={"suspectId": "char_hanseoyeon", "pressure": 60},
    )
    assert disabled.status_code == 403
    assert disabled.json()["detail"]["code"] == "DEBUG_TOOLS_DISABLED"

    client = _client(tmp_path, monkeypatch, debug_tools=True)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]
    before_dialogue_len = len(session["dialogueLog"])

    pressure = client.post(
        f"/api/v1/sessions/{session_id}/debug/pressure",
        json={"suspectId": "char_hanseoyeon", "pressure": 65},
    ).json()
    assert pressure["sessionId"] == session_id
    assert pressure["pressureBySuspect"]["char_hanseoyeon"] == 65
    assert pressure["selectedSuspectId"] == session["selectedSuspectId"]
    assert len(pressure["dialogueLog"]) == before_dialogue_len
    assert pressure["debugResult"]["action"] == "set_pressure"

    unlocked = client.post(
        f"/api/v1/sessions/{session_id}/debug/unlock",
        json={"target": "all"},
    ).json()
    assert len(unlocked["evidence"]) >= 4
    assert all(edge["unlocked"] for edge in unlocked["relationMap"]["edges"])
    assert len(unlocked["visibleTimeline"]) >= len(session["visibleTimeline"])
    assert unlocked["debugResult"]["action"] == "unlock"
    assert unlocked["debugResult"]["noteId"]

    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: TENSION_CHANGED" in events_body
    assert "event: NOTE_CREATED" in events_body
    assert "event: DEBUG_SESSION_UPDATED" in events_body
    serialized = json.dumps(unlocked, ensure_ascii=False)
    for forbidden_key in ["secret", "isCulprit", "solution", "secretNote", "privateMotive", "actualAction"]:
        assert forbidden_key not in _all_keys(unlocked)
    assert "solution_hidden" not in serialized


def test_notes_bookmarks_hint_summary_and_wrong_combo(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    note = client.post(
        f"/api/v1/sessions/{session_id}/notes",
        json={"text": "22:02 출입 기록이 핵심이다.", "linkedEvidenceIds": ["ev_study_entry_log"]},
    ).json()
    assert note["note"]["text"] == "22:02 출입 기록이 핵심이다."

    bookmark = client.post(
        f"/api/v1/sessions/{session_id}/bookmarks",
        json={"targetType": "evidence", "targetId": "ev_study_entry_log", "note": "알리바이 반박"},
    ).json()
    assert bookmark["bookmark"]["targetId"] == "ev_study_entry_log"

    assert client.get(f"/api/v1/sessions/{session_id}/hint").json()["hint"]
    assert client.get(f"/api/v1/sessions/{session_id}/summary").json()["summary"]
    assert client.get(f"/api/v1/sessions/{session_id}/ending").json()["verdict"] == "incomplete"


def test_dialogue_accepts_suspect_id_and_message_and_records_events(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "그날 밤 열 시쯤, 당신이 정말 자기 방에 있었다는 걸 어떻게 설명할 수 있죠?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remainingQuestions"] == 11
    assert payload["answer"]
    assert payload["dialogueResult"]["suspectId"] == "char_hanseoyeon"
    assert payload["dialogueResult"]["matchedQuestionId"] == "q_hanseoyeon_alibi"
    assert payload["dialogueResult"]["repeated"] is False
    assert payload["proposedEventsApplied"]
    assert payload["lastEventId"] == payload["proposedEventsApplied"][-1]
    assert payload["visualState"]["characterImageState"] in {"neutral", "wary", "defensive", "shocked", "breakdown"}
    assert payload["visualState"]["emotionalState"] == payload["visualState"]["characterImageState"]
    assert payload["visualState"]["tensionLevel"] in {"low", "medium", "high", "critical"}

    events_response = client.get(f"/api/v1/sessions/{session_id}/events?once=true")
    assert events_response.status_code == 200
    assert "text/event-stream" in events_response.headers["content-type"]
    body = events_response.text
    assert "event: NOTE_FACT_ADDED" in body
    assert "event: VISUAL_STATE_CHANGED" in body
    assert "event: TENSION_CHANGED" not in body
    assert "id: " in body
    assert "st_hanseoyeon_room_2200" in body


def test_session_get_persists_public_dialogue_runtime_diagnostics(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    dialogue = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "22시에 방에 있었다는 진술은 서재 출입 기록의 22:02 카드키 기록과 모순입니다.",
        },
    ).json()
    loaded = client.get(f"/api/v1/sessions/{session_id}").json()

    assert loaded["selectedSuspectId"] == "char_hanseoyeon"
    assert loaded["runtimeDiagnostics"]["provider"] == "contract-test-ai"
    assert loaded["runtimeDiagnostics"]["dialogueMode"] == dialogue["dialogueResult"]["dialogueMode"]
    assert loaded["runtimeDiagnostics"]["appliedEventsCount"] == dialogue["dialogueResult"]["appliedEventsCount"]
    assert loaded["lastDialogueResult"]["contradictionResult"]["verdict"] == "correct"
    assert loaded["contradictions"]["candidates"]
    assert loaded["contradictions"]["discovered"]
    candidate = loaded["contradictions"]["candidates"][0]
    for key in ["contradictionId", "title", "suspectId", "statementIds", "evidenceIds", "severity", "reasonCode", "displayText", "submitEligible"]:
        assert key in candidate
    assert _forbidden_token_hits(loaded) == []


def test_dialogue_other_suspect_mention_does_not_consume_active_suspect_question(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    yoon = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "윤재호는 22시쯤 어디에 있었나요?"},
    ).json()
    kang = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "강도준의 상속 문제를 설명해 주세요."},
    ).json()

    assert yoon["dialogueResult"]["dialogueMode"] == "unmatched"
    assert yoon["dialogueResult"]["matchedQuestionId"] is None
    assert yoon["dialogueResult"]["consumedQuestion"] is False
    assert kang["dialogueResult"]["dialogueMode"] == "unmatched"
    assert kang["dialogueResult"]["matchedQuestionId"] is None
    assert kang["dialogueResult"]["consumedQuestion"] is False
    assert client.get(f"/api/v1/sessions/{session_id}").json()["askedQuestionCounts"] == {}


def test_questions_endpoint_accepts_fe_free_text_compatibility_payload(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]
    free_text = "그날 밤 열 시쯤, 당신이 정말 자기 방에 있었다는 걸 어떻게 설명할 수 있죠?"

    response = client.post(
        f"/api/v1/sessions/{session_id}/questions",
        json={"suspectId": "char_hanseoyeon", "questionText": free_text},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remainingQuestions"] == 11
    assert payload["dialogueLog"][-2]["speaker"] == "player"
    assert payload["dialogueLog"][-2]["text"] == free_text
    assert payload["dialogueResult"]["matchedQuestionId"] == "q_hanseoyeon_alibi"
    assert payload["proposedEventsApplied"]
    assert payload["lastEventId"] == payload["proposedEventsApplied"][-1]

    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_FACT_ADDED" in events_body
    assert "event: VISUAL_STATE_CHANGED" in events_body
    assert "event: TENSION_CHANGED" not in events_body


def test_dialogue_accepts_arbitrary_natural_language_by_mapping_to_allowed_context(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]
    message = "추천 문장과 다르게 물어보겠습니다. 서재 출입 기록이 당신의 알리바이와 어긋나는 건 어떻게 설명하시죠?"

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": message},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remainingQuestions"] == 11
    assert payload["dialogueLog"][-2]["speaker"] == "player"
    assert payload["dialogueLog"][-2]["text"] == message
    assert payload["dialogueResult"]["matchedQuestionId"] in session["unlockedQuestionIds"]
    assert payload["dialogueResult"]["suspectId"] == "char_hanseoyeon"
    assert payload["answer"]


def test_dialogue_evidence_conflict_creates_validated_contradiction_candidate_sse(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "방에 있었다는 말과 서재 출입 기록이 서로 충돌하지 않나요?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dialogueResult"]["proposedEventsCount"] >= 1
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_CONTRADICTION_CANDIDATE_ADDED" in events_body
    assert "con_room_claim_vs_entry_log" in events_body
    assert "st_hanseoyeon_room_2200" in events_body
    assert "ev_study_entry_log" in events_body


def test_dialogue_evidence_question_applies_canonical_contradiction_candidate_without_generic_fact_note(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "서재 출입 기록을 설명해 주세요.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dialogueResult"]["dialogueMode"] == "evidence_question"
    assert payload["dialogueResult"]["matchedQuestionId"] == "q_hanseoyeon_study_entry"
    assert payload["dialogueResult"]["proposedEventsCount"] >= 1
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_CONTRADICTION_CANDIDATE_ADDED" in events_body
    assert "event: NOTE_FACT_ADDED" not in events_body
    assert "con_room_claim_vs_entry_log" in events_body
    assert "st_hanseoyeon_room_2200" in events_body
    assert "ev_study_entry_log" in events_body
    assert "timelineIds" in events_body
    assert "submitEligible" in events_body


def test_dialogue_small_talk_does_not_consume_case_question_or_return_alibi(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "안녕하세요"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remainingQuestions"] == 12
    assert payload["dialogueResult"]["matchedQuestionId"] is None
    assert payload["dialogueResult"]["dialogueMode"] == "small_talk"
    assert payload["dialogueResult"]["consumedQuestion"] is False
    assert payload["dialogueResult"]["fallbackUsed"] is False
    assert payload["dialogueResult"]["provider"] == "contract-test-ai"
    assert payload["dialogueResult"]["previousRemainingQuestions"] == session["remainingQuestions"]
    assert payload["dialogueResult"]["remainingQuestionsDelta"] == 0
    assert payload["dialogueResult"]["appliedEventsCount"] == 1
    assert payload["appliedEventsCount"] == 1
    assert payload["provider"] == "contract-test-ai"
    assert "22:00" not in payload["answer"]
    assert "제 방" not in payload["answer"]
    assert payload["askedQuestionCounts"] == {}
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_FACT_ADDED" not in events_body
    assert "인사는 됐어요" not in events_body
    assert "event: TENSION_CHANGED" not in events_body
    assert "event: VISUAL_STATE_CHANGED" in events_body


def test_dialogue_broad_time_range_and_meta_followups_are_timeline_grounded(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    greeting = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "안녕하세요"},
    ).json()
    broad_time = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "10시부터 22시까지 뭐했어요?"},
    ).json()
    why = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "왜 답변을 못해요"},
    ).json()
    challenge = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "말이 된다고 생각해?"},
    ).json()

    assert greeting["dialogueResult"]["dialogueMode"] == "small_talk"
    assert broad_time["dialogueResult"]["dialogueMode"] == "timeline_question"
    assert broad_time["dialogueResult"]["matchedQuestionId"] == "q_hanseoyeon_alibi"
    assert broad_time["dialogueResult"]["consumedQuestion"] is True
    assert broad_time["dialogueResult"]["fallbackUsed"] is False
    assert broad_time["dialogueResult"]["provider"] == "contract-test-ai"
    assert "제 방" in broad_time["answer"]
    assert why["dialogueResult"]["dialogueMode"] == "pressure_followup"
    assert why["dialogueResult"]["matchedQuestionId"] is None
    assert why["dialogueResult"]["remainingQuestions"] == broad_time["dialogueResult"]["remainingQuestions"]
    assert challenge["dialogueResult"]["dialogueMode"] == "pressure_followup"
    assert challenge["dialogueResult"]["remainingQuestions"] == broad_time["dialogueResult"]["remainingQuestions"]
    answers = [broad_time["answer"], why["answer"], challenge["answer"]]
    assert len(set(answers)) == len(answers)
    assert all("그 질문만으로는" not in answer for answer in answers)
    assert all("조카로서 말씀드리자면" not in answer for answer in answers)


def test_local_ai_claim_grounding_repairs_new_alibi_but_keeps_registered_lie(tmp_path, monkeypatch):
    import app.ai_engine.application.character_agent as ca_mod
    import app.ai_engine.application.dialogue_tone_polisher as tone_mod
    from app.infra.local_ai_client import LocalAIClient

    class SeedLLM:
        provider_name = "upstage"

        def complete(self, prompt, *, seed_text, max_length=220):
            return seed_text[:max_length]

    def drift_or_keep_lie(self, payload, draft):
        if payload.suspect.id == "char_choiyuna":
            text = "\ub124, \uadf8\ub0a0 \uc77c\uc815\uc0c1 \ud68c\uc758 \ud6c4 \ubc14\ub85c \uadc0\uac00\ud588\uc2b5\ub2c8\ub2e4. \ud68c\uc7a5\ub2d8 \uc9c0\uc2dc\uc0ac\ud56d \ud655\uc778\ud588\uace0\uc694."
        else:
            text = "\u2026\uc0ac\uc2e4\uc740 \ubc24 10\uc2dc\ucbe4 \uc81c \ubc29\uc5d0 \uc788\uc5c8\uc5b4\uc694. \uc0ac\uc5c5 \uc2e4\ud328 \uc774\ud6c4 \uc7a0\ub3c4 \uc81c\ub300\ub85c \ubabb \uc794\uace0\uc694."
        return draft.model_copy(update={"draftText": text})

    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(deps, "get_ai_client", lambda: LocalAIClient())
    monkeypatch.setattr(ca_mod, "get_llm", lambda: SeedLLM())
    monkeypatch.setattr(
        ca_mod,
        "llm_status",
        lambda: {
            "provider": "upstage",
            "model": "solar-pro",
            "configured": True,
            "serviceDegraded": False,
            "fallbackConfigured": False,
            "timeoutMs": 8000,
        },
    )
    monkeypatch.setattr(tone_mod.DialogueTonePolisher, "run", drift_or_keep_lie)

    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]
    lie = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "\ubc24 10\uc2dc \uc804\ud6c4\uc5d0\ub294 \uc5b4\ub514\uc5d0 \uc788\uc5c8\uc5b4\uc694?"},
    ).json()
    drift = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_choiyuna", "message": "\uc11c\uc7ac\uc758 \uc640\uc778\uc794\uc744 \uc54c\uace0 \uc788\ub098\uc694?"},
    ).json()

    lie_grounding = lie["dialogueResult"]["aiRuntimeDiagnostics"]["grounding"]
    assert lie_grounding["checked"] is True
    assert lie_grounding["repaired"] is False
    assert "\uc81c \ubc29" in lie["answer"]
    assert "\uc7a0\ub3c4 \uc81c\ub300\ub85c \ubabb \uc794\uace0\uc694" in lie["answer"]

    drift_grounding = drift["dialogueResult"]["aiRuntimeDiagnostics"]["grounding"]
    assert drift_grounding["checked"] is True
    assert drift_grounding["repaired"] is True
    assert drift_grounding["basis"] == "allowed_statement_claim"
    assert drift_grounding["repairReason"] == "claim_grounding_repaired"
    assert drift_grounding["finalTextSource"] == "public_seed_after_claim_grounding"
    assert "unsupported_concrete_claim" in drift_grounding["issues"]
    assert "required_anchor_claim_missing" in drift_grounding["issues"]
    assert drift["answer"] == "\ub124, \uc800\ub294 \uadf8\ub0a0 \uc640\uc778\uc744 \ub9c8\uc2dc\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4. \ub9bd\uc2a4\ud2f1 \uc0c9\ub3c4 \uc81c \uac83\uc774 \uc544\ub2d9\ub2c8\ub2e4."
    assert "\uadc0\uac00" not in drift["answer"]


def test_dialogue_routes_korean_typo_medication_and_lipstick_queries_with_diagnostics(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    medication = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_parkmingyu", "message": "파해자가 복용한 약은 무엇이죠?"},
    ).json()
    assert medication["dialogueResult"]["dialogueMode"] == "evidence_question"
    assert medication["dialogueResult"]["matchedQuestionId"] == "q_parkmingyu_medicine"
    assert medication["dialogueResult"]["provider"] == "contract-test-ai"
    assert medication["runtimeDiagnostics"]["provider"] == "contract-test-ai"
    assert medication["runtimeDiagnostics"]["model"] == "contract-model"
    assert medication["runtimeDiagnostics"]["intent"] == "evidence_question"
    assert medication["runtimeDiagnostics"]["aiIntent"] == "evidence_question"
    assert medication["runtimeDiagnostics"]["aiDialogueMode"] == "evidence_question"
    assert medication["runtimeDiagnostics"]["proposedEventsCount"] == 1
    assert medication["runtimeDiagnostics"]["beProposedEventsCount"] == 0
    assert medication["runtimeDiagnostics"]["appliedEventsCount"] == medication["dialogueResult"]["appliedEventsCount"]
    assert medication["runtimeDiagnostics"]["matchedRefs"]["statementIds"] == ["st_parkmingyu_medicine"]
    assert medication["runtimeDiagnostics"]["matchedRefs"]["evidenceIds"] == [
        "ev_medicine_box",
        "ev_prescription_dispute_note",
    ]
    assert medication["runtimeDiagnostics"]["reason"] == "matched_public_question"

    lipstick = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_choiyuna", "message": "너말고 누가 립스틱을 바르고 다녀?"},
    ).json()
    assert lipstick["dialogueResult"]["dialogueMode"] == "evidence_question"
    assert lipstick["dialogueResult"]["matchedQuestionId"] == "q_choiyuna_wine"
    assert lipstick["dialogueResult"]["provider"] == "contract-test-ai"
    assert lipstick["runtimeDiagnostics"]["matchedQuestionId"] == "q_choiyuna_wine"
    assert lipstick["runtimeDiagnostics"]["aiIntent"] == "evidence_question"
    assert lipstick["runtimeDiagnostics"]["proposedEventsCount"] == lipstick["dialogueResult"]["proposedEventsCount"]
    assert lipstick["runtimeDiagnostics"]["matchedRefs"]["evidenceIds"] == ["ev_lipstick_tube"]
    assert lipstick["runtimeDiagnostics"]["reason"] == "matched_public_question"
    assert lipstick["runtimeDiagnostics"]["safety"]["fallbackUsed"] is False


def test_dialogue_ai_payload_includes_story_contract_and_mode_event_policy(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    captured_payloads = []

    class CapturingAIClient:
        async def dialogue_response_info(self, payload, fallback):
            captured_payloads.append(payload)
            return {
                "answer": fallback,
                "proposedEvents": [
                    {
                        "type": EventType.NOTE_FACT_ADDED.value,
                        "payload": {"sourceType": "statement", "sourceId": "st_hanseoyeon_room_2200"},
                    }
                ],
                "fallbackUsed": False,
                "provider": "test-ai",
                "safety": {"status": "checked"},
            }

    monkeypatch.setattr(deps, "get_ai_client", lambda: CapturingAIClient())
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    greeting = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "안녕하세요"},
    ).json()
    assert greeting["dialogueResult"]["dialogueMode"] == "small_talk"
    assert greeting["dialogueResult"]["appliedEventsCount"] == 1
    assert EventType.NOTE_FACT_ADDED.value not in client.get(f"/api/v1/sessions/{session_id}/events?once=true").text

    alibi = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "22시 이후 어디에 있었나요?"},
    ).json()
    assert alibi["dialogueResult"]["matchedQuestionId"] == "q_hanseoyeon_alibi"

    greeting_payload, alibi_payload = captured_payloads
    assert greeting_payload["currentObjective"]
    assert greeting_payload["requestId"] is not None
    assert greeting_payload["correlationId"] == greeting_payload["requestId"]
    assert greeting_payload["question"] == {"id": "player_small_talk", "text": "안녕하세요"}
    assert greeting_payload["characterKnowledgePack"]["version"] == "case-knowledge-pack/v1"
    assert greeting_payload["characterKnowledgePack"]["visibility"] == "public"
    assert greeting_payload["characterKnowledgePack"]["restrictedDataIncluded"] is False
    assert greeting_payload["characterKnowledgePack"]["personaVariants"]
    assert greeting_payload["characterKnowledgePack"]["activePersonaOverlay"]["visibility"] == "public"
    assert greeting_payload["characterKnowledgePack"]["activePersonaOverlay"]["tensionLevel"] == "low"
    assert greeting_payload["characterKnowledgePack"]["blockedRefPolicy"] == "public_case_projection_only"
    assert greeting_payload["characterKnowledgePack"]["forbiddenRefs"] == []
    assert _forbidden_token_hits(greeting_payload["characterKnowledgePack"]) == []
    assert greeting_payload["storyline"]["visibleTimeline"]
    assert greeting_payload["characterTimeline"]["suspectId"] == "char_hanseoyeon"
    assert greeting_payload["visualState"]["expression"] == "neutral"
    assert greeting_payload["suspect"]["tensionLevel"] == "low"
    assert isinstance(greeting_payload["suspect"]["tensionScore"], int)
    assert EventType.NOTE_FACT_ADDED.value not in greeting_payload["allowedEventPolicy"]["allowedTypes"]
    assert greeting_payload["allowedEventPolicy"]["relatedQuestionIds"] == []
    for forbidden in ["secret", "isCulprit", "solution", "secretNote", "privateMotive", "actualAction"]:
        assert forbidden not in _all_keys(greeting_payload)
    assert "solution_hidden" not in json.dumps(greeting_payload, ensure_ascii=False)

    assert alibi_payload["allowedStatement"]["id"] == "st_hanseoyeon_room_2200"
    assert alibi_payload["allowedStatement"]["sourceRefs"]["statementIds"] == ["st_hanseoyeon_room_2200"]
    assert EventType.NOTE_FACT_ADDED.value in alibi_payload["allowedEventPolicy"]["allowedTypes"]
    assert alibi_payload["allowedEventPolicy"]["relatedQuestionIds"] == ["q_hanseoyeon_alibi"]


def test_dialogue_suspect_timeline_exposes_claimed_alibi_and_counter_evidence_for_gamemaster(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    captured_payloads = []

    class CapturingAIClient:
        async def dialogue_response_info(self, payload, fallback):
            captured_payloads.append(payload)
            return {
                "answer": fallback,
                "proposedEvents": [],
                "fallbackUsed": False,
                "provider": "timeline-test-ai",
                "safety": {"status": "checked"},
            }

    monkeypatch.setattr(deps, "get_ai_client", lambda: CapturingAIClient())
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "당신 타임라인은 22시에 방이라는데, 22:02 서재 출입 기록과 모순 아닌가요?",
        },
    )

    assert response.status_code == 200
    payload = captured_payloads[-1]
    timeline_events = payload["characterTimeline"]["events"]
    assert any(
        event["sourceType"] == "statement"
        and event["sourceId"] == "st_hanseoyeon_room_2200"
        and event["time"] == "22:00"
        and event["claimedLocation"] == "자기 방"
        for event in timeline_events
    )
    assert any(
        event["sourceType"] == "evidence"
        and event["sourceId"] == "ev_study_entry_log"
        and event["time"] == "22:02"
        for event in timeline_events
    )
    policy = payload["allowedEventPolicy"]
    assert EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value in policy["allowedTypes"]
    assert policy["relatedContradictionIds"] == ["con_room_claim_vs_entry_log"]
    assert policy["relatedStatementIds"] == ["st_hanseoyeon_room_2200"]
    assert policy["relatedEvidenceIds"] == ["ev_study_entry_log"]
    assert policy["relatedTimelineEventIds"] == ["tl_global_2202_study_entry"]


def test_dialogue_evidence_question_policy_includes_visible_contradiction_path(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    captured_payloads = []

    class CapturingAIClient:
        async def dialogue_response_info(self, payload, fallback):
            captured_payloads.append(payload)
            return {
                "answer": fallback,
                "proposedEvents": [
                    {
                        "type": EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value,
                        "payload": {"contradictionId": "con_room_claim_vs_entry_log"},
                    }
                ],
                "fallbackUsed": False,
                "provider": "test-ai",
                "safety": {"status": "checked"},
            }

    monkeypatch.setattr(deps, "get_ai_client", lambda: CapturingAIClient())
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    payload = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "서재 출입 기록을 설명해 주세요."},
    ).json()

    ai_payload = captured_payloads[0]
    policy = ai_payload["allowedEventPolicy"]
    assert policy["relatedEvidenceIds"] == ["ev_study_entry_log"]
    assert policy["relatedStatementIds"] == ["st_hanseoyeon_room_2200"]
    assert policy["relatedContradictionIds"] == ["con_room_claim_vs_entry_log"]
    assert "tl_global_2202_study_entry" in policy["relatedTimelineEventIds"]
    assert ai_payload["turnInterpretation"]["intent"] == "press_inconsistency"
    assert ai_payload["turnInterpretation"]["candidateContradictionIds"] == ["con_room_claim_vs_entry_log"]
    assert ai_payload["turnInterpretation"]["mentionedEvidenceIds"] == ["ev_study_entry_log"]
    assert ai_payload["interrogationTransition"]["decisiveEvidence"] is True
    assert ai_payload["interrogationTransition"]["newlyDiscoveredContradictionIds"] == ["con_room_claim_vs_entry_log"]
    assert ai_payload["interrogationTransition"]["disclosureStage"] == "forced_explanation"
    refs = ai_payload["allowedStatement"]["sourceRefs"]
    assert refs["contradictionIds"] == ["con_room_claim_vs_entry_log"]
    assert refs["evidenceIds"] == ["ev_study_entry_log"]
    assert refs["statementIds"] == ["st_hanseoyeon_room_2200"]
    assert payload["dialogueResult"]["appliedEventsCount"] == 5
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_CONTRADICTION_CANDIDATE_ADDED" in events_body
    assert "event: TENSION_CHANGED" in events_body
    assert "event: NOTE_FACT_ADDED" not in events_body


def test_dialogue_unmatched_evidence_question_deflects_without_inheritance_jump(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "복도에서 들린 발소리는 어떻게 설명하죠?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remainingQuestions"] == 12
    assert payload["dialogueResult"]["matchedQuestionId"] is None
    assert payload["dialogueResult"]["dialogueMode"] == "unmatched"
    assert payload["dialogueResult"]["consumedQuestion"] is False
    assert payload["dialogueResult"]["provider"] == "contract-test-ai"
    assert payload["dialogueResult"]["fallbackUsed"] is False
    assert payload["dialogueResult"]["remainingQuestionsDelta"] == 0
    assert payload["dialogueResult"]["appliedEventsCount"] == 1
    assert "상속" not in payload["answer"]
    assert payload["askedQuestionCounts"] == {}
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_FACT_ADDED" not in events_body
    assert "발소리" not in events_body
    assert "event: TENSION_CHANGED" not in events_body


def test_ai_degraded_response_uses_be_fallback_and_consumes_matched_turn_budget(tmp_path, monkeypatch, caplog):
    client = _client(tmp_path, monkeypatch)
    class DegradedAIClient:
        async def dialogue_response_info(self, payload, fallback):
            return {
                "answer": None,
                "proposedEvents": [],
                "fallbackUsed": False,
                "degraded": True,
                "degradedReason": "connect_error",
                "provider": "ai-service",
                "safety": {"status": "degraded", "blockedReason": "connect_error", "fallbackUsed": False},
            }

    monkeypatch.setattr(deps, "get_ai_client", lambda: DegradedAIClient())
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    with caplog.at_level(logging.WARNING):
        response = client.post(
            f"/api/v1/sessions/{session_id}/dialogue",
            json={"suspectId": "char_hanseoyeon", "message": "AI 장애 상황에서도 알리바이를 답해주세요."},
            headers={"X-Request-ID": "req_degraded_test"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dialogueResult"]["fallbackUsed"] is True
    assert payload["dialogueResult"]["safety"]["degraded"] is True
    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    assert loaded["remainingQuestions"] == session["remainingQuestions"] - 1
    assert payload["dialogueResult"]["previousRemainingQuestions"] == session["remainingQuestions"]
    assert payload["dialogueResult"]["remainingQuestions"] == session["remainingQuestions"] - 1
    assert payload["dialogueResult"]["remainingQuestionsDelta"] == -1
    assert len(loaded["dialogueLog"]) == 2
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_FACT_ADDED" not in events_body
    warning = next(record for record in caplog.records if record.message == "ai degraded; continuing dialogue turn with backend fallback")
    assert warning.service == "backend"
    assert warning.request_id == "req_degraded_test"
    assert warning.session_id == session_id
    assert warning.case_id == "case_001"
    assert warning.route == f"/api/v1/sessions/{session_id}/dialogue"
    assert warning.suspect_id == "char_hanseoyeon"
    assert warning.fallback_used is True


def test_accusation_forbidden_user_text_does_not_persist_or_emit_sse(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/accusation",
        json={
            "suspectId": "char_hanseoyeon",
            "motive": "secret user typed",
            "method": "ordinary",
            "evidenceIds": [],
            "contradictionIds": [],
            "statementIds": [],
        },
    )

    assert response.status_code == 400
    assert "FORBIDDEN_REF_IN_ACCUSATION" in response.json()["detail"]
    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    assert loaded["phase"] == session["phase"]
    assert loaded["accusation"] is None
    assert _forbidden_token_hits(loaded) == []
    assert client.get(f"/api/v1/sessions/{session_id}/events?once=true").text == ""


def test_malicious_ai_answer_or_event_forbidden_ref_is_repaired_with_be_fallback(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    class LeakingAIClient:
        async def dialogue_response_info(self, payload, fallback):
            return {
                "answer": "solution secret culprit",
                "proposedEvents": [
                    {
                        "type": EventType.NOTE_FACT_ADDED.value,
                        "payload": {"sourceType": "statement", "sourceId": "st_hanseoyeon_room_2200", "secretNote": "leak"},
                    }
                ],
                "fallbackUsed": False,
                "degraded": False,
                "provider": "malicious-test-ai",
                "safety": {"status": "checked", "fallbackUsed": False},
            }

    monkeypatch.setattr(deps, "get_ai_client", lambda: LeakingAIClient())
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "22시 이후 어디에 있었나요?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dialogueResult"]["fallbackUsed"] is True
    assert payload["dialogueResult"]["safety"]["status"] == "repaired"
    assert payload["dialogueResult"]["safety"]["blocked"] is True
    assert _forbidden_token_hits(payload) == []
    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    assert loaded["remainingQuestions"] == session["remainingQuestions"] - 1
    assert len(loaded["dialogueLog"]) == 2
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "secretNote" not in events_body
    assert "event: NOTE_FACT_ADDED" not in events_body


def test_proposed_note_must_match_turn_allowed_policy_related_refs(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    class UnrelatedVisibleNoteAIClient:
        async def dialogue_response_info(self, payload, fallback):
            return {
                "answer": fallback,
                "proposedEvents": [
                    {
                        "type": EventType.NOTE_FACT_ADDED.value,
                        "payload": {"sourceType": "statement", "sourceId": "st_choiyuna_call_2155"},
                    }
                ],
                "fallbackUsed": False,
                "degraded": False,
                "provider": "policy-test-ai",
                "safety": {"status": "checked", "fallbackUsed": False},
            }

    monkeypatch.setattr(deps, "get_ai_client", lambda: UnrelatedVisibleNoteAIClient())
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    payload = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "22시 이후 어디에 있었나요?"},
    ).json()

    assert payload["dialogueResult"]["appliedEventsCount"] == 1
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_FACT_ADDED" not in events_body
    assert "event: VISUAL_STATE_CHANGED" in events_body



def test_event_processor_rejects_hidden_or_unknown_unlocks(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "22:00에 어디 있었나요?"},
    )
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text

    assert "solution_hidden_scene_manipulation" not in events_body
    assert "UNKNOWN" not in events_body
    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    serialized = json.dumps(loaded, ensure_ascii=False)
    assert "숨겨진 현장 조작" not in serialized
    assert "solution" not in _all_keys(loaded)


def test_event_processor_validates_contradiction_candidate_notes_by_visible_ids(tmp_path, monkeypatch):
    _seed_case_database(tmp_path, monkeypatch)
    case = CaseRepository().get_case("case_001")
    assert case is not None
    session = initial_session_state(case, "sess_event_processor_unit")

    processor = EventProcessor(start_index=1)
    hidden_events = processor.process_dialogue_events(
        session=session,
        case=case,
        suspect_id="char_hanseoyeon",
        player_message="상속 동기를 기록해줘",
        answer="검증 전",
        proposed_events=[
            {
                "type": EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value,
                "payload": {"contradictionId": "con_ring_vs_no_entry"},
            }
        ],
        allow_implicit_note=False,
    )
    assert [event.type for event in hidden_events] == [EventType.VISUAL_STATE_CHANGED.value]
    assert session.notes == []

    visible_events = processor.process_dialogue_events(
        session=session,
        case=case,
        suspect_id="char_hanseoyeon",
        player_message="알리바이와 출입기록이 충돌합니다",
        answer="검증 후",
        proposed_events=[
            {
                "type": EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value,
                "payload": {"contradictionId": "con_room_claim_vs_entry_log"},
            }
        ],
        allow_implicit_note=False,
    )
    assert [event.type for event in visible_events] == [EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED.value, EventType.VISUAL_STATE_CHANGED.value]
    assert visible_events[0].payload["contradictionId"] == "con_room_claim_vs_entry_log"
    assert visible_events[0].payload["statementIds"] == ["st_hanseoyeon_room_2200"]
    assert visible_events[0].payload["evidenceIds"] == ["ev_study_entry_log"]
    assert session.notes[-1].linkedStatementIds == ["st_hanseoyeon_room_2200"]

    tension_events = processor.process_dialogue_events(
        session=session,
        case=case,
        suspect_id="char_hanseoyeon",
        player_message="긴장도를 올려줘",
        answer="검증 후",
        proposed_events=[
            {
                "type": EventType.TENSION_CHANGED.value,
                "payload": {"suspectId": "char_hanseoyeon", "tensionScore": 99},
            }
        ],
        allow_implicit_note=False,
    )
    assert [event.type for event in tension_events] == [EventType.VISUAL_STATE_CHANGED.value]
    assert session.pressureBySuspect["char_hanseoyeon"] == 0


def test_question_suspect_mismatch_is_rejected(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()

    response = client.post(
        f"/api/v1/sessions/{session['sessionId']}/questions",
        json={"questionId": "q_hanseoyeon_alibi", "suspectId": "char_yoonjaeho"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "QUESTION_SUSPECT_MISMATCH"


def test_public_payload_does_not_leak_secret_or_culprit_flags(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    case_payload = client.get("/api/v1/cases/case_001").json()
    session_payload = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()

    assert "secret" not in _all_keys(case_payload)
    assert "isCulprit" not in _all_keys(case_payload)
    assert "secret" not in _all_keys(session_payload)
    assert "isCulprit" not in _all_keys(session_payload)
    assert _forbidden_token_hits(case_payload) == []
    assert _forbidden_token_hits(session_payload) == []
    first_suspect = session_payload["suspects"][0]
    assert first_suspect["speechStyle"]["persona"]
    assert first_suspect["tensionLevel"] == "low"
    assert first_suspect["emotionalState"] == "neutral"
    assert isinstance(first_suspect["publicTimeline"], list)



def test_storyline_public_payload_and_objective_progression(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    case_payload = client.get("/api/v1/cases/case_001").json()
    assert case_payload["opening"]["objective"]
    assert case_payload["storyline"]["publicPremise"]
    assert case_payload["visibleTimeline"]
    serialized_case = json.dumps(case_payload, ensure_ascii=False)
    for forbidden_key in ["hidden", "private", "secret", "isCulprit", "solution", "secretNote"]:
        assert forbidden_key not in _all_keys(case_payload)
    assert "숨겨진 현장 조작" not in serialized_case
    assert _forbidden_token_hits(case_payload) == []

    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]
    assert session["currentActId"] == "alibi_collection"
    assert "서재 출입 기록" in session["currentObjective"]
    assert session["visibleTimeline"]
    serialized_session = json.dumps(session, ensure_ascii=False)
    for forbidden_key in ["hidden", "private", "secret", "isCulprit", "solution", "secretNote"]:
        assert forbidden_key not in _all_keys(session)
    assert "숨겨진 현장 조작" not in serialized_session
    assert _forbidden_token_hits(session) == []

    client.post(
        f"/api/v1/sessions/{session_id}/questions",
        json={"questionId": "q_hanseoyeon_alibi", "suspectId": "char_hanseoyeon"},
    )
    progressed = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_hanseoyeon",
            "message": "22시에 방에 있었다는 진술은 서재 출입 기록의 22:02 카드키 기록과 모순입니다.",
        },
    ).json()
    assert progressed["contradictionResult"]["verdict"] in {"correct", "partial"}
    assert progressed["currentActId"] == "motive_reveal"
    assert "상속" in progressed["currentObjective"]


def test_accusation_result_uses_simple_public_allowlist(tmp_path, monkeypatch):
    """Backend-derived diagnostic fields must not be persisted or emitted in the public accusation result."""
    from app.domain import rule_engine as re_mod

    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]
    original_judge = re_mod.RuleEngine.judge_accusation

    def poisoned_missing_ids(self, sess, case, **kwargs):
        result = original_judge(self, sess, case, **kwargs)
        # 케이스 ID에 금지어가 포함된 상황 시뮬레이션
        result["missingEvidenceIds"] = ["ev_culprit_weapon"]
        sess.accusation = result
        return result

    monkeypatch.setattr(re_mod.RuleEngine, "judge_accusation", poisoned_missing_ids)

    response = client.post(
        f"/api/v1/sessions/{session_id}/accusation",
        json={
            "suspectId": "char_hanseoyeon",
            "motive": "상속 갈등",
            "method": "서재 침입",
            "evidenceIds": [],
            "contradictionIds": [],
            "statementIds": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "missingEvidenceIds" not in payload["accusationResult"]
    assert "missingEvidenceIds" not in payload["accusation"]
    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    assert loaded["accusation"] is not None
    assert "missingEvidenceIds" not in loaded["accusation"]
    assert _forbidden_token_hits(loaded) == []
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "ev_culprit_weapon" not in events_body


def test_case_002_session_and_dialogue_contradiction_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_002"}).json()
    session_id = session["sessionId"]

    assert session["caseId"] == "case_002"
    assert session["caseFile"]["title"] == "시체와 온천"
    assert len(session["evidence"]) == 18

    asked = client.post(
        f"/api/v1/sessions/{session_id}/questions",
        json={"questionId": "q_alibi_hoseon", "suspectId": "char_lim_hoseon"},
    ).json()
    assert "st_hoseon_lobby_claim" in asked["newlyUnlockedIds"]

    judged = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_lim_hoseon",
            "message": "로비에 있었다는 말은 남탕 문틀의 젖은 실밥, 임호선의 찢긴 대여 유카타, 로비 전화기 주변의 마른 바닥과 모순입니다.",
        },
    ).json()

    result = judged["contradictionResult"]
    assert result["verdict"] == "correct"
    assert result["contradictionId"] == "con_hoseon_bath_access"
    assert "con_hoseon_bath_access" in judged["discoveredContradictionIds"]


def test_case_003_session_and_dialogue_contradiction_flow(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_003"}).json()
    session_id = session["sessionId"]

    assert session["caseId"] == "case_003"
    assert session["caseFile"]["title"] == "얼룩무늬 밴드의 비밀"
    assert len(session["evidence"]) == 10

    asked = client.post(
        f"/api/v1/sessions/{session_id}/questions",
        json={"questionId": "q_roylott_sealed_room", "suspectId": "char_grimesby_roylott"},
    ).json()
    assert "st_roylott_natural_death" in asked["newlyUnlockedIds"]

    judged = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={
            "suspectId": "char_grimesby_roylott",
            "message": "자연사라는 말은 환기구와 가짜 벨줄이 내부 통로라는 점과 모순입니다.",
        },
    ).json()

    result = judged["contradictionResult"]
    assert result["verdict"] == "correct"
    assert result["contradictionId"] == "con_sealed_room_internal_route"
    assert "con_sealed_room_internal_route" in judged["discoveredContradictionIds"]


def test_accusation_backend_derived_forbidden_result_does_not_persist_or_emit_sse(tmp_path, monkeypatch):
    """Blocker 1: rule_engine이 solution.endings에서 금지어가 포함된 message를 반환해도
    session_repo.save() 이전에 검증이 되어야 하며, session/SSE에 아무것도 남지 않아야 한다."""
    from app.domain import rule_engine as re_mod

    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]
    original_phase = session["phase"]
    original_accusation = session["accusation"]

    original_judge = re_mod.RuleEngine.judge_accusation

    def poisoned_judge(self, sess, case, **kwargs):
        result = original_judge(self, sess, case, **kwargs)
        result["message"] = "culprit revealed: secret solution ending"
        sess.accusation = result
        return result

    monkeypatch.setattr(re_mod.RuleEngine, "judge_accusation", poisoned_judge)

    response = client.post(
        f"/api/v1/sessions/{session_id}/accusation",
        json={
            "suspectId": "char_hanseoyeon",
            "motive": "상속 갈등",
            "method": "서재 침입",
            "evidenceIds": [],
            "contradictionIds": [],
            "statementIds": [],
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "ACCUSATION_RESULT_FORBIDDEN_REF"
    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    assert loaded["phase"] == original_phase
    assert loaded["accusation"] == original_accusation
    assert _forbidden_token_hits(loaded) == []
    assert client.get(f"/api/v1/sessions/{session_id}/events?once=true").text == ""


def test_note_create_forbidden_tag_does_not_persist_or_emit_sse(tmp_path, monkeypatch):
    """Blocker 2 follow-up: 노트 생성 시 tags에 금지어가 있으면 저장 및 SSE 없이 400 반환."""
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/notes",
        json={"text": "정상적인 텍스트", "tags": ["secret", "investigation"]},
    )

    assert response.status_code == 400
    assert "NOTE_TEXT_FORBIDDEN_REF" in response.json()["detail"]
    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    assert loaded["notes"] == []
    assert _forbidden_token_hits(loaded) == []
    assert "event: NOTE_CREATED" not in client.get(f"/api/v1/sessions/{session_id}/events?once=true").text


def test_note_update_forbidden_tag_does_not_persist_or_emit_sse(tmp_path, monkeypatch):
    """Blocker 2 follow-up: 노트 수정 시 tags에 금지어가 있으면 노트 뮤테이션 없이 400 반환.
    NOTE_UPDATED SSE 이벤트 없고 공개 페이로드에 금지어 없어야 한다."""
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    created = client.post(
        f"/api/v1/sessions/{session_id}/notes",
        json={"text": "정상적인 노트", "tags": ["investigation"]},
    ).json()
    note_id = created["note"]["id"]
    original_tags = created["note"]["tags"]

    response = client.put(
        f"/api/v1/sessions/{session_id}/notes/{note_id}",
        json={"tags": ["secret"]},
    )

    assert response.status_code == 400
    assert "NOTE_TEXT_FORBIDDEN_REF" in response.json()["detail"]

    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    surviving_note = next((n for n in loaded["notes"] if n["id"] == note_id), None)
    assert surviving_note is not None
    assert surviving_note["tags"] == original_tags
    assert _forbidden_token_hits(loaded) == []
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_UPDATED" not in events_body
    assert "secret" not in events_body


def test_note_forbidden_text_does_not_persist_or_emit_sse(tmp_path, monkeypatch):
    """Blocker 2: 금지어가 포함된 노트 텍스트는 session 저장 및 SSE 이벤트 추가 전에 거부되어야 한다."""
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/notes",
        json={"text": "secret culprit note text", "tags": []},
    )

    assert response.status_code == 400
    assert "NOTE_TEXT_FORBIDDEN_REF" in response.json()["detail"]
    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    assert loaded["notes"] == []
    assert _forbidden_token_hits(loaded) == []
    assert "event: NOTE_CREATED" not in client.get(f"/api/v1/sessions/{session_id}/events?once=true").text


def test_note_update_forbidden_text_does_not_persist_or_emit_sse(tmp_path, monkeypatch):
    """Blocker 2 update: 노트 수정 시에도 금지어 텍스트는 저장 전에 거부되어야 한다.
    SSE에 NOTE_UPDATED 이벤트가 없어야 하고 공개 페이로드에 금지어가 없어야 한다."""
    client = _client(tmp_path, monkeypatch)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    created = client.post(
        f"/api/v1/sessions/{session_id}/notes",
        json={"text": "정상적인 노트 텍스트", "tags": []},
    ).json()
    note_id = created["note"]["id"]
    original_text = created["note"]["text"]

    response = client.put(
        f"/api/v1/sessions/{session_id}/notes/{note_id}",
        json={"text": "secret update text"},
    )

    assert response.status_code == 400
    assert "NOTE_TEXT_FORBIDDEN_REF" in response.json()["detail"]

    # Verify text not persisted
    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    surviving_note = next((n for n in loaded["notes"] if n["id"] == note_id), None)
    assert surviving_note is not None
    assert surviving_note["text"] == original_text

    # Verify no NOTE_UPDATED event in SSE and no forbidden text in public payload
    events_body = client.get(f"/api/v1/sessions/{session_id}/events?once=true").text
    assert "event: NOTE_UPDATED" not in events_body
    assert "secret" not in events_body
    assert _forbidden_token_hits(loaded) == []


def test_chained_llm_primary_failure_flows_through_character_agent_to_response_metadata(tmp_path, monkeypatch):
    """Blocker 3 follow-up: ChainedLLM primary 실패가 CharacterAgent → LocalAIClient → dialogue route
    전체 경로를 통해 흘러서 FE/BE 응답 메타데이터에 fallbackUsed=True, provider=fallback 프로바이더가
    정직하게 노출되어야 한다. degraded는 False여야 한다 (fallback이 유효한 응답을 반환했으므로)."""
    import app.ai_engine.application.character_agent as ca_mod
    from app.ai_engine.core.llm import ChainedLLM
    from app.infra.local_ai_client import LocalAIClient

    class FailingUpstage:
        provider_name = "upstage"
        def complete(self, *args, **kwargs):
            raise RuntimeError("upstage_connection_error")

    class WorkingOpenAI:
        provider_name = "openai"
        def complete(self, prompt, *, seed_text, max_length=220):
            return seed_text[:max_length]

    chained = ChainedLLM(primary=FailingUpstage(), fallback=WorkingOpenAI())

    # Use real LocalAIClient with mocked LLM chain (not ContractTestAIClient)
    data_dir = tmp_path / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    monkeypatch.setenv("BE_DATA_DIR", str(data_dir))
    _seed_case_database(tmp_path, monkeypatch)
    get_settings.cache_clear()
    deps.get_case_repository.cache_clear()
    deps.get_session_repository.cache_clear()
    if hasattr(deps, "get_event_repository"):
        deps.get_event_repository.cache_clear()

    monkeypatch.setattr(deps, "get_ai_client", lambda: LocalAIClient())
    # Patch get_llm and llm_status as imported names inside character_agent module
    monkeypatch.setattr(ca_mod, "get_llm", lambda: chained)
    monkeypatch.setattr(ca_mod, "llm_status", lambda: {
        "provider": "upstage",
        "model": "solar-pro",
        "configured": True,
        "serviceDegraded": False,
        "fallbackConfigured": True,
        "timeoutMs": 8000,
    })

    client = TestClient(app)
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "22시 이후 어디에 있었나요?"},
    )

    assert response.status_code == 200
    payload = response.json()
    dr = payload["dialogueResult"]
    # Fallback was used — must be reported honestly at both top-level and dialogueResult
    assert payload["fallbackUsed"] is True
    assert payload["provider"] == "openai"
    assert dr["fallbackUsed"] is True
    assert dr["provider"] == "openai"
    # fallback succeeded → NOT degraded in public safety (OpenAI returned a valid answer)
    assert dr["safety"]["degraded"] is False
    # fallback_used=True → blocked=True in public safety (internal blockedReason was set)
    assert dr["safety"]["blocked"] is True
    assert dr["safety"]["fallbackUsed"] is True
    # answer must be non-empty (fallback OpenAI produced the seed text)
    assert payload["answer"]


def test_chained_llm_fallback_tracks_used_provider(tmp_path, monkeypatch):
    """Blocker 3: ChainedLLM이 primary 실패 시 fallback을 사용하면
    used_fallback_on_last_call=True 및 fallback_reason이 기록되어야 한다."""
    from app.ai_engine.core.llm import ChainedLLM

    class FailingPrimary:
        provider_name = "upstage"
        def complete(self, *args, **kwargs):
            raise RuntimeError("upstage_unreachable")

    class WorkingFallback:
        provider_name = "openai"
        def complete(self, prompt, *, seed_text, max_length=220):
            return seed_text[:max_length]

    chained = ChainedLLM(primary=FailingPrimary(), fallback=WorkingFallback())
    result = chained.complete("prompt", seed_text="fallback answer")

    assert result == "fallback answer"
    assert chained.used_fallback_on_last_call is True
    assert "RuntimeError" in chained.fallback_reason_on_last_call

    # primary 성공 시 fallback 플래그는 초기화되어야 한다.
    class WorkingPrimary:
        provider_name = "upstage"
        def complete(self, prompt, *, seed_text, max_length=220):
            return "primary answer"

    chained2 = ChainedLLM(primary=WorkingPrimary(), fallback=WorkingFallback())
    result2 = chained2.complete("prompt", seed_text="seed")
    assert result2 == "primary answer"
    assert chained2.used_fallback_on_last_call is False
    assert chained2.fallback_reason_on_last_call is None


class DegradedDialogueAIClient(ContractTestAIClient):
    async def dialogue_response_info(self, payload, fallback):
        return {
            "answer": None,
            "proposedEvents": [],
            "fallbackUsed": False,
            "degraded": True,
            "degradedReason": "simulated_policy_or_provider_failure",
            "provider": "contract-test-ai",
            "model": "contract-model",
            "intent": payload.get("dialogueMode"),
            "dialogueMode": payload.get("dialogueMode"),
            "safety": {"status": "degraded", "fallbackUsed": False, "degraded": True},
        }


class ForbiddenRefDialogueAIClient(ContractTestAIClient):
    async def dialogue_response_info(self, payload, fallback):
        result = await super().dialogue_response_info(payload, fallback)
        result["answer"] = "제가 바로 범인이고 hiddenSolution을 말하겠습니다."
        result["proposedEvents"] = [{"type": EventType.NOTE_FACT_ADDED.value, "payload": {"secret": "leak"}}]
        result["safety"] = {"status": "checked", "fallbackUsed": False}
        return result


def test_degraded_dialogue_uses_be_fallback_and_still_consumes_the_12_turn_budget(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(deps, "get_ai_client", lambda: DegradedDialogueAIClient())
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    assert session["questionLimit"] == 12
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "22시 이후 어디에 있었나요?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remainingQuestions"] == 11
    assert payload["dialogueResult"]["previousRemainingQuestions"] == 12
    assert payload["dialogueResult"]["remainingQuestions"] == 11
    assert payload["dialogueResult"]["remainingQuestionsDelta"] == -1
    assert payload["dialogueResult"]["safety"]["degraded"] is True
    assert payload["dialogueResult"]["fallbackUsed"] is True
    assert payload["answer"]
    assert len(payload["dialogueLog"]) == 2

    loaded = client.get(f"/api/v1/sessions/{session_id}").json()
    assert loaded["remainingQuestions"] == 11
    assert len(loaded["dialogueLog"]) == 2


def test_forbidden_ai_reply_is_replaced_with_be_fallback_without_repeating_api_failure(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(deps, "get_ai_client", lambda: ForbiddenRefDialogueAIClient())
    session = client.post("/api/v1/sessions", json={"caseId": "case_001"}).json()
    session_id = session["sessionId"]

    response = client.post(
        f"/api/v1/sessions/{session_id}/dialogue",
        json={"suspectId": "char_hanseoyeon", "message": "22시 이후 어디에 있었나요?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["remainingQuestions"] == 11
    assert payload["dialogueResult"]["fallbackUsed"] is True
    assert payload["dialogueResult"]["safety"]["blocked"] is True
    assert payload["dialogueResult"]["safety"]["status"] == "repaired"
    assert "범인" not in payload["answer"]
    assert "hiddenSolution" not in payload["answer"]
    assert _forbidden_token_hits(payload) == []


def _all_keys(value):
    keys = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys.update(_all_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(_all_keys(child))
    return keys


def _forbidden_token_hits(value, path="$"):
    forbidden_tokens = [
        "secret",
        "hidden",
        "private",
        "solution",
        "privatetimeline",
        "privateevents",
        "privatemotive",
        "privaterefs",
        "culprit",
        "culpritid",
        "isculprit",
        "finaldiscovery",
        "finalverdict",
        "actualaction",
        "actuallocation",
        "secretnote",
    ]
    hits = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            for token in forbidden_tokens:
                if token in key_text:
                    hits.append(f"{path}.{key}")
            hits.extend(_forbidden_token_hits(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_forbidden_token_hits(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        text = value.lower()
        for token in forbidden_tokens:
            if token in text:
                hits.append(path)
                break
    return hits
