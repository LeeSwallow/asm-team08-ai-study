from __future__ import annotations

from typing import Any

from app.ai_engine.core.solution_guard import redact_solution_terms
from app.ai_engine.prompts.hint import HINT_SYSTEM_PROMPT
from app.ai_engine.schemas.safety import Safety
from app.ai_engine.schemas.hints import HintRequest, HintResponse

from .common import run_langgraph_or_pipeline


def inspect_progress(state: dict[str, Any]) -> dict[str, Any]:
    payload: HintRequest = state["payload"]
    evidence_ids = [item.id for item in payload.discoveredEvidence]
    return {"evidence_ids": evidence_ids, "prompt": HINT_SYSTEM_PROMPT}


def select_hint_level(state: dict[str, Any]) -> dict[str, Any]:
    payload: HintRequest = state["payload"]
    return {"level": payload.hintLevel}


def generate_hint(state: dict[str, Any]) -> dict[str, Any]:
    payload: HintRequest = state["payload"]
    if payload.allowedClues:
        clue = payload.allowedClues[0].strip()
    elif payload.storyline and (payload.storyline.currentObjective or payload.storyline.visibleTimeline):
        objective = payload.storyline.currentObjective or payload.storyline.openingObjective or "현재 목표"
        public_timeline = [event for event in payload.storyline.visibleTimeline if not getattr(event, "hidden", False)]
        timeline = public_timeline[0] if public_timeline else None
        if timeline:
            time_label = f"{timeline.time} " if timeline.time else ""
            clue = f"현재 목표 '{objective}'를 기준으로 {time_label}{timeline.title} 항목과 확보한 진술을 비교해 보세요."
        else:
            clue = f"현재 목표 '{objective}'에 맞춰 아직 확인하지 않은 진술과 기록을 먼저 대조해 보세요."
    elif payload.discoveredEvidence:
        evidence = payload.discoveredEvidence[0]
        clue = f"{evidence.name or evidence.id}의 시간과 관련 진술을 다시 비교해 보세요."
    else:
        clue = "이미 확인한 진술 중 시간과 장소가 함께 언급된 문장을 먼저 묶어 보세요."

    if payload.hintLevel == "strong":
        text = f"가장 중요한 단서는 이것입니다: {clue}"
    elif payload.hintLevel == "direct":
        text = f"{clue} 그 항목이 어떤 진술과 맞물리는지 확인해 보세요."
    else:
        text = f"아직 보지 않은 결론보다, {clue}"
    return {"text": text}


def guard_spoiler(state: dict[str, Any]) -> dict[str, Any]:
    payload: HintRequest = state["payload"]
    text, safety = redact_solution_terms(state["text"], reveal_allowed=payload.revealAllowed)
    return {"text": text, "safety": safety}


def format_hint(state: dict[str, Any]) -> dict[str, Any]:
    safety = state.get("safety", Safety())
    return {
        "result": HintResponse(
            text=state["text"],
            level=state["level"],
            referencedEvidenceIds=state.get("evidence_ids", []),
            safety=Safety(
                leaksSolution=safety.leaks_solution,
                violatesCaseFacts=False,
                blockedTerms=list(safety.blocked_terms),
                repaired=safety.repaired,
                blockedReason=safety.blocked_reason,
            ),
        )
    }


def run_hint_graph(payload: HintRequest) -> HintResponse:
    state = run_langgraph_or_pipeline(
        {"payload": payload},
        [
            ("inspect_progress", inspect_progress),
            ("select_hint_level", select_hint_level),
            ("generate_hint", generate_hint),
            ("guard_spoiler", guard_spoiler),
            ("format_hint", format_hint),
        ],
    )
    return state["result"]
