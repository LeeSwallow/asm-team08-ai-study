import json

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
