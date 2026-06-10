from __future__ import annotations

from app.ai_engine.core.solution_guard import SafetyResult, contains_secret, redact_solution_terms
from app.ai_engine.core.text_normalization import normalize_text, sentence_parts


SAFE_DIALOGUE_PADDING = {
    "",
    "잠깐만요",
    "솔직히 말하면",
    "글쎄요",
    "그 질문은 좀 불편하네요",
    "제 기억은 그래요",
    "안녕하세요",
    "기억나는 건 거기까지예요",
    "정확히",
    "오해",
    "불쾌하네요",
}

CASE_CONTEXT_TOKENS = (
    "피해자",
    "용의자",
    "증거",
    "단서",
    "기록",
    "약",
    "약물",
    "처방",
    "복용",
    "의료",
    "의사",
    "와인잔",
    "와인",
    "립스틱",
    "자국",
    "서재",
    "복도",
    "현장",
    "범행",
    "알리바이",
)

_SALIENCE_STOPWORDS = {
    "한서연",
    "윤재호",
    "박민규",
    "최윤아",
    "사건",
    "당일",
    "무렵",
    "진술했다",
    "말했습니다",
    "있었다고",
    "했습니다",
    "제가",
    "저는",
    "그날",
    "것은",
    "것도",
}


def _salient_fact_terms(text: str) -> set[str]:
    normalized = normalize_text(text)
    terms: set[str] = set()
    for raw in normalized.replace(".", " ").replace(",", " ").split():
        token = raw.strip("…!?·:;()[]{}\"'")
        if len(token) < 2 or token in _SALIENCE_STOPWORDS:
            continue
        terms.add(token)
        if len(token) >= 4:
            terms.add(token[:3])
    return terms


def _generated_preserves_allowed_fact(
    generated: str,
    allowed_statement: str,
    allowed_context_terms: tuple[str, ...],
) -> bool:
    allowed_terms = _salient_fact_terms(allowed_statement)
    if not allowed_terms:
        return False
    generated_terms = _salient_fact_terms(generated)
    overlap = allowed_terms & generated_terms
    required = min(2, len(allowed_terms))
    if len(overlap) < required:
        return False
    normalized_generated = normalize_text(generated)
    return not _padding_has_unsupported_case_context(normalized_generated, allowed_statement, allowed_context_terms)


def _normalize_padding(text: str) -> str:
    return text.strip(" \t\n\r,.!?。！？")


def extract_case_context_terms(text: str) -> tuple[str, ...]:
    normalized = normalize_text(text)
    return tuple(token for token in CASE_CONTEXT_TOKENS if token in normalized)


def _padding_is_non_factual_guidance(text: str) -> bool:
    return False


def _padding_has_unsupported_case_context(
    text: str,
    allowed_statement: str,
    allowed_context_terms: tuple[str, ...] = (),
) -> bool:
    allowed_context = normalize_text(" ".join((allowed_statement, *allowed_context_terms)))
    return any(token in text and token not in allowed_context for token in CASE_CONTEXT_TOKENS)


def _padding_is_safe(
    text: str,
    allowed_statement: str = "",
    allowed_context_terms: tuple[str, ...] = (),
) -> bool:
    parts = [_normalize_padding(part) for part in sentence_parts(text)]
    if not parts:
        return True

    def part_is_safe(part: str) -> bool:
        if _padding_has_unsupported_case_context(part, allowed_statement, allowed_context_terms):
            return False
        if part in SAFE_DIALOGUE_PADDING or _padding_is_non_factual_guidance(part):
            return True
        for style_word in ("정확히", "오해", "불쾌하네요"):
            prefix = f"{style_word} "
            if part.startswith(prefix):
                return part_is_safe(part.removeprefix(prefix))
        return False

    return all(part_is_safe(part) for part in parts)


def enforce_allowed_statement(
    generated: str,
    allowed_statement: str,
    allowed_context_terms: tuple[str, ...] = (),
) -> tuple[str, bool]:
    allowed = normalize_text(allowed_statement)
    generated = normalize_text(generated)
    if not generated:
        return allowed, False

    if allowed in generated:
        prefix, suffix = generated.split(allowed, 1)
        if _padding_is_safe(prefix, allowed, allowed_context_terms) and _padding_is_safe(
            suffix,
            allowed,
            allowed_context_terms,
        ):
            return generated, False
        return allowed, generated != allowed

    if _generated_preserves_allowed_fact(generated, allowed_statement, allowed_context_terms):
        return generated, False

    safe_parts = [part for part in sentence_parts(generated) if part and part in allowed]
    if safe_parts:
        return " ".join(safe_parts), True

    return allowed, generated != allowed


def guard_dialogue_text(
    text: str,
    allowed_statement: str,
    reveal_allowed: bool = False,
    enforce_statement_scope: bool = True,
    allowed_context_terms: tuple[str, ...] = (),
) -> tuple[str, SafetyResult]:
    if not enforce_statement_scope:
        redacted, redaction = redact_solution_terms(text, reveal_allowed=reveal_allowed)
        final_leaks, final_blocked_terms = contains_secret(redacted, reveal_allowed=reveal_allowed)
        return redacted, SafetyResult(
            leaks_solution=final_leaks,
            violates_case_facts=False,
            blocked_terms=final_blocked_terms or redaction.blocked_terms,
            repaired=redaction.repaired,
            blocked_reason=redaction.blocked_reason,
        )

    scoped, repaired_scope = enforce_allowed_statement(text, allowed_statement, allowed_context_terms)
    redacted, redaction = redact_solution_terms(scoped, reveal_allowed=reveal_allowed)
    final_text, repaired_after_redaction = enforce_allowed_statement(
        redacted,
        allowed_statement,
        allowed_context_terms,
    )
    final_leaks, final_blocked_terms = contains_secret(final_text, reveal_allowed=reveal_allowed)
    final_violates = not (
        normalize_text(allowed_statement) in normalize_text(final_text)
        or _generated_preserves_allowed_fact(final_text, allowed_statement, allowed_context_terms)
    )

    blocked_reason = redaction.blocked_reason
    if repaired_scope or repaired_after_redaction:
        blocked_reason = "case_fact_scope_repaired"

    return final_text, SafetyResult(
        leaks_solution=final_leaks,
        violates_case_facts=final_violates,
        blocked_terms=final_blocked_terms,
        repaired=repaired_scope or redaction.repaired or repaired_after_redaction,
        blocked_reason=blocked_reason,
    )
