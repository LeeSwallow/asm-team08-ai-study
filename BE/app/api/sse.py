import json

from app.domain.models import EventEntry


def sse_format(event: EventEntry) -> str:
    data = json.dumps({"sessionId": event.sessionId, "payload": event.payload}, ensure_ascii=False)
    return f"event: {event.type}\nid: {event.id}\ndata: {data}\n\n"
