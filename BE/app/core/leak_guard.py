from typing import Any


FORBIDDEN_REF_TOKENS = (
    "secret",
    "solution",
    "privatetimeline",
    "privateevents",
    "privatemotive",
    "privaterefs",
    "culprit",
    "culpritid",
    "isculprit",
    "finaldiscovery",
    "finalverdict",
    "actualaction",
    "actuallocation",
    "secretnote",
)


def forbidden_ref_hits(value: Any, path: str = "$") -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            for token in FORBIDDEN_REF_TOKENS:
                if token in key_text:
                    hits.append({"path": f"{path}.{key}", "token": token, "where": "key"})
            hits.extend(forbidden_ref_hits(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(forbidden_ref_hits(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        text = value.lower()
        for token in FORBIDDEN_REF_TOKENS:
            if token in text:
                hits.append({"path": path, "token": token, "where": "value"})
                break
    return hits


def assert_no_forbidden_refs(value: Any, *, surface: str) -> None:
    hits = forbidden_ref_hits(value)
    if hits:
        paths = ", ".join(f"{hit['path']}:{hit['token']}" for hit in hits[:5])
        raise ValueError(f"FORBIDDEN_REF_LEAK:{surface}:{paths}")
