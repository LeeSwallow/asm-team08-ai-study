import asyncio
import json
from collections.abc import AsyncIterator

from app.application.ports import EventRepositoryPort
from app.domain.models import EventEntry


def sse_format(event: EventEntry) -> str:
    data = json.dumps(
        {
            "id": event.id,
            "type": event.type,
            "eventType": event.type,
            "sessionId": event.sessionId,
            "payload": event.payload,
            "createdAt": event.createdAt.isoformat(),
        },
        ensure_ascii=False,
    )
    return f"event: {event.type}\nid: {event.id}\ndata: {data}\n\n"


async def session_event_stream(
    event_repo: EventRepositoryPort,
    session_id: str,
    replay: list[EventEntry],
    last_event_id: str | None,
    once: bool,
) -> AsyncIterator[str]:
    for event in replay:
        yield sse_format(event)
    if once:
        return

    last_seen = replay[-1].id if replay else last_event_id
    while True:
        await asyncio.sleep(1)
        events = event_repo.list_for_session(session_id, after_event_id=last_seen)
        for event in events:
            last_seen = event.id
            yield sse_format(event)
