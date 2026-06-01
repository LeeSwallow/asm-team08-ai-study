import asyncio
from collections.abc import AsyncIterator

from app.api.sse import sse_format
from app.domain.models import EventEntry
from app.infra.event_repository import EventRepository


async def session_event_stream(
    event_repo: EventRepository,
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
