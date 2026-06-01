from __future__ import annotations

from types import SimpleNamespace

from app.ai_engine.application.character_agent import render_dialogue_seed
from app.ai_engine.application.light_rule_check import _quality_issues
from app.ai_engine.application.knowledge_retriever import KnowledgeRetriever
from app.ai_engine.domain.proposed_events import propose_dialogue_events
from app.ai_engine.schemas.agents import DraftCharacterReply, LightRuleCheckInput
from app.ai_engine.schemas.dialogue import DialogueRequest


class FakeGraph:
    available = True

    def run(self, query: str, **_: object) -> list[dict]:
        if "MADE_STATEMENT" in query:
            return [
                {
                    "statementId": "st_alibi",
                    "statementText": "저는 22:00에 제 방에 있었어요.",
                    "timeWindow": "22:00",
                    "location": "방",
                    "contradictions": [
                        {
                            "contradictionId": "con_alibi_vs_entry",
                            "title": "알리바이와 출입 기록 충돌",
                            "severity": "high",
                        }
                    ],
                    "evidenceConflicts": [{"evidenceId": "ev_entry", "name": "출입 기록"}],
                }
            ]
        if "MATCH (t:TimelineEvent" in query:
            return [
                {
                    "timelineId": "tl_2200",
                    "time": "22:00",
                    "title": "공개된 22시 행적",
                    "description": "공개 타임라인 항목",
                }
            ]
        return []


def test_retriever_splits_character_and_game_master_context() -> None:
    context = KnowledgeRetriever(FakeGraph()).retrieve_dialogue_context(
        case_id="case_001",
        suspect_id="char_hanseoyeon",
        question_text="22시에 어디 있었나요?",
        allowed_statement_text="저는 22:00에 제 방에 있었어요.",
        unlocked_statement_ids=["st_alibi"],
        unlocked_evidence_ids=["ev_entry"],
        discovered_contradiction_ids=[],
    )

    assert context.character_context.matched_statements[0]["id"] == "st_alibi"
    assert context.character_context.matched_timeline_events[0]["id"] == "tl_2200"
    assert not hasattr(context.character_context, "related_contradictions")
    assert context.event_context.matched_statement_ids == ["st_alibi"]
    assert context.event_context.matched_timeline_ids == ["tl_2200"]
    assert context.event_context.candidate_contradiction_ids == ["con_alibi_vs_entry"]


def test_game_master_event_context_is_used_only_for_event_refs() -> None:
    payload = DialogueRequest.model_validate(
        {
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "char_hanseoyeon", "name": "한서연"},
            "dialogueMode": "evidence_question",
            "question": {"id": "q_entry", "text": "출입 기록 증거를 보면 이상하지 않나요?"},
            "allowedStatement": {"id": "st_alibi", "text": "저는 22:00에 제 방에 있었어요."},
            "allowedEventPolicy": {"allowedTypes": ["NOTE_CONTRADICTION_CANDIDATE_ADDED"]},
        }
    )
    event_context = SimpleNamespace(
        matched_statement_ids=["st_alibi"],
        matched_evidence_ids=["ev_entry"],
        matched_timeline_ids=["tl_2200"],
        candidate_contradiction_ids=["con_alibi_vs_entry"],
    )

    events = propose_dialogue_events(payload, event_context=event_context)

    assert [event.type for event in events] == ["NOTE_CONTRADICTION_CANDIDATE_ADDED"]
    assert events[0].payload["contradictionId"] == "con_alibi_vs_entry"
    assert events[0].sourceRefs["statementIds"] == ["st_alibi"]
    assert events[0].sourceRefs["evidenceIds"] == ["ev_entry"]


def test_location_time_seed_uses_spoken_dialogue_tone() -> None:
    payload = DialogueRequest.model_validate(
        {
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "char_hanseoyeon", "name": "한서연", "role": "조카"},
            "dialogueMode": "timeline_question",
            "question": {"id": "q_time", "text": "22시에 어디 있었나요?"},
            "allowedStatement": {"id": "st_alibi", "text": "저는 22:00에 제 방에 있었어요."},
        }
    )

    seed = render_dialogue_seed(payload)

    assert "22시요?" in seed
    assert "저는 22:00에 제 방에 있었어요." in seed
    assert "시간대를 묻는 거라면" not in seed
    assert "제 기억은 이렇게 정리됩니다" not in seed


def test_stiff_summary_tone_triggers_regeneration_quality_issue() -> None:
    payload = DialogueRequest.model_validate(
        {
            "sessionId": "session_001",
            "caseId": "case_001",
            "suspect": {"id": "char_hanseoyeon", "name": "한서연"},
            "dialogueMode": "timeline_question",
            "question": {"id": "q_time", "text": "22시에 어디 있었나요?"},
            "allowedStatement": {"id": "st_alibi", "text": "저는 22:00에 제 방에 있었어요."},
        }
    )
    draft = DraftCharacterReply(
        suspectId="char_hanseoyeon",
        draftText="시간대를 묻는 거라면, 제 기억은 이렇게 정리됩니다. 저는 22:00에 제 방에 있었어요. 그 이상은 추측하고 싶지 않습니다.",
        provider="test",
        model="test",
    )
    check_input = LightRuleCheckInput(
        draft=draft,
        allowedStatement=payload.allowedStatement,
        intent="location_time",
    )

    issues = _quality_issues(draft.draftText, payload.allowedStatement.text, check_input)

    assert "stiff_summary_tone" in issues
