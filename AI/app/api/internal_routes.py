from typing import Any

from fastapi import APIRouter

from app.core.llm import llm_status
from app.graph.dialogue_graph import run_dialogue_graph
from app.graph.ending_graph import run_ending_graph
from app.graph.hint_graph import run_hint_graph
from app.graph.summary_graph import run_summary_graph
from app.schemas.dialogue import DialogueRequest, DialogueResponse
from app.schemas.endings import EndingExplainRequest, EndingExplainResponse
from app.schemas.hints import HintRequest, HintResponse
from app.schemas.notes import NotesSummaryRequest, NotesSummaryResponse

router = APIRouter()


@router.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "ai", **llm_status()}


@router.post("/internal/v1/dialogue/respond", response_model=DialogueResponse)
def dialogue_respond(payload: DialogueRequest) -> DialogueResponse:
    return run_dialogue_graph(payload)


@router.post("/internal/v1/hints", response_model=HintResponse)
def hints(payload: HintRequest) -> HintResponse:
    return run_hint_graph(payload)


@router.post("/internal/v1/notes/summary", response_model=NotesSummaryResponse)
def notes_summary(payload: NotesSummaryRequest) -> NotesSummaryResponse:
    return run_summary_graph(payload)


@router.post("/internal/v1/endings/explain", response_model=EndingExplainResponse)
def endings_explain(payload: EndingExplainRequest) -> EndingExplainResponse:
    return run_ending_graph(payload)
