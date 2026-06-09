from __future__ import annotations

from dataclasses import dataclass
import re

from app.ai_engine.core.text_normalization import normalize_text


SECRET_PATTERNS = [
    "범인",
    "진범",
    "살해",
    "살인",
    "동기",
    "흉기",
    "결정적 증거",
    "culprit",
    "killer",
    "motive",
    "solution",
    "secret",
    "hidden truth",
    "privateTimeline",
    "privateEvents",
    "privateMotive",
    "privateRefs",
    "secretNote",
    "isCulprit",
    "culpritId",
    "finalDiscovery",
    "finalVerdict",
    "actualAction",
    "actualLocation",
    "privateNote",
    "culpritInference",
    "isLie",
    "hidden",
    "hiddenSolution",
    "비밀",
    "숨겨진 진실",
]


@dataclass(frozen=True)
class SafetyResult:
    leaks_solution: bool = False
    violates_case_facts: bool = False
    blocked_terms: tuple[str, ...] = ()
    fallback_used: bool = False
    repaired: bool = False
    blocked_reason: str | None = None


def contains_secret(text: str, reveal_allowed: bool = False) -> tuple[bool, tuple[str, ...]]:
    if reveal_allowed:
        return False, ()
    lowered = text.lower()
    blocked = tuple(term for term in SECRET_PATTERNS if term.lower() in lowered)
    return bool(blocked), blocked


def redact_solution_terms(text: str, reveal_allowed: bool = False) -> tuple[str, SafetyResult]:
    leaks, blocked_terms = contains_secret(text, reveal_allowed=reveal_allowed)
    if not leaks:
        return text, SafetyResult()

    redacted = text
    for term in sorted(blocked_terms, key=len, reverse=True):
        redacted = re.sub(re.escape(term), "그 부분", redacted, flags=re.IGNORECASE)
    return redacted, SafetyResult(
        leaks_solution=True,
        blocked_terms=blocked_terms,
        repaired=True,
        blocked_reason="solution_terms_redacted",
    )
