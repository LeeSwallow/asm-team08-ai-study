from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.ai_engine.core.llm import llm_status
from app.ai_engine.core.trace_store import agent_trace_store

AI_LOGGER_NAME = "app.ai"
logger = logging.getLogger(AI_LOGGER_NAME)


@dataclass(frozen=True)
class AiLogContext:
    request_id: str | None
    session_id: str
    case_id: str
    graph: str
    suspect_id: str | None = None
    suspect_name: str | None = None
    dialogue_mode: str | None = None
    question_preview: str | None = None


def now_ms() -> float:
    return perf_counter()


def emit_ai_node_log(
    context: AiLogContext,
    *,
    node: str,
    started_at: float,
    provider: str | None = None,
    model: str | None = None,
    fallback_used: bool = False,
    repaired: bool = False,
    blocked_reason: str | None = None,
    proposed_event_count: int = 0,
    level: int = logging.INFO,
) -> None:
    status = llm_status()
    latency_ms = int((perf_counter() - started_at) * 1000)
    resolved_provider = provider or str(status["provider"])
    resolved_model = model or str(status["model"])
    logger.log(
        level,
        "ai graph node completed",
        extra={
            "service": "ai",
            "request_id": context.request_id,
            "session_id": context.session_id,
            "case_id": context.case_id,
            "graph": context.graph,
            "node": node,
            "provider": resolved_provider,
            "model": resolved_model,
            "latency_ms": latency_ms,
            "fallback_used": fallback_used,
            "repaired": repaired,
            "blocked_reason": blocked_reason,
            "proposed_event_count": proposed_event_count,
        },
    )
    agent_trace_store.record(
        request_id=context.request_id,
        session_id=context.session_id,
        case_id=context.case_id,
        graph=context.graph,
        suspect_id=context.suspect_id,
        suspect_name=context.suspect_name,
        dialogue_mode=context.dialogue_mode,
        question_preview=context.question_preview,
        node=node,
        provider=resolved_provider,
        model=resolved_model,
        latency_ms=latency_ms,
        fallback_used=fallback_used,
        repaired=repaired,
        reason=blocked_reason,
        proposed_event_count=proposed_event_count,
        level=level,
    )
