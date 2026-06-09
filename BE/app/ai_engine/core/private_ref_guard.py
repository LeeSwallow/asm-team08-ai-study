from __future__ import annotations


FORBIDDEN_PRIVATE_REF_KEYS = frozenset(
    {
        "secret",
        "solution",
        "privateTimeline",
        "privateEvents",
        "privateMotive",
        "privateRefs",
        "culprit",
        "culpritId",
        "isCulprit",
        "finalDiscovery",
        "finalVerdict",
        "actualAction",
        "actualLocation",
        "secretNote",
        "privateNote",
        "culpritInference",
        "isLie",
        "hidden",
        "hiddenSolution",
    }
)


def _is_forbidden_private_key(key: object) -> bool:
    normalized = str(key)
    lowered = normalized.lower()
    return (
        normalized in FORBIDDEN_PRIVATE_REF_KEYS
        or lowered.startswith("private")
        or lowered.startswith("secret")
        or lowered.startswith("hidden")
        or "culprit" in lowered
        or "solution" in lowered
        or lowered in {"islie", "actualaction", "actuallocation", "finaldiscovery", "finalverdict"}
    )


def _is_hidden_private_item(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    visibility = str(value.get("visibility", "")).lower()
    return bool(value.get("hidden") is True or visibility in {"hidden", "private", "secret"})


def strip_forbidden_private_refs(value: object) -> object:
    """Drop hidden-truth keys from BE-provided public context before agents see it."""
    if isinstance(value, dict):
        if _is_hidden_private_item(value):
            return {}
        return {
            key: strip_forbidden_private_refs(item)
            for key, item in value.items()
            if not _is_forbidden_private_key(key)
        }
    if isinstance(value, list):
        return [strip_forbidden_private_refs(item) for item in value if not _is_hidden_private_item(item)]
    return value
