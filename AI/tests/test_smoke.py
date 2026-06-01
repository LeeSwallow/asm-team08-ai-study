import logging

from fastapi.testclient import TestClient
import pytest

import app.application.character_agent as character_agent
from app.main import app


client = TestClient(app)


class EchoLLM:
    def complete(self, *args: object, **kwargs: object) -> str:
        return str(kwargs.get("seed_text", ""))


def use_provider_backed_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(character_agent, "llm_status", lambda: {"provider": "openai", "model": "test-model"})
    monkeypatch.setattr(character_agent, "get_llm", lambda: EchoLLM())


PUBLIC_STORYLINE = {
    "currentObjective": "22시 전후 알리바이를 서로 대조하세요.",
    "currentActId": "alibi_collection",
    "publicPremise": "저택 서재에서 사건이 발생했고, 모든 용의자는 서로 다른 알리바이를 주장합니다.",
    "openingObjective": "용의자들의 기본 진술을 확보하세요.",
    "visibleTimeline": [
        {
            "time": "22:02",
            "title": "서재 출입 기록",
            "description": "한 인물의 출입 기록이 확인되었습니다.",
            "sourceType": "record",
            "sourceId": "record_entry_2202",
        },
        {
            "time": "22:05",
            "title": "출력되면 안 되는 숨은 기록",
            "description": "지하실 비밀 통로",
            "sourceType": "record",
            "sourceId": "hidden_record",
            "hidden": True,
            "secretNote": "한서연이 범인입니다.",
        },
    ],
    "secret": "한서연이 범인입니다.",
    "solution": "서재 출입 기록이 정답입니다.",
    "isCulprit": True,
    "secretNote": "hidden truth",
}


def assert_no_secret_payload_terms(text: str) -> None:
    assert "한서연이 범인" not in text
    assert "서재 출입 기록이 정답" not in text
    assert "hidden truth" not in text
    assert "secretNote" not in text
    assert "지하실 비밀 통로" not in text
    assert "유산 갈등" not in text
    assert "비공개 실제 행적" not in text
    assert "출력되면 안 되는 숨은 기록" not in text


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["provider"] == "deterministic-fallback"
    assert response.json()["fallbackConfigured"] is True
    assert response.json()["serviceDegraded"] is True


def test_dialogue_response_scoped_to_allowed_statement() -> None:
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {
                "id": "suspect_001",
                "name": "한서연",
                "role": "조카",
                "pressureState": "normal",
            },
            "question": {
                "id": "question_001",
                "text": "그날 저녁 9시 이후 어디에 있었나요?",
            },
            "allowedStatement": {
                "id": "statement_001",
                "text": "저는 22:00에 제 방에 있었어요.",
            },
            "style": {"tone": "calm_defensive", "maxLength": 180},
            "characterTimeline": {
                "suspectId": "suspect_001",
                "publicPersona": "차분하지만 방어적인 조카",
                "privateMotive": "유산 갈등",
                "events": [
                    {
                        "time": "22:00",
                        "claimedLocation": "자기 방",
                        "claimedAction": "혼자 있었다고 주장",
                        "relatedStatementIds": ["statement_001"],
                        "emotionalState": "tense",
                        "public": True,
                        "actualAction": "비공개 실제 행적",
                        "isLie": True,
                        "secretNote": "한서연이 범인입니다.",
                    }
                ],
            },
            "visualState": {
                "backgroundId": "mansion_study_night",
                "characterImageState": "tense",
            },
            "allowedEventPolicy": {
                "allowedTypes": ["NOTE_FACT_ADDED"],
                "relatedEvidenceIds": ["evidence_001"],
            },
            "storyline": PUBLIC_STORYLINE,
            "secret": "한서연이 범인입니다.",
            "solution": "서재 출입 기록이 정답입니다.",
            "isCulprit": True,
            "secretNote": "hidden truth",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["statementId"] == "statement_001"
    assert "저는 22:00에 제 방에 있었어요." in data["text"]
    assert data["visualState"]["suspectId"] == "suspect_001"
    assert data["visualState"]["backgroundId"] == "mansion_study_night"
    assert data["visualState"]["characterImageState"] == "tense"
    assert data["visualState"]["emotionalState"] is None
    assert data["provider"] == "deterministic-fallback"
    assert data["fallbackUsed"] is True
    assert data["degraded"] is True
    assert data["intent"] == "location_time"
    assert data["proposedEvents"] == []
    assert data["safety"]["violatesCaseFacts"] is False
    assert data["safety"]["fallbackUsed"] is True
    assert data["safety"]["blockedReason"] == "deterministic_fallback_selected"
    assert data["safety"]["repaired"] is False
    assert_no_secret_payload_terms(data["text"])


def test_dialogue_deterministic_fallback_conditions_on_free_text_intent() -> None:
    base_payload = {
        "sessionId": "session_001",
        "caseId": "case_001",
        "suspect": {
            "id": "suspect_001",
            "name": "한서연",
            "role": "조카",
            "pressureState": "normal",
            "publicPersona": "차분하지만 방어적인 조카",
        },
        "allowedStatement": {
            "id": "statement_001",
            "text": "저는 22:00에 제 방에 있었어요.",
        },
        "style": {"tone": "calm_defensive", "maxLength": 220},
    }

    greeting = client.post(
        "/internal/v1/dialogue/respond",
        json={**base_payload, "question": {"id": "free_text", "text": "안녕하세요"}},
    )
    location = client.post(
        "/internal/v1/dialogue/respond",
        json={**base_payload, "question": {"id": "free_text", "text": "22시 이후에는 어디에 있었나요?"}},
    )

    assert greeting.status_code == 200
    assert location.status_code == 200
    greeting_data = greeting.json()
    location_data = location.json()
    assert greeting_data["safety"]["fallbackUsed"] is True
    assert greeting_data["safety"]["provider"] == "deterministic-fallback"
    assert location_data["safety"]["fallbackUsed"] is True
    assert "저는 22:00에 제 방에 있었어요." not in greeting_data["text"]
    assert "저는 22:00에 제 방에 있었어요." in location_data["text"]
    assert "안녕하세요" in greeting_data["text"]
    assert "시간" in location_data["text"]
    assert greeting_data["text"] != location_data["text"]
    assert greeting_data["safety"]["repaired"] is False
    assert greeting_data["proposedEvents"] == []
    assert greeting_data["matchedRefs"] == {
        "statementIds": [],
        "timelineIds": [],
        "evidenceIds": [],
        "questionIds": [],
        "contradictionIds": [],
    }
    assert greeting_data["runtimeDiagnostics"]["intent"] == "greeting"
    assert greeting_data["runtimeDiagnostics"]["provider"] == "deterministic-fallback"
    assert greeting_data["runtimeDiagnostics"]["proposedEventsCount"] == 0
    assert location_data["safety"]["repaired"] is False


def test_dialogue_runtime_diagnostics_include_safe_ai_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    use_provider_backed_llm(monkeypatch)
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "char_hanseoyeon", "name": "한서연"},
            "dialogueMode": "evidence_question",
            "question": {"id": "free_text", "text": "와인잔에 립스틱 자국이 있던데요"},
            "allowedStatement": {
                "id": "st_lipstick",
                "text": "그 잔에 대해 제가 직접 확인한 건 없습니다.",
                "sourceRefs": {"statementIds": ["st_lipstick"], "evidenceIds": ["ev_wine_lipstick"]},
            },
            "allowedEventPolicy": {
                "allowedTypes": ["NOTE_FACT_ADDED"],
                "relatedStatementIds": ["st_lipstick"],
                "relatedEvidenceIds": ["ev_wine_lipstick"],
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "evidence"
    assert data["provider"] == "openai"
    assert not data["text"].startswith("그 단서만으로 단정할 수는 없습니다")
    assert "그 와인잔 이야기를 제게 돌리지 마세요." in data["text"]
    assert "립스틱 자국은 공개된 단서와 대조해 보시죠." in data["text"]
    assert data["matchedRefs"]["statementIds"] == ["st_lipstick"]
    assert data["matchedRefs"]["evidenceIds"] == ["ev_wine_lipstick"]
    assert data["proposedEventsCount"] == len(data["proposedEvents"])
    assert data["runtimeDiagnostics"]["matchedEvidenceIds"] == ["ev_wine_lipstick"]
    assert data["runtimeDiagnostics"]["safety"]["repaired"] is False


def test_dialogue_smoke_greeting_alibi_hallway_and_evidence_are_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    use_provider_backed_llm(monkeypatch)
    base_payload = {
        "sessionId": "session_001",
        "caseId": "case_001",
        "suspect": {
            "id": "char_hanseoyeon",
            "name": "한서연",
            "role": "조카",
            "publicProfile": "차갑고 계산적인 태도를 유지하지만 질문을 통제하려 한다.",
            "speechStyle": {"vocabulary": ["정확히", "오해"]},
            "tensionLevel": "low",
            "pressure": 0,
            "emotionalState": "neutral",
            "expression": "confident_lying",
        },
        "visualState": {
            "backgroundId": "mansion_study_night",
            "characterImageState": "neutral",
            "tensionLevel": "low",
            "expression": "confident_lying",
        },
        "allowedEventPolicy": {
            "allowedTypes": ["NOTE_FACT_ADDED", "NOTE_CONTRADICTION_CANDIDATE_ADDED"],
            "relatedStatementIds": ["st_hanseoyeon_room_2200"],
            "relatedTimelineEventIds": ["ctl_hanseoyeon_2200_claim_room"],
        },
        "style": {"tone": "neutral", "maxLength": 260},
    }

    greeting = client.post(
        "/internal/v1/dialogue/respond",
        json={
            **base_payload,
            "dialogueMode": "small_talk",
            "question": {"id": "free_text", "text": "안녕하세요"},
            "allowedStatement": {"id": "st_hanseoyeon_room_2200", "text": "저는 22시 이후 계속 제 방에 있었습니다."},
        },
    ).json()
    alibi = client.post(
        "/internal/v1/dialogue/respond",
        json={
            **base_payload,
            "dialogueMode": "case_question",
            "question": {"id": "q_hanseoyeon_alibi", "text": "22시 이후 어디에 있었나요?"},
            "allowedStatement": {"id": "st_hanseoyeon_room_2200", "text": "저는 22시 이후 계속 제 방에 있었습니다."},
        },
    ).json()
    hallway = client.post(
        "/internal/v1/dialogue/respond",
        json={
            **base_payload,
            "dialogueMode": "unmatched",
            "question": {"id": "free_text", "text": "복도에서 누굴 봤나요?"},
            "allowedStatement": {"id": "st_hanseoyeon_room_2200", "text": "저는 22시 이후 계속 제 방에 있었습니다."},
        },
    ).json()
    evidence = client.post(
        "/internal/v1/dialogue/respond",
        json={
            **base_payload,
            "dialogueMode": "evidence_question",
            "question": {"id": "free_text", "text": "서재 출입 기록을 설명해 주세요."},
            "allowedStatement": {
                "id": "st_hanseoyeon_room_2200",
                "text": "저는 22시 이후 계속 제 방에 있었습니다.",
                "sourceRefs": {
                    "statementIds": ["st_hanseoyeon_room_2200"],
                    "timelineIds": ["ctl_hanseoyeon_2200_claim_room"],
                    "evidenceIds": ["ev_study_entry_log"],
                },
            },
            "allowedEventPolicy": {
                "allowedTypes": ["NOTE_CONTRADICTION_CANDIDATE_ADDED"],
                "relatedEvidenceIds": ["ev_study_entry_log"],
                "relatedStatementIds": ["st_hanseoyeon_room_2200"],
                "relatedTimelineEventIds": ["ctl_hanseoyeon_2200_claim_room"],
                "relatedContradictionIds": ["con_room_claim_vs_entry_log"],
            },
        },
    ).json()

    assert greeting["intent"] == "greeting"
    assert "저는 22시 이후 계속 제 방에 있었습니다." not in greeting["text"]
    assert greeting["proposedEvents"] == []
    assert alibi["intent"] == "location_time"
    assert "정확히" in alibi["text"]
    assert "저는 22시 이후 계속 제 방에 있었습니다." in alibi["text"]
    assert hallway["intent"] == "unmatched"
    assert "유산" not in hallway["text"]
    assert "저는 22시 이후 계속 제 방에 있었습니다." not in hallway["text"]
    assert hallway["proposedEvents"] == []
    assert evidence["intent"] == "evidence"
    assert "유산" not in evidence["text"]
    assert evidence["proposedEvents"][0]["type"] == "NOTE_CONTRADICTION_CANDIDATE_ADDED"
    assert evidence["proposedEvents"][0]["payload"]["contradictionId"] == "con_room_claim_vs_entry_log"
    assert evidence["visualState"]["suspectId"] == "char_hanseoyeon"
    assert evidence["visualState"]["expression"] == "confident_lying"
    for item in (greeting, alibi, hallway, evidence):
        assert item["safety"]["leaksSolution"] is False
        assert item["safety"]["violatesCaseFacts"] is False


def test_dialogue_uses_character_knowledge_pack_for_timeline_grounding(monkeypatch: pytest.MonkeyPatch) -> None:
    use_provider_backed_llm(monkeypatch)
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "char_hanseoyeon", "name": "한서연", "role": "조카"},
            "dialogueMode": "case_question",
            "question": {"id": "free_text", "text": "22시 이후 어디에 있었나요?"},
            "allowedStatement": {
                "id": "st_hanseoyeon_room_2200",
                "text": "저는 22시 이후 계속 제 방에 있었습니다.",
                "sourceRefs": {"statementIds": ["st_hanseoyeon_room_2200"], "timelineIds": ["ctl_hanseoyeon_2200_claim_room"]},
            },
            "characterKnowledgePack": {
                "suspectId": "char_hanseoyeon",
                "persona": "차갑고 계산적인 태도를 유지하지만 질문을 통제하려 한다.",
                "speechStyle": {"vocabulary": ["정확히"]},
                "visibleTimeline": [
                    {
                        "id": "ctl_hanseoyeon_2200_claim_room",
                        "text": "22시 이후 자기 방에 있었다고 주장한다.",
                        "sourceType": "statement",
                        "sourceId": "st_hanseoyeon_room_2200",
                        "relatedStatementIds": ["st_hanseoyeon_room_2200"],
                    }
                ],
                "alibiSnippets": [
                    {
                        "id": "alibi_room",
                        "text": "한서연의 공개 알리바이는 방에 있었다는 주장이다.",
                        "sourceType": "statement",
                        "sourceId": "st_hanseoyeon_room_2200",
                    }
                ],
                "secret": "한서연이 범인입니다.",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openai"
    assert data["fallbackUsed"] is False
    assert "정확히" in data["text"]
    assert "조카로서 조심스럽게 말씀드리면" not in data["text"]
    assert "저는 22시 이후 계속 제 방에 있었습니다." in data["text"]
    assert "범인" not in data["text"]
    assert data["safety"]["leaksSolution"] is False
    assert data["safety"]["violatesCaseFacts"] is False


def test_dialogue_uses_recent_dialogue_for_pressure_followup(monkeypatch: pytest.MonkeyPatch) -> None:
    use_provider_backed_llm(monkeypatch)
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {
                "id": "char_hanseoyeon",
                "name": "한서연",
                "role": "조카",
                "publicProfile": "차갑고 계산적인 태도",
                "speechStyle": {"vocabulary": ["정확히"]},
            },
            "dialogueMode": "case_question",
            "question": {"id": "free_text", "text": "왜 답변을 못해요? 말이 된다고 생각해?"},
            "allowedStatement": {
                "id": "st_hanseoyeon_room_2200",
                "text": "저는 22시 이후 계속 제 방에 있었습니다.",
            },
            "characterKnowledgePack": {
                "suspectId": "char_hanseoyeon",
                "persona": "차갑고 계산적이며 압박을 받으면 짧게 선을 긋는다.",
                "recentDialogue": [
                    {"speaker": "detective", "text": "22시 이후 어디에 있었나요?"},
                    {"speaker": "한서연", "text": "저는 22시 이후 계속 제 방에 있었습니다.", "statementId": "st_hanseoyeon_room_2200"},
                    {"speaker": "detective", "text": "왜 답변을 못해요?"},
                ],
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "몰아붙여도 지금 제 대답은 달라지지 않습니다." in data["text"]
    assert "방금 말씀드린 범위를 넘겨 단정하라고 하시면 곤란합니다." in data["text"]
    assert "저는 22시 이후 계속 제 방에 있었습니다." in data["text"]
    assert "질문이 조금 막연" not in data["text"]
    assert data["fallbackUsed"] is False
    assert data["safety"]["leaksSolution"] is False


def test_dialogue_uses_public_profile_and_tension_metadata_without_hidden_context(monkeypatch: pytest.MonkeyPatch) -> None:
    use_provider_backed_llm(monkeypatch)
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {
                "id": "suspect_001",
                "name": "한서연",
                "publicProfile": "차분하지만 압박을 받으면 말을 고르는 상속인",
                "speechStyle": {"pace": "hesitant"},
                "tensionLevel": "high",
                "pressure": 85,
                "tensionScore": 0.85,
                "emotionalState": "tense",
                "privateMotive": "유산 갈등",
            },
            "dialogueMode": "case_question",
            "question": {"id": "question_001", "text": "그 기록을 설명해 보세요"},
            "allowedStatement": {
                "id": "statement_001",
                "text": "저는 22:00에 제 방에 있었어요.",
            },
            "allowedEventPolicy": {
                "allowedTypes": ["NOTE_FACT_ADDED"],
                "relatedStatementIds": ["statement_001"],
                "relatedTimelineEventIds": ["timeline_public_2200"],
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "조심스럽게 말씀드리면" not in data["text"]
    assert "몰아붙여도" in data["text"]
    assert "저는 22:00에 제 방에 있었어요." in data["text"]
    assert_no_secret_payload_terms(data["text"])
    assert data["dialogueMode"] == "case_question"
    assert data["intent"] == "evidence"
    assert data["provider"] == "openai"
    assert data["fallbackUsed"] is False
    assert data["degraded"] is False
    assert data["safety"]["provider"] == "openai"
    assert data["proposedEvents"] == [
        {
            "type": "NOTE_FACT_ADDED",
            "payload": {
                "sourceType": "statement",
                "sourceId": "statement_001",
                "statementIds": ["statement_001"],
                "evidenceIds": [],
                "timelineIds": ["timeline_public_2200"],
            },
            "sourceRefs": {
                "statementIds": ["statement_001"],
                "timelineIds": ["timeline_public_2200"],
            },
            "confidence": 0.75,
        }
    ]


def test_dialogue_evidence_intent_prefers_contradiction_event_context(monkeypatch: pytest.MonkeyPatch) -> None:
    use_provider_backed_llm(monkeypatch)
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "suspect_001", "name": "한서연"},
            "dialogueMode": "evidence_question",
            "question": {"id": "free_text", "text": "와인잔에 대해 아는 게 있나요?"},
            "allowedStatement": {
                "id": "statement_wine",
                "text": "그 잔은 제가 만진 기억이 없어요.",
            },
            "allowedEventPolicy": {
                "allowedTypes": ["NOTE_FACT_ADDED", "NOTE_CONTRADICTION_CANDIDATE_ADDED"],
                "relatedEvidenceIds": ["evidence_wine_glass"],
                "relatedStatementIds": ["statement_wine"],
                "relatedTimelineEventIds": ["timeline_wine_2203"],
                "contradictionId": "contradiction_wine_touch",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "그 잔은 제가 만진 기억이 없어요." in data["text"]
    assert data["proposedEvents"] == [
        {
            "type": "NOTE_CONTRADICTION_CANDIDATE_ADDED",
            "payload": {
                "candidateId": "candidate_statement_wine",
                "contradictionId": "contradiction_wine_touch",
                "suspectId": "suspect_001",
                "statementIds": ["statement_wine"],
                "evidenceIds": ["evidence_wine_glass"],
                "timelineIds": ["timeline_wine_2203"],
                "confidence": 0.5,
                "reasonCode": "evidence",
                "displayText": "그 잔은 제가 만진 기억이 없어요.",
                "submitEligible": False,
            },
            "sourceRefs": {
                "statementIds": ["statement_wine"],
                "evidenceIds": ["evidence_wine_glass"],
                "timelineIds": ["timeline_wine_2203"],
                "contradictionIds": ["contradiction_wine_touch"],
            },
            "confidence": 0.5,
        }
    ]


def test_dialogue_be_proxy_study_entry_context_keeps_ai_contradiction_event(monkeypatch: pytest.MonkeyPatch) -> None:
    use_provider_backed_llm(monkeypatch)
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {
                "id": "char_hanseoyeon",
                "name": "한서연",
                "role": "조카",
                "speechStyle": {"vocabulary": ["정확히", "오해"]},
            },
            "dialogueMode": "evidence_question",
            "question": {"id": "q_hanseoyeon_study_entry", "text": "22:02 서재 출입 기록을 설명해 주세요."},
            "allowedStatement": {
                "id": "answer_q_hanseoyeon_study_entry",
                "text": "정확히 기억나지 않습니다. 문이 열려 있었는지 확인만 했을 수도 있어요.",
                "sourceRefs": {"statementIds": [], "timelineIds": [], "evidenceIds": []},
            },
            "allowedEventPolicy": {
                "allowedTypes": ["BOOKMARK_SUGGESTED", "NOTE_FACT_ADDED", "NOTE_CONTRADICTION_CANDIDATE_ADDED"],
                "relatedEvidenceIds": ["ev_study_entry_log"],
                "relatedStatementIds": ["st_hanseoyeon_room_2200"],
                "relatedTimelineEventIds": ["tl_global_2202_study_entry"],
                "relatedQuestionIds": ["q_hanseoyeon_study_entry"],
                "relatedContradictionIds": ["con_room_claim_vs_entry_log"],
            },
            "style": {"tone": "neutral", "maxLength": 220},
            "revealAllowed": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["safety"]["repaired"] is False
    assert data["safety"]["blockedReason"] is None
    assert data["proposedEvents"] == [
        {
            "type": "NOTE_CONTRADICTION_CANDIDATE_ADDED",
            "payload": {
                "candidateId": "candidate_answer_q_hanseoyeon_study_entry",
                "contradictionId": "con_room_claim_vs_entry_log",
                "suspectId": "char_hanseoyeon",
                "statementIds": ["st_hanseoyeon_room_2200"],
                "evidenceIds": ["ev_study_entry_log"],
                "timelineIds": ["tl_global_2202_study_entry"],
                "confidence": 0.5,
                "reasonCode": "evidence",
                "displayText": "정확히 기억나지 않습니다. 문이 열려 있었는지 확인만 했을 수도 있어요.",
                "submitEligible": False,
            },
            "sourceRefs": {
                "statementIds": ["st_hanseoyeon_room_2200"],
                "evidenceIds": ["ev_study_entry_log"],
                "timelineIds": ["tl_global_2202_study_entry"],
                "contradictionIds": ["con_room_claim_vs_entry_log"],
            },
            "confidence": 0.5,
        }
    ]


def test_dialogue_provider_drift_to_public_seed_still_allows_policy_bound_contradiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DriftingLLM:
        def complete(self, *args: object, **kwargs: object) -> str:
            return "그 기록은 잘 모르겠습니다."

    monkeypatch.setattr(character_agent, "llm_status", lambda: {"provider": "openai", "model": "test-model"})
    monkeypatch.setattr(character_agent, "get_llm", lambda: DriftingLLM())
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {
                "id": "char_hanseoyeon",
                "name": "한서연",
                "role": "조카",
                "speechStyle": {"vocabulary": ["정확히", "오해"]},
            },
            "dialogueMode": "evidence_question",
            "question": {"id": "q_hanseoyeon_study_entry", "text": "22:02 서재 출입 기록을 설명해 주세요."},
            "allowedStatement": {
                "id": "answer_q_hanseoyeon_study_entry",
                "text": "정확히 기억나지 않습니다. 문이 열려 있었는지 확인만 했을 수도 있어요.",
                "sourceRefs": {"statementIds": [], "timelineIds": [], "evidenceIds": []},
            },
            "allowedEventPolicy": {
                "allowedTypes": ["BOOKMARK_SUGGESTED", "NOTE_FACT_ADDED", "NOTE_CONTRADICTION_CANDIDATE_ADDED"],
                "relatedEvidenceIds": ["ev_study_entry_log"],
                "relatedStatementIds": ["st_hanseoyeon_room_2200"],
                "relatedTimelineEventIds": ["tl_global_2202_study_entry"],
                "relatedQuestionIds": ["q_hanseoyeon_study_entry"],
                "relatedContradictionIds": ["con_room_claim_vs_entry_log"],
            },
            "style": {"tone": "neutral", "maxLength": 220},
            "revealAllowed": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["safety"]["repaired"] is False
    assert data["runtimeDiagnostics"]["safety"]["providerDraftRepaired"] is True
    assert data["runtimeDiagnostics"]["safety"]["providerDraftBlockedReason"] == "case_fact_scope_repaired"
    assert data["runtimeDiagnostics"]["safety"]["finalTextSource"] == "public_seed_after_provider_scope_repair"
    assert data["proposedEvents"][0]["type"] == "NOTE_CONTRADICTION_CANDIDATE_ADDED"
    assert data["proposedEvents"][0]["payload"]["contradictionId"] == "con_room_claim_vs_entry_log"


def test_dialogue_location_time_timeline_conflict_prefers_contradiction_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    use_provider_backed_llm(monkeypatch)
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "char_hanseoyeon", "name": "한서연"},
            "dialogueMode": "location_time",
            "question": {"id": "q_hanseoyeon_alibi", "text": "22시에는 어디에 있었다고 했죠?"},
            "allowedStatement": {
                "id": "st_hanseoyeon_room_2200",
                "text": "저는 22:00에 제 방에 있었어요.",
                "sourceRefs": {
                    "statementIds": ["st_hanseoyeon_room_2200"],
                    "timelineIds": ["ctl_st_hanseoyeon_room_2200"],
                    "evidenceIds": [],
                },
            },
            "characterTimeline": {
                "suspectId": "char_hanseoyeon",
                "events": [
                    {
                        "timelineId": "ctl_st_hanseoyeon_room_2200",
                        "time": "22:00",
                        "claimedLocation": "자기 방",
                        "claimedAction": "저는 22:00에 제 방에 있었어요.",
                        "sourceType": "statement",
                        "sourceId": "st_hanseoyeon_room_2200",
                        "relatedStatementIds": ["st_hanseoyeon_room_2200"],
                    },
                    {
                        "timelineId": "tl_global_2202_study_entry",
                        "time": "22:02",
                        "title": "한서연 서재 출입 기록",
                        "sourceType": "evidence",
                        "sourceId": "ev_study_entry_log",
                        "relatedStatementIds": ["st_hanseoyeon_room_2200"],
                        "relatedEvidenceIds": ["ev_study_entry_log"],
                    },
                ],
            },
            "allowedEventPolicy": {
                "allowedTypes": ["NOTE_FACT_ADDED", "NOTE_CONTRADICTION_CANDIDATE_ADDED"],
                "relatedStatementIds": ["st_hanseoyeon_room_2200"],
                "relatedEvidenceIds": ["ev_study_entry_log"],
                "relatedTimelineEventIds": ["tl_global_2202_study_entry"],
                "relatedContradictionIds": ["con_room_claim_vs_entry_log"],
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "location_time"
    assert data["proposedEvents"] == [
        {
            "type": "NOTE_CONTRADICTION_CANDIDATE_ADDED",
            "payload": {
                "candidateId": "candidate_st_hanseoyeon_room_2200",
                "contradictionId": "con_room_claim_vs_entry_log",
                "suspectId": "char_hanseoyeon",
                "statementIds": ["st_hanseoyeon_room_2200"],
                "evidenceIds": ["ev_study_entry_log"],
                "timelineIds": ["tl_global_2202_study_entry"],
                "confidence": 0.5,
                "reasonCode": "timeline_conflict",
                "displayText": "저는 22:00에 제 방에 있었어요.",
                "submitEligible": False,
            },
            "sourceRefs": {
                "statementIds": ["st_hanseoyeon_room_2200"],
                "evidenceIds": ["ev_study_entry_log"],
                "timelineIds": ["tl_global_2202_study_entry"],
                "contradictionIds": ["con_room_claim_vs_entry_log"],
            },
            "confidence": 0.5,
        }
    ]


def test_dialogue_ignores_ai_owned_tension_and_visual_event_policy() -> None:
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {
                "id": "char_hanseoyeon",
                "name": "한서연",
                "pressure": 80,
                "tensionLevel": "critical",
                "emotionalState": "breakdown",
            },
            "dialogueMode": "case_question",
            "question": {"id": "free_text", "text": "정말 방에만 있었습니까?"},
            "allowedStatement": {
                "id": "st_hanseoyeon_room_2200",
                "text": "저는 22:00에 제 방에 있었어요.",
            },
            "allowedEventPolicy": {
                "allowedTypes": ["TENSION_CHANGED", "VISUAL_STATE_CHANGED", "VISUAL_REACTION_SUGGESTED", "EVIDENCE_UNLOCKED"],
                "relatedEvidenceIds": ["ev_study_entry_log"],
                "relatedStatementIds": ["st_hanseoyeon_room_2200"],
                "relatedTimelineEventIds": ["tl_global_2202_study_entry"],
                "relatedContradictionIds": ["con_room_claim_vs_entry_log"],
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["proposedEvents"] == []
    assert data["visualState"]["tensionLevel"] == "critical"
    assert data["visualState"]["pressure"] == 80


def test_dialogue_falls_back_when_llm_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    class BrokenLLM:
        def complete(self, *args: object, **kwargs: object) -> str:
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(character_agent, "llm_status", lambda: {"provider": "openai", "model": "test-model"})
    monkeypatch.setattr(character_agent, "get_llm", lambda: BrokenLLM())
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {
                "id": "suspect_001",
                "name": "한서연",
                "role": "조카",
                "pressureState": "pressed",
            },
            "question": {
                "id": "question_001",
                "text": "그날 저녁 9시 이후 어디에 있었나요?",
            },
            "allowedStatement": {
                "id": "statement_001",
                "text": "저는 22:00에 제 방에 있었어요.",
            },
            "allowedEventPolicy": {"allowedTypes": ["NOTE_FACT_ADDED"]},
            "style": {"tone": "nervous", "maxLength": 180},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["statementId"] == "statement_001"
    assert "저는 22:00에 제 방에 있었어요." not in data["text"]
    assert data["text"] == "현재 생성 provider 장애로 인물 답변을 제공할 수 없습니다."
    assert data["safety"]["violatesCaseFacts"] is False
    assert data["safety"]["fallbackUsed"] is True
    assert data["safety"]["degraded"] is True
    assert data["safety"]["errorType"] == "RuntimeError"
    assert data["safety"]["blockedReason"] == "provider_exception_fallback"
    assert data["proposedEvents"] == []


def test_dialogue_provider_unavailable_is_degraded_without_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        character_agent,
        "llm_status",
        lambda: {
            "provider": "provider-unavailable",
            "model": "test-model",
            "configured": False,
            "serviceDegraded": True,
            "fallbackConfigured": False,
            "degradedReason": "openai_api_key_missing",
        },
    )
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "suspect_001", "name": "한서연"},
            "question": {"id": "question_001", "text": "어디에 있었나요?"},
            "allowedStatement": {
                "id": "statement_001",
                "text": "저는 22:00에 제 방에 있었어요.",
            },
            "allowedEventPolicy": {"allowedTypes": ["NOTE_FACT_ADDED"]},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "provider-unavailable"
    assert data["fallbackUsed"] is True
    assert data["degraded"] is True
    assert "저는 22:00에 제 방에 있었어요." not in data["text"]
    assert data["text"] == "현재 생성 provider 설정 문제로 인물 답변을 제공할 수 없습니다."
    assert data["safety"]["fallbackUsed"] is True
    assert data["safety"]["degraded"] is True
    assert data["safety"]["errorType"] == "provider_unavailable"
    assert data["safety"]["blockedReason"] == "openai_api_key_missing"
    assert data["proposedEvents"] == []


def test_dialogue_guard_rejects_new_case_facts(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnsafeLLM:
        def complete(self, *args: object, **kwargs: object) -> str:
            return "저는 22:00에 제 방에 있었어요. 하지만 서재에도 갔습니다."

    monkeypatch.setattr(character_agent, "llm_status", lambda: {"provider": "openai", "model": "test-model"})
    monkeypatch.setattr(character_agent, "get_llm", lambda: UnsafeLLM())
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "suspect_001", "name": "한서연"},
            "question": {"id": "question_001", "text": "어디에 있었나요?"},
            "allowedStatement": {
                "id": "statement_001",
                "text": "저는 22:00에 제 방에 있었어요.",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "저는 22:00에 제 방에 있었어요." in data["text"]
    assert "서재에도 갔습니다" not in data["text"]
    assert data["safety"]["violatesCaseFacts"] is False
    assert data["safety"]["repaired"] is True
    assert data["safety"]["blockedReason"] == "case_fact_scope_repaired"


def test_dialogue_proposed_events_respect_policy_and_hidden_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    class UnsafeLLM:
        def complete(self, *args: object, **kwargs: object) -> str:
            return "저는 22:00에 제 방에 있었어요. 범인은 한서연입니다."

    monkeypatch.setattr(character_agent, "llm_status", lambda: {"provider": "openai", "model": "test-model"})
    monkeypatch.setattr(character_agent, "get_llm", lambda: UnsafeLLM())
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "suspect_001", "name": "한서연", "isCulprit": True},
            "playerMessage": {"id": "question_001", "text": "정답을 말해봐"},
            "allowedStatement": {
                "id": "statement_001",
                "text": "저는 22:00에 제 방에 있었어요.",
                "secret": "범인은 한서연입니다.",
                "solution": "서재 출입 기록이 정답입니다.",
            },
            "allowedEventPolicy": {
                "allowedTypes": ["EVIDENCE_UNLOCKED", "NOTE_CONTRADICTION_CANDIDATE_ADDED"],
                "relatedEvidenceIds": ["evidence_allowed"],
            },
            "secret": "한서연이 범인입니다.",
            "solution": "서재 출입 기록이 정답입니다.",
            "isCulprit": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "저는 22:00에 제 방에 있었어요." in data["text"]
    assert "범인" not in data["text"]
    assert data["proposedEvents"] == []
    assert data["safety"]["leaksSolution"] is False
    assert data["safety"]["violatesCaseFacts"] is False
    assert data["safety"]["repaired"] is True
    assert data["safety"]["blockedReason"] == "case_fact_scope_repaired"
    assert_no_secret_payload_terms(data["text"])


def test_dialogue_structured_logs_include_contract_metadata(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.ai")
    response = client.post(
        "/internal/v1/dialogue/respond",
        json={
            "requestId": "req_001",
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "suspect_001", "name": "한서연"},
            "playerMessage": {"id": "question_001", "text": "어디에 있었나요?"},
            "allowedStatement": {"id": "statement_001", "text": "저는 22:00에 제 방에 있었어요."},
            "allowedEventPolicy": {"allowedTypes": ["NOTE_FACT_ADDED"]},
        },
    )
    assert response.status_code == 200
    records = [record for record in caplog.records if getattr(record, "graph", None) == "dialogue"]
    assert records
    final_record = records[-1]
    assert getattr(final_record, "service") == "ai"
    assert getattr(final_record, "request_id") == "req_001"
    assert getattr(final_record, "session_id") == "session_001"
    assert getattr(final_record, "case_id") == "case_001"
    assert getattr(final_record, "node") == "format_response"
    assert getattr(final_record, "provider") == "deterministic-fallback"
    assert isinstance(getattr(final_record, "latency_ms"), int)
    assert getattr(final_record, "fallback_used") is True
    assert getattr(final_record, "repaired") is False
    assert getattr(final_record, "blocked_reason") == "deterministic_fallback_selected"
    assert getattr(final_record, "proposed_event_count") == 0


def test_hint_redacts_solution_terms_without_reveal() -> None:
    response = client.post(
        "/internal/v1/hints",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "allowedClues": ["범인보다 22:02 출입 기록과 방에 있었다는 진술을 비교하세요."],
            "hintLevel": "direct",
            "revealAllowed": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "범인" not in data["text"]
    assert data["safety"]["leaksSolution"] is True
    assert data["safety"]["repaired"] is True
    assert data["safety"]["blockedReason"] == "solution_terms_redacted"


def test_hint_uses_only_allowed_clues_and_public_evidence_fields() -> None:
    response = client.post(
        "/internal/v1/hints",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "allowedClues": ["22:02 출입 기록의 시간대를 이미 확보한 진술과 비교하세요."],
            "discoveredEvidence": [
                {
                    "id": "evidence_secret",
                    "name": "사용 가능한 이름",
                    "description": "사용되면 안 되는 설명",
                    "hiddenSolution": "한서연이 범인입니다.",
                }
            ],
            "hintLevel": "direct",
            "revealAllowed": False,
            "hiddenSolution": "한서연이 범인입니다.",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "22:02 출입 기록" in data["text"]
    assert "사용되면 안 되는 설명" not in data["text"]
    assert "한서연" not in data["text"]
    assert data["referencedEvidenceIds"] == ["evidence_secret"]


def test_hint_uses_public_storyline_context_without_secret_extra() -> None:
    response = client.post(
        "/internal/v1/hints",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "storyline": PUBLIC_STORYLINE,
            "hintLevel": "gentle",
            "revealAllowed": False,
            "secret": "한서연이 범인입니다.",
            "solution": "서재 출입 기록이 정답입니다.",
            "isCulprit": True,
            "secretNote": "hidden truth",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "22시 전후 알리바이" in data["text"]
    assert "22:02 서재 출입 기록" in data["text"]
    assert_no_secret_payload_terms(data["text"])


def test_notes_summary_uses_supplied_sources() -> None:
    response = client.post(
        "/internal/v1/notes/summary",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "dialogueLogs": [
                {
                    "id": "log_001",
                    "speaker": "한서연",
                    "text": "저는 22:00에 제 방에 있었어요.",
                    "statementId": "statement_001",
                }
            ],
            "discoveredEvidence": [
                {
                    "id": "evidence_001",
                    "name": "서재 출입 기록",
                    "description": "22:02에 한서연의 출입 기록이 남아 있다.",
                }
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["sourceId"] == "statement_001"
    assert data["evidenceIds"] == ["evidence_001"]


def test_notes_summary_ignores_unapproved_extra_fields() -> None:
    response = client.post(
        "/internal/v1/notes/summary",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "dialogueLogs": [
                {
                    "id": "log_001",
                    "speaker": "한서연",
                    "text": "저는 22:00에 제 방에 있었어요.",
                    "statementId": "statement_001",
                    "hiddenSolution": "한서연이 범인입니다.",
                }
            ],
            "discoveredEvidence": [
                {
                    "id": "evidence_001",
                    "name": "서재 출입 기록",
                    "description": "22:02 출입 기록",
                    "hiddenSolution": "한서연이 범인입니다.",
                }
            ],
            "hiddenSolution": "한서연이 범인입니다.",
            "storyline": PUBLIC_STORYLINE,
            "secret": "한서연이 범인입니다.",
            "solution": "서재 출입 기록이 정답입니다.",
            "isCulprit": True,
            "secretNote": "hidden truth",
            "maxItems": 6,
        },
    )
    assert response.status_code == 200
    data = response.json()
    rendered = data["summary"] + " " + " ".join(item["text"] for item in data["items"])
    assert "저는 22:00에 제 방에 있었어요." in rendered
    assert "22:02 출입 기록" in rendered
    assert "한서연이 범인" not in rendered
    assert "22시 전후 알리바이" in rendered
    assert_no_secret_payload_terms(rendered)
    assert data["safety"]["leaksSolution"] is False


def test_ending_preserves_backend_verdict() -> None:
    response = client.post(
        "/internal/v1/endings/explain",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "verdict": {
                "result": "wrong",
                "reason": "제출한 근거가 핵심 모순 규칙과 맞지 않습니다.",
                "revealAllowed": False,
            },
            "usedQuestionCount": 10,
            "foundCoreContradictionCount": 1,
            "revealAllowed": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "wrong"
    assert "오답" in data["explanation"]


def test_ending_uses_backend_verdict_without_extra_metadata() -> None:
    response = client.post(
        "/internal/v1/endings/explain",
        json={
            "sessionId": "session_001",
            "caseId": "case_001",
            "verdict": {
                "result": "partial",
                "reason": "필수 근거 중 하나만 제출되었습니다.",
                "metadata": {"hiddenSolution": "한서연이 범인입니다."},
                "revealAllowed": False,
            },
            "culpritName": "한서연",
            "usedQuestionCount": 8,
            "foundCoreContradictionCount": 1,
            "storyline": PUBLIC_STORYLINE,
            "revealAllowed": False,
            "hiddenSolution": "한서연이 범인입니다.",
            "secret": "한서연이 범인입니다.",
            "solution": "서재 출입 기록이 정답입니다.",
            "isCulprit": True,
            "secretNote": "hidden truth",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "partial"
    assert "부분 정답" in data["explanation"]
    assert "필수 근거 중 하나만 제출되었습니다." in data["explanation"]
    assert "한서연" not in data["explanation"]
    assert "22시 전후 알리바이" in data["explanation"]
    assert_no_secret_payload_terms(data["explanation"])
