from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    request_id: str | None
    route: str
