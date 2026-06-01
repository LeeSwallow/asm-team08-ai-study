import logging

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from app.api.deps import (
    get_dialogue_service,
    get_event_repository,
    get_session_commands,
)
from app.application.dialogue_service import DialogueService
from app.application.session_commands import SessionCommands
from app.core.config import Settings, get_settings
from app.core.errors import bad_request, forbidden, service_unavailable
from app.core.leak_guard import assert_no_forbidden_refs
from app.core.observability import RequestContext
from app.domain.case_engine import visible_session_payload
from app.domain.event_processor import build_visual_state
from app.domain.event_types import EventType
from app.domain.interrogation_state import pressure_state as _pressure_state
from app.domain.interrogation_state import tension_level as _tension_level
from app.domain.models import Case, EventEntry, SessionState
from app.infra.event_repository import EventRepository
from app.infra.sse_transport import session_event_stream
from app.schemas.sessions import (
    AccusationRequest,
    AskQuestionRequest,
    BookmarkRequest,
    ContradictionRequest,
    CreateSessionRequest,
    DebugPressureRequest,
    DebugUnlockRequest,
    DialogueRequest,
    NoteRequest,
    NotesSummaryRequest,
    NoteUpdateRequest,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = logging.getLogger(__name__)


@router.post("")
def create_session(
    request: CreateSessionRequest,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
):
    session, case = commands.create_session(request.caseId)
    return _session_payload(session, case, event_repo)


@router.get("/{session_id}")
def get_session(
    session_id: str,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
):
    session, case = commands.load_session_and_case(session_id)
    return _session_payload(session, case, event_repo)


@router.post("/{session_id}/questions")
async def ask_question(
    session_id: str,
    request: AskQuestionRequest,
    raw_request: Request,
    commands: SessionCommands = Depends(get_session_commands),
    dialogue_service: DialogueService = Depends(get_dialogue_service),
    event_repo: EventRepository = Depends(get_event_repository),
):
    if request.questionText is not None:
        if not request.suspectId:
            raise bad_request("SUSPECT_REQUIRED_FOR_FREE_TEXT_QUESTION")
        result = await dialogue_service.submit(
            session_id=session_id,
            suspect_id=request.suspectId,
            message=request.questionText,
            question_id=request.questionId,
            request_context=_request_context(raw_request),
        )
        return _merge_session_payload(result, event_repo)
    if not request.questionId:
        raise bad_request("QUESTION_ID_OR_TEXT_REQUIRED")
    session, case = commands.load_session_and_case(session_id)
    question = next((item for item in case.questions if item.questionId == request.questionId), None)
    if question is None:
        raise bad_request("QUESTION_NOT_FOUND")
    if request.suspectId is not None and request.suspectId != question.characterId:
        raise bad_request("QUESTION_SUSPECT_MISMATCH")
    result = await dialogue_service.submit(
        session_id=session_id,
        suspect_id=question.characterId,
        message=question.text,
        question_id=request.questionId,
        request_context=_request_context(raw_request),
    )
    return _merge_session_payload(result, event_repo)


@router.post("/{session_id}/dialogue")
async def submit_dialogue(
    session_id: str,
    request: DialogueRequest,
    raw_request: Request,
    dialogue_service: DialogueService = Depends(get_dialogue_service),
    event_repo: EventRepository = Depends(get_event_repository),
):
    result = await dialogue_service.submit(
        session_id=session_id,
        suspect_id=request.suspectId,
        message=request.message,
        question_id=request.questionId,
        request_context=_request_context(raw_request),
    )
    return _merge_session_payload(result, event_repo)


@router.get("/{session_id}/events")
def stream_events(
    session_id: str,
    request: Request,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    once: bool = Query(default=False),
):
    session, case = commands.load_session_and_case(session_id)
    replay = event_repo.list_for_session(session.sessionId, after_event_id=last_event_id)
    logger.info(
        "sse connected",
        extra={
            "service": "backend",
            "request_id": getattr(request.state, "request_id", None),
            "session_id": session.sessionId,
            "case_id": case.caseId,
            "route": str(request.url.path),
            "last_event_id": last_event_id,
            "event_count": len(replay),
            "fallback_used": False,
        },
    )
    return StreamingResponse(
        session_event_stream(event_repo, session.sessionId, replay, last_event_id, once),
        media_type="text/event-stream",
    )


@router.post("/{session_id}/debug/pressure")
def debug_set_pressure(
    session_id: str,
    request: DebugPressureRequest,
    raw_request: Request,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
    settings: Settings = Depends(get_settings),
):
    _require_debug_tools(settings)
    result = commands.debug_set_pressure(
        session_id=session_id,
        suspect_id=request.suspectId,
        pressure=request.pressure,
        request_context=_request_context(raw_request),
    )
    _append_debug_events(result, event_repo, "pressure", {"suspectId": request.suspectId})
    return _merge_session_payload(result, event_repo)


@router.post("/{session_id}/debug/unlock")
def debug_unlock(
    session_id: str,
    request: DebugUnlockRequest,
    raw_request: Request,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
    settings: Settings = Depends(get_settings),
):
    _require_debug_tools(settings)
    result = commands.debug_unlock(
        session_id=session_id,
        target=request.target,
        request_context=_request_context(raw_request),
    )
    _append_debug_events(result, event_repo, "unlock", {"target": request.target})
    return _merge_session_payload(result, event_repo)


@router.post("/{session_id}/contradictions")
def raise_contradiction(
    session_id: str,
    request: ContradictionRequest,
    raw_request: Request,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
):
    result = commands.judge_contradiction(
        session_id=session_id,
        suspect_id=request.suspectId,
        statement_ids=request.statementIds,
        evidence_ids=request.evidenceIds,
        request_context=_request_context(raw_request),
    )
    _append_contradiction_events(result, event_repo)
    return _merge_session_payload(result, event_repo)


@router.post("/{session_id}/accusation")
def accuse(
    session_id: str,
    request: AccusationRequest,
    raw_request: Request,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
):
    result = commands.judge_accusation(
        session_id=session_id,
        suspect_id=request.suspectId,
        evidence_ids=request.evidenceIds,
        contradiction_ids=request.contradictionIds,
        statement_ids=request.statementIds,
        motive=request.motive,
        method=request.method,
        request_context=_request_context(raw_request),
    )
    _append_accusation_event(result, event_repo)
    return _merge_session_payload(result, event_repo)


@router.get("/{session_id}/notes")
def list_notes(
    session_id: str,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
):
    session, case = commands.load_session_and_case(session_id)
    payload = _session_payload(session, case, event_repo)
    return {
        "sessionId": session.sessionId,
        "caseId": case.caseId,
        "notes": payload["notes"],
        "notebook": payload["notebook"],
        "lastEventId": payload["lastEventId"],
    }


@router.post("/{session_id}/notes")
def create_note(
    session_id: str,
    request: NoteRequest,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
):
    result = commands.create_note(
        session_id=session_id,
        text=request.text,
        tags=request.tags,
        linked_statement_ids=request.linkedStatementIds,
        linked_evidence_ids=request.linkedEvidenceIds,
        linked_record_ids=request.linkedRecordIds,
    )
    _append_note_event(result, event_repo, EventType.NOTE_CREATED)
    return _merge_session_payload(result, event_repo)


@router.put("/{session_id}/notes/{note_id}")
def update_note(
    session_id: str,
    note_id: str,
    request: NoteUpdateRequest,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
):
    result = commands.update_note(
        session_id=session_id,
        note_id=note_id,
        text=request.text,
        tags=request.tags,
        linked_statement_ids=request.linkedStatementIds,
        linked_evidence_ids=request.linkedEvidenceIds,
        linked_record_ids=request.linkedRecordIds,
    )
    _append_note_event(result, event_repo, EventType.NOTE_UPDATED)
    return _merge_session_payload(result, event_repo)


@router.delete("/{session_id}/notes/{note_id}")
def delete_note(
    session_id: str,
    note_id: str,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
):
    result = commands.delete_note(session_id=session_id, note_id=note_id)
    _append_note_event(result, event_repo, EventType.NOTE_DELETED)
    return _merge_session_payload(result, event_repo)


@router.post("/{session_id}/bookmarks")
def create_bookmark(
    session_id: str,
    request: BookmarkRequest,
    commands: SessionCommands = Depends(get_session_commands),
    event_repo: EventRepository = Depends(get_event_repository),
):
    result = commands.create_bookmark(session_id, request.targetType, request.targetId, request.note)
    return _merge_session_payload(result, event_repo)


@router.post("/{session_id}/notes/summary")
async def summarize_notes(
    session_id: str,
    request: NotesSummaryRequest,
    commands: SessionCommands = Depends(get_session_commands),
):
    return await commands.summarize_notes(session_id, request.note)


@router.get("/{session_id}/summary")
async def get_summary(
    session_id: str,
    commands: SessionCommands = Depends(get_session_commands),
):
    return await commands.get_summary(session_id)


@router.get("/{session_id}/hint")
async def get_hint(
    session_id: str,
    commands: SessionCommands = Depends(get_session_commands),
):
    return await commands.get_hint(session_id)


@router.get("/{session_id}/ending")
async def get_ending(
    session_id: str,
    commands: SessionCommands = Depends(get_session_commands),
):
    return await commands.get_ending(session_id)


def _session_payload(session: SessionState, case: Case, event_repo: EventRepository) -> dict:
    payload = visible_session_payload(session, case)
    payload["lastEventId"] = event_repo.last_id(session.sessionId)
    payload["visualState"] = build_visual_state(session, case, session.selectedSuspectId)
    _assert_public_payload(payload, "session_payload")
    return payload


def _merge_session_payload(result: dict, event_repo: EventRepository) -> dict:
    session = result.pop("session")
    case = result.pop("case")
    payload = _session_payload(session, case, event_repo)
    payload.update(result)
    _assert_public_payload(payload, "merged_session_payload")
    return payload


def _assert_public_payload(payload: dict, surface: str) -> None:
    try:
        assert_no_forbidden_refs(payload, surface=surface)
    except ValueError as exc:
        logger.error("forbidden ref in public payload", extra={"service": "backend", "surface": surface, "fallback_used": False})
        raise service_unavailable(
            "PUBLIC_PAYLOAD_FORBIDDEN_REF",
            {"surface": surface, "fallbackUsed": False, "degradedReason": str(exc).split(":", 2)[0]},
        )


def _require_debug_tools(settings: Settings) -> None:
    if not settings.debug_tools_enabled:
        raise forbidden(
            "DEBUG_TOOLS_DISABLED",
            {"message": "Debug endpoints require BE_DEBUG_TOOLS_ENABLED=true."},
        )


def _append_note_event(result: dict, event_repo: EventRepository, event_type: EventType) -> None:
    session = result["session"]
    case = result["case"]
    note = result.get("note")
    payload = {"deletedNoteId": result.get("deletedNoteId")} if event_type == EventType.NOTE_DELETED else {"note": note}
    event = EventEntry(
        id=event_repo.next_id(session.sessionId),
        sessionId=session.sessionId,
        caseId=case.caseId,
        type=event_type.value,
        payload=payload,
    )
    event_repo.append_many([event])


def _append_debug_events(result: dict, event_repo: EventRepository, action: str, context: dict) -> None:
    session = result["session"]
    case = result["case"]
    debug_result = result.get("debugResult", {})
    events: list[EventEntry] = []
    next_index = event_repo.next_index(session.sessionId)

    def new_event(event_type: EventType, payload: dict) -> EventEntry:
        nonlocal next_index
        event = EventEntry(
            id=f"evt_{next_index:06d}",
            sessionId=session.sessionId,
            caseId=case.caseId,
            type=event_type.value,
            payload=payload,
        )
        next_index += 1
        return event

    if action == "pressure":
        suspect_id = str(context.get("suspectId") or session.selectedSuspectId or "")
        if suspect_id:
            pressure = session.pressureBySuspect.get(suspect_id, 0)
            events.append(
                new_event(
                    EventType.TENSION_CHANGED,
                    {
                        "suspectId": suspect_id,
                        "pressure": pressure,
                        "pressureState": _pressure_state(pressure),
                        "tensionLevel": _tension_level(pressure),
                        "tensionScore": pressure,
                        "debug": True,
                    },
                )
            )
            events.append(new_event(EventType.VISUAL_STATE_CHANGED, build_visual_state(session, case, suspect_id)))

    evidence_ids = {item.evidenceId for item in case.evidence}
    for item_id in debug_result.get("unlockedIds", []):
        if item_id in evidence_ids:
            events.append(new_event(EventType.EVIDENCE_UNLOCKED, {"evidenceId": item_id, "debug": True}))

    if debug_result.get("noteId"):
        note = next((item for item in session.notes if item.id == debug_result["noteId"]), None)
        if note is not None:
            events.append(new_event(EventType.NOTE_CREATED, {"note": note.model_dump(mode="json")}))

    events.append(
        new_event(
            EventType.DEBUG_SESSION_UPDATED,
            {
                "action": action,
                "target": context.get("target"),
                "suspectId": context.get("suspectId"),
                "unlockedCount": len(debug_result.get("unlockedIds", [])),
                "noteId": debug_result.get("noteId"),
                "debug": True,
            },
        )
    )
    event_repo.append_many(events)


def _append_contradiction_events(result: dict, event_repo: EventRepository) -> None:
    session = result["session"]
    case = result["case"]
    verdict = result.get("contradictionResult", {})
    events: list[EventEntry] = []
    next_index = event_repo.next_index(session.sessionId)

    def new_event(event_type: EventType, payload: dict) -> EventEntry:
        nonlocal next_index
        event = EventEntry(
            id=f"evt_{next_index:06d}",
            sessionId=session.sessionId,
            caseId=case.caseId,
            type=event_type.value,
            payload=payload,
        )
        next_index += 1
        return event

    if verdict.get("verdict") == "correct" and verdict.get("contradictionId"):
        contradiction_id = verdict["contradictionId"]
        contradiction = next((item for item in case.contradictions if item.contradictionId == contradiction_id), None)
        if contradiction is not None:
            events.append(
                new_event(
                    EventType.NOTE_CONTRADICTION_CANDIDATE_ADDED,
                    {
                        "contradictionId": contradiction.contradictionId,
                        "suspectId": contradiction.relatedCharacterId,
                        "statementIds": list(contradiction.requiredStatementIds),
                        "evidenceIds": list(contradiction.requiredEvidenceIds),
                        "text": contradiction.message,
                        "status": "discovered",
                        "submitEligible": True,
                    },
                )
            )

    evidence_ids = {item.evidenceId for item in case.evidence}
    for item_id in session.newlyUnlockedIds:
        if item_id in evidence_ids:
            events.append(new_event(EventType.EVIDENCE_UNLOCKED, {"evidenceId": item_id}))

    if verdict.get("verdict") == "correct" and verdict.get("newlyDiscovered") is True and verdict.get("contradictionId"):
        suspect_id = verdict.get("suspectId") or request_suspect_id(verdict, case)
        if suspect_id:
            pressure = session.pressureBySuspect.get(suspect_id, 0)
            events.append(
                new_event(
                    EventType.TENSION_CHANGED,
                    {
                        "suspectId": suspect_id,
                        "pressure": pressure,
                        "pressureState": _pressure_state(pressure),
                        "tensionLevel": _tension_level(pressure),
                        "tensionScore": pressure,
                    },
                )
            )
            events.append(new_event(EventType.VISUAL_STATE_CHANGED, build_visual_state(session, case, suspect_id)))

    event_repo.append_many(events)


def _append_accusation_event(result: dict, event_repo: EventRepository) -> None:
    session = result["session"]
    case = result["case"]
    accusation = result.get("accusationResult", {})
    payload = {
        "verdict": accusation.get("verdict"),
        "proofComplete": accusation.get("proofComplete"),
        "submittedMotive": accusation.get("submittedMotive"),
        "submittedMethod": accusation.get("submittedMethod"),
        "missingEvidenceIds": accusation.get("missingEvidenceIds", []),
        "missingContradictionIds": accusation.get("missingContradictionIds", []),
        "missingStatementIds": accusation.get("missingStatementIds", []),
        "message": accusation.get("message"),
        "phase": session.phase,
    }
    _assert_public_payload(payload, "accusation_sse_payload")
    event = EventEntry(
        id=event_repo.next_id(session.sessionId),
        sessionId=session.sessionId,
        caseId=case.caseId,
        type=EventType.ACCUSATION_RESOLVED.value,
        payload=payload,
    )
    event_repo.append_many([event])


def request_suspect_id(verdict: dict, case: Case) -> str | None:
    contradiction_id = verdict.get("contradictionId")
    contradiction = next((item for item in case.contradictions if item.contradictionId == contradiction_id), None)
    return contradiction.relatedCharacterId if contradiction else None


def _request_context(request: Request) -> RequestContext:
    return RequestContext(
        request_id=getattr(request.state, "request_id", None),
        route=str(request.url.path),
    )
