from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from app.core.leak_guard import forbidden_ref_hits


_NODE_ACTIVITIES = {
    "load_context": "공개 사건 컨텍스트 로드",
    "validate_scope": "허용 진술과 공개 범위 확인",
    "KnowledgeRetriever": "공개 지식 컨텍스트 조회",
    "DialogueDirectorAgent": "응답 전략과 허용 수준 결정",
    "CharacterAgent": "캐릭터 대사 초안 생성",
    "DialogueTonePolisher": "캐릭터 말투 자연화",
    "LightRuleCheck": "비밀 유출과 사실 범위 검증",
    "GroundingCheckAgent": "허용 진술 기반 응답 검증",
    "GameMasterAgent": "공개 게임 이벤트 제안",
    "format_response": "공개 응답 계약 구성",
}
_TRACE_COMPLETE_NODE = "format_response"
_MAX_TEXT_LENGTH = 120


def _safe_text(value: str | None) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).split())[:_MAX_TEXT_LENGTH]
    return "redacted" if forbidden_ref_hits(text) else text


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentTraceStore:
    """Bounded in-memory store for public-safe Agent execution metadata."""

    def __init__(self, capacity: int = 500) -> None:
        self.capacity = capacity
        self._events: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._lock = Lock()
        self._sequence = 0

    def record(
        self,
        *,
        request_id: str | None,
        session_id: str,
        case_id: str,
        graph: str,
        suspect_id: str | None,
        suspect_name: str | None,
        dialogue_mode: str | None,
        question_preview: str | None,
        node: str,
        provider: str | None,
        model: str | None,
        latency_ms: int,
        fallback_used: bool,
        repaired: bool,
        reason: str | None,
        proposed_event_count: int,
        level: int,
    ) -> None:
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            trace_id = _safe_text(request_id) or f"trace_{_safe_text(session_id) or 'unknown'}_{sequence}"
            event = {
                "sequence": sequence,
                "recordedAt": _utc_now(),
                "traceId": trace_id,
                "requestId": _safe_text(request_id),
                "sessionId": _safe_text(session_id),
                "caseId": _safe_text(case_id),
                "graph": _safe_text(graph),
                "suspectId": _safe_text(suspect_id),
                "suspectName": _safe_text(suspect_name),
                "dialogueMode": _safe_text(dialogue_mode),
                "questionPreview": _safe_text(question_preview),
                "node": _safe_text(node),
                "activity": _NODE_ACTIVITIES.get(node, "Agent 노드 작업 완료"),
                "provider": _safe_text(provider),
                "model": _safe_text(model),
                "latencyMs": max(0, int(latency_ms)),
                "fallbackUsed": bool(fallback_used),
                "repaired": bool(repaired),
                "reason": _safe_text(reason),
                "proposedEventCount": max(0, int(proposed_event_count)),
                "level": "warning" if level >= 30 else "info",
            }
            self._events.append(event)

    def clear(self) -> int:
        with self._lock:
            removed = len(self._events)
            self._events.clear()
            return removed

    def list_traces(
        self,
        *,
        session_id: str | None = None,
        case_id: str | None = None,
        graph: str | None = None,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._events)

        filtered = [
            event
            for event in events
            if (not session_id or event["sessionId"] == session_id)
            and (not case_id or event["caseId"] == case_id)
            and (not graph or event["graph"] == graph)
        ]
        grouped: dict[str, list[dict[str, Any]]] = {}
        for event in filtered:
            grouped.setdefault(str(event["traceId"]), []).append(event)

        traces = [self._build_trace(trace_id, items) for trace_id, items in grouped.items()]
        traces.sort(key=lambda item: item["lastSequence"], reverse=True)
        return traces[:limit]

    def _build_trace(self, trace_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
        ordered = sorted(events, key=lambda item: item["sequence"])
        latest = ordered[-1]
        complete = any(item["node"] == _TRACE_COMPLETE_NODE for item in ordered)
        has_fallback = any(item["fallbackUsed"] for item in ordered)
        has_warning = any(item["level"] == "warning" for item in ordered)
        has_repair = any(item["repaired"] for item in ordered)
        status = "running"
        if complete:
            status = "fallback" if has_fallback else "warning" if has_warning else "repaired" if has_repair else "completed"
        return {
            "traceId": trace_id,
            "requestId": latest["requestId"],
            "sessionId": latest["sessionId"],
            "caseId": latest["caseId"],
            "graph": latest["graph"],
            "suspectId": latest["suspectId"],
            "suspectName": latest["suspectName"],
            "dialogueMode": latest["dialogueMode"],
            "questionPreview": latest["questionPreview"],
            "startedAt": ordered[0]["recordedAt"],
            "completedAt": latest["recordedAt"] if complete else None,
            "lastSequence": latest["sequence"],
            "status": status,
            "nodeCount": len(ordered),
            "totalLatencyMs": sum(item["latencyMs"] for item in ordered),
            "provider": next((item["provider"] for item in reversed(ordered) if item["provider"]), None),
            "model": next((item["model"] for item in reversed(ordered) if item["model"]), None),
            "fallbackUsed": has_fallback,
            "repaired": has_repair,
            "events": ordered,
        }


agent_trace_store = AgentTraceStore()
