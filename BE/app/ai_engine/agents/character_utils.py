from __future__ import annotations

from app.ai_engine.core.solution_guard import contains_secret


def _normalized_tension_score(value: int | float | None) -> float | None:
    if value is None:
        return None
    score = float(value)
    if score <= 1:
        return score * 100
    return score


def _safe_short_text(value: object, max_length: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if contains_secret(text)[0] or any(term in text.lower() for term in ("secret", "solution", "isculprit", "secretnote")):
        return ""
    if len(text) > max_length:
        return text[: max_length - 1].rstrip() + "…"
    return text


def _strip_outer_dialogue_quotes(text: str) -> str:
    stripped = text.strip()
    quote_pairs = (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"))
    changed = True
    while changed and len(stripped) >= 2:
        changed = False
        for left, right in quote_pairs:
            if stripped.startswith(left) and stripped.endswith(right):
                stripped = stripped[len(left) : -len(right)].strip()
                changed = True
                break
    return stripped


def _choice_index(*values: object, modulo: int) -> int:
    if modulo <= 0:
        return 0
    rendered = "|".join(str(value or "") for value in values)
    return sum(ord(ch) for ch in rendered) % modulo
