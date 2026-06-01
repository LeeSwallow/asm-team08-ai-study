from __future__ import annotations

from typing import Any

from app.core.guard import redact_solution_terms
from app.prompts.ending import ENDING_SYSTEM_PROMPT
from app.schemas.common import Safety
from app.schemas.endings import EndingExplainRequest, EndingExplainResponse

from .common import run_langgraph_or_pipeline


RESULT_LABELS = {
    "correct": "정답",
    "partial": "부분 정답",
    "insufficient": "근거 부족",
    "wrong": "오답",
}


def load_verdict(state: dict[str, Any]) -> dict[str, Any]:
    payload: EndingExplainRequest = state["payload"]
    result = payload.verdict.result
    return {"result": result, "label": payload.verdict.label or RESULT_LABELS.get(result, result), "prompt": ENDING_SYSTEM_PROMPT}


def generate_explanation(state: dict[str, Any]) -> dict[str, Any]:
    payload: EndingExplainRequest = state["payload"]
    verdict = payload.verdict
    chunks = [f"Backend 판정은 {state['label']}입니다."]
    if payload.storyline:
        if payload.storyline.publicPremise:
            chunks.append(f"공개 전제: {payload.storyline.publicPremise}")
        objective = payload.storyline.currentObjective or payload.storyline.openingObjective
        if objective:
            chunks.append(f"마지막 목표: {objective}")
    if verdict.reason:
        chunks.append(verdict.reason)
    if payload.usedQuestionCount is not None:
        chunks.append(f"사용한 질문 수는 {payload.usedQuestionCount}회입니다.")
    if payload.foundCoreContradictionCount is not None:
        chunks.append(f"발견한 핵심 모순은 {payload.foundCoreContradictionCount}개입니다.")
    if verdict.missedEvidenceIds:
        chunks.append(f"놓친 근거 ID: {', '.join(verdict.missedEvidenceIds)}.")
    if payload.culpritName and (payload.revealAllowed or verdict.revealAllowed):
        chunks.append(f"최종 범인 정보: {payload.culpritName}.")
    return {"explanation": " ".join(chunks)}


def guard_ending(state: dict[str, Any]) -> dict[str, Any]:
    payload: EndingExplainRequest = state["payload"]
    reveal_allowed = payload.revealAllowed or payload.verdict.revealAllowed
    explanation, safety = redact_solution_terms(state["explanation"], reveal_allowed=reveal_allowed)
    return {"explanation": explanation, "safety": safety}


def format_ending(state: dict[str, Any]) -> dict[str, Any]:
    safety = state.get("safety", Safety())
    return {
        "result": EndingExplainResponse(
            result=state["result"],
            explanation=state["explanation"],
            safety=Safety(
                leaksSolution=safety.leaks_solution,
                violatesCaseFacts=False,
                blockedTerms=list(safety.blocked_terms),
                repaired=safety.repaired,
                blockedReason=safety.blocked_reason,
            ),
        )
    }


def run_ending_graph(payload: EndingExplainRequest) -> EndingExplainResponse:
    state = run_langgraph_or_pipeline(
        {"payload": payload},
        [
            ("load_verdict", load_verdict),
            ("generate_explanation", generate_explanation),
            ("guard_ending", guard_ending),
            ("format_ending", format_ending),
        ],
    )
    return state["result"]
