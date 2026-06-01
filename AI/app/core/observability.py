from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.core.llm import llm_status

AI_LOGGER_NAME = "app.ai"
logger = logging.getLogger(AI_LOGGER_NAME)


@dataclass(frozen=True)
class AiLogContext:
    request_id: str | None
    session_id: str
    case_id: str
    graph: str


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
            "provider": provider or status["provider"],
            "model": model or status["model"],
            "latency_ms": int((perf_counter() - started_at) * 1000),
            "fallback_used": fallback_used,
            "repaired": repaired,
            "blocked_reason": blocked_reason,
            "proposed_event_count": proposed_event_count,
        },
    )
