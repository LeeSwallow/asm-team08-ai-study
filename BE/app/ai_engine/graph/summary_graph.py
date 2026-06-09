from __future__ import annotations

from typing import Any

from app.ai_engine.core.solution_guard import redact_solution_terms
from app.ai_engine.prompts.summary import SUMMARY_SYSTEM_PROMPT
from app.ai_engine.schemas.safety import Safety
from app.ai_engine.schemas.notes import NotesSummaryRequest, NotesSummaryResponse, SummaryItem

from .common import run_langgraph_or_pipeline


def load_sources(state: dict[str, Any]) -> dict[str, Any]:
    payload: NotesSummaryRequest = state["payload"]
    evidence_ids = [item.id for item in payload.discoveredEvidence]
    return {"evidence_ids": evidence_ids, "prompt": SUMMARY_SYSTEM_PROMPT}


def summarize_logs(state: dict[str, Any]) -> dict[str, Any]:
    payload: NotesSummaryRequest = state["payload"]
    items: list[SummaryItem] = []
    if payload.storyline:
        if payload.storyline.currentObjective:
            items.append(SummaryItem(sourceId=payload.storyline.currentActId or "current_objective", text=f"현재 목표: {payload.storyline.currentObjective}"))
        elif payload.storyline.openingObjective:
            items.append(SummaryItem(sourceId="opening_objective", text=f"초기 목표: {payload.storyline.openingObjective}"))
        if payload.storyline.publicPremise and len(items) < payload.maxItems:
            items.append(SummaryItem(sourceId="public_premise", text=f"공개 전제: {payload.storyline.publicPremise}"))
        remaining_timeline_slots = payload.maxItems - len(items)
        public_timeline = [event for event in payload.storyline.visibleTimeline if not getattr(event, "hidden", False)]
        for event in public_timeline[:remaining_timeline_slots]:
            time_label = f"{event.time} " if event.time else ""
            description = f": {event.description}" if event.description else ""
            items.append(SummaryItem(sourceId=event.sourceId or event.title, text=f"{time_label}{event.title}{description}"))
    for log in payload.dialogueLogs[: payload.maxItems]:
        if len(items) >= payload.maxItems:
            break
        source_id = log.statementId or log.id or log.speaker
        items.append(SummaryItem(sourceId=source_id, text=f"{log.speaker}: {log.text}"))
    remaining = payload.maxItems - len(items)
    if remaining > 0:
        for evidence in payload.discoveredEvidence[:remaining]:
            label = evidence.name or evidence.id
            description = evidence.description or "세부 설명 없음"
            items.append(SummaryItem(sourceId=evidence.id, text=f"{label}: {description}"))
    summary = " / ".join(item.text for item in items) if items else "아직 요약할 대화나 증거가 없습니다."
    return {"items": items, "summary": summary}


def guard_summary(state: dict[str, Any]) -> dict[str, Any]:
    payload: NotesSummaryRequest = state["payload"]
    summary, safety = redact_solution_terms(state["summary"], reveal_allowed=payload.revealAllowed)
    safe_items = []
    leaks = safety.leaks_solution
    blocked = list(safety.blocked_terms)
    for item in state["items"]:
        text, item_safety = redact_solution_terms(item.text, reveal_allowed=payload.revealAllowed)
        leaks = leaks or item_safety.leaks_solution
        blocked.extend(item_safety.blocked_terms)
        safe_items.append(SummaryItem(sourceId=item.sourceId, text=text))
    return {
        "summary": summary,
        "items": safe_items,
        "safety": Safety(
            leaksSolution=leaks,
            blockedTerms=sorted(set(blocked)),
            repaired=leaks,
            blockedReason="solution_terms_redacted" if leaks else None,
        ),
    }


def format_summary(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "result": NotesSummaryResponse(
            summary=state["summary"],
            items=state["items"],
            evidenceIds=state.get("evidence_ids", []),
            safety=state.get("safety", Safety()),
        )
    }


def run_summary_graph(payload: NotesSummaryRequest) -> NotesSummaryResponse:
    state = run_langgraph_or_pipeline(
        {"payload": payload},
        [
            ("load_sources", load_sources),
            ("summarize_logs", summarize_logs),
            ("guard_summary", guard_summary),
            ("format_summary", format_summary),
        ],
    )
    return state["result"]
