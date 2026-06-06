from time import perf_counter

from fastapi.testclient import TestClient

from app.ai_engine.core.observability import AiLogContext, emit_ai_node_log
from app.ai_engine.core.trace_store import agent_trace_store
from app.core.config import get_settings
from app.main import app


def _client(monkeypatch, *, enabled: bool) -> TestClient:
    monkeypatch.setenv("BE_DEBUG_TOOLS_ENABLED", "true" if enabled else "false")
    get_settings.cache_clear()
    return TestClient(app)


def test_agent_logger_requires_debug_tools(monkeypatch) -> None:
    agent_trace_store.clear()
    response = _client(monkeypatch, enabled=False).get("/api/v1/agent-logs")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "AGENT_LOGGER_DISABLED"


def test_agent_logger_groups_public_safe_node_metadata(monkeypatch) -> None:
    agent_trace_store.clear()
    context = AiLogContext(
        request_id="req_logger_test",
        session_id="session_logger_test",
        case_id="case_001",
        graph="dialogue",
        suspect_id="char_hanseoyeon",
        suspect_name="한서연",
        dialogue_mode="timeline_question",
        question_preview="22시에는 어디에 있었나요?",
    )
    emit_ai_node_log(context, node="CharacterAgent", started_at=perf_counter(), provider="upstage", model="solar-pro")
    emit_ai_node_log(
        context,
        node="LightRuleCheck",
        started_at=perf_counter(),
        provider="upstage",
        model="solar-pro",
        repaired=True,
        blocked_reason="case_fact_scope_repaired",
    )
    emit_ai_node_log(context, node="format_response", started_at=perf_counter(), provider="upstage", model="solar-pro")

    response = _client(monkeypatch, enabled=True).get(
        "/api/v1/agent-logs",
        params={"sessionId": "session_logger_test"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["enabled"] is True
    assert len(payload["traces"]) == 1
    trace = payload["traces"][0]
    assert trace["traceId"] == "req_logger_test"
    assert trace["status"] == "repaired"
    assert trace["suspectName"] == "한서연"
    assert trace["dialogueMode"] == "timeline_question"
    assert trace["questionPreview"] == "22시에는 어디에 있었나요?"
    assert [event["node"] for event in trace["events"]] == ["CharacterAgent", "LightRuleCheck", "format_response"]
    assert trace["events"][0]["activity"] == "캐릭터 대사 초안 생성"
    assert "prompt" not in str(payload).lower()
    assert "answer" not in str(payload).lower()

    cleared = _client(monkeypatch, enabled=True).delete("/api/v1/agent-logs")
    assert cleared.json()["cleared"] == 3
