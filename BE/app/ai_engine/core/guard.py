from __future__ import annotations

import re
from dataclasses import dataclass


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

SAFE_DIALOGUE_PADDING = {
    "",
    "잠깐만요",
    "솔직히 말하면",
    "글쎄요",
    "그 질문은 좀 불편하네요",
    "더 보탤 말은 많지 않아요",
    "제 기억은 그래요",
    "안녕하세요",
    "갑작스럽지만 협조하겠습니다",
    "다만 제가 확인해 드릴 수 있는 건",
    "시간대를 묻는 거라면",
    "제 기억은 이렇습니다",
    "그 단서와 연결해 단정할 수는 없어요",
    "제가 직접 말할 수 있는 건",
    "몰아붙여도 제 대답은 달라지지 않아요",
    "시간대를 묻는 거라면, 제 기억은 이렇습니다",
    "그 단서와 연결해 단정할 수는 없어요. 제가 직접 말할 수 있는 건",
    "조심스럽게 말씀드리면",
    "조심스럽게 말씀드리면 시간대를 묻는 거라면, 제 기억은 이렇습니다",
    "조심스럽게 말씀드리면 그 단서와 연결해 단정할 수는 없어요",
    "조심스럽게 말씀드리면 그 단서와 연결해 단정할 수는 없어요. 제가 직접 말할 수 있는 건",
    "조심스럽게 말씀드리면 몰아붙여도 제 대답은 달라지지 않아요",
    "조심스럽게 말씀드리면 솔직히 말하면",
    "시간대를 묻는 거라면, 제 기억은 이렇게 정리됩니다",
    "그 이상은 추측하고 싶지 않습니다",
    "그 단서만으로 단정할 수는 없습니다",
    "그 단서를 묻는 거라면, 제 말만으로 단정할 수는 없습니다",
    "립스틱이나 와인잔 같은 단서는 제 말만으로 단정할 수는 없습니다",
    "그 와인잔 이야기를 제게 돌리지 마세요",
    "제가 직접 확인한 건 이 정도입니다",
    "립스틱 자국은 공개된 단서와 대조해 보시죠",
    "의학 쪽 단서를 묻는 거라면, 제가 공개적으로 확인할 수 있는 범위는 제한적입니다",
    "의학적으로 단정하려면 공개된 기록부터 맞춰 봐야 합니다",
    "제가 지금 말할 수 있는 건 여기까지입니다",
    "처방이나 복용 약은 공개된 의료 단서와 대조해 보세요",
    "다른 사람을 특정하라는 질문이라면, 제가 공개적으로 확인할 수 있는 범위는 제한적입니다",
    "제가 직접 확인해 드릴 수 있는 말은 이것뿐입니다",
    "그 단서만으로 단정할 수는 없습니다. 제가 직접 확인해 드릴 수 있는 말은 이것뿐입니다",
    "그 단서를 묻는 거라면, 제 말만으로 단정할 수는 없습니다. 제가 직접 확인해 드릴 수 있는 말은 이것뿐입니다",
    "립스틱이나 와인잔 같은 단서는 제 말만으로 단정할 수는 없습니다. 제가 직접 확인해 드릴 수 있는 말은 이것뿐입니다",
    "그 와인잔 이야기를 제게 돌리지 마세요. 제가 직접 확인한 건 이 정도입니다",
    "그 와인잔 이야기를 제게 돌리지 마세요. 제가 직접 확인한 건 이 정도입니다. 립스틱 자국은 공개된 단서와 대조해 보시죠",
    "의학 쪽 단서를 묻는 거라면, 제가 공개적으로 확인할 수 있는 범위는 제한적입니다. 제가 직접 확인해 드릴 수 있는 말은 이것뿐입니다",
    "의학적으로 단정하려면 공개된 기록부터 맞춰 봐야 합니다. 제가 지금 말할 수 있는 건 여기까지입니다",
    "의학적으로 단정하려면 공개된 기록부터 맞춰 봐야 합니다. 제가 지금 말할 수 있는 건 여기까지입니다. 처방이나 복용 약은 공개된 의료 단서와 대조해 보세요",
    "다른 사람을 특정하라는 질문이라면, 제가 공개적으로 확인할 수 있는 범위는 제한적입니다. 제가 직접 확인해 드릴 수 있는 말은 이것뿐입니다",
    "몰아붙여도 지금 제 대답은 달라지지 않습니다",
    "다만 같은 말을 반복하라는 식의 질문은 불편하군요",
    "방금 말씀드린 범위를 넘겨 단정하라고 하시면 곤란합니다",
    "조심스럽게 말씀드리면 시간대를 묻는 거라면, 제 기억은 이렇게 정리됩니다",
    "조심스럽게 말씀드리면 그 단서만으로 단정할 수는 없습니다",
    "조심스럽게 말씀드리면 그 단서만으로 단정할 수는 없습니다. 제가 직접 확인해 드릴 수 있는 말은 이것뿐입니다",
    "조심스럽게 말씀드리면 몰아붙여도 지금 제 대답은 달라지지 않습니다",
    "정확히",
    "오해",
    "불쾌하군요",
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


@dataclass(frozen=True)
class SafetyResult:
    leaks_solution: bool = False
    violates_case_facts: bool = False
    blocked_terms: tuple[str, ...] = ()
    fallback_used: bool = False
    repaired: bool = False
    blocked_reason: str | None = None


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def contains_secret(text: str, reveal_allowed: bool = False) -> tuple[bool, tuple[str, ...]]:
    if reveal_allowed:
        return False, ()
    lowered = text.lower()
    blocked = tuple(term for term in SECRET_PATTERNS if term.lower() in lowered)
    return bool(blocked), blocked


def sentence_parts(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?。！？])\s+|(?<=[요다죠까])\s+", normalize_text(text))
    return [part.strip() for part in parts if part.strip()]


def _normalize_padding(text: str) -> str:
    return re.sub(r"^[\s,.!?。！？]+|[\s,.!?。！？]+$", "", text).strip()


def extract_case_context_terms(text: str) -> tuple[str, ...]:
    normalized = normalize_text(text)
    return tuple(token for token in CASE_CONTEXT_TOKENS if token in normalized)


def _padding_is_non_factual_guidance(text: str) -> bool:
    if not text or contains_secret(text)[0] or len(text) > 100:
        return False
    factual_predicate_patterns = (
        r"\S+(?:했|하였|있었|없었|먹었|마셨|갔|왔|봤|보았|만났|들었|열었|닫았|숨겼|훔쳤|남겼|발견됐|발견되었|복용했|처방했|처방됐|처방되었|착용했|사용했|만졌)습니다\b",
        r"\S+(?:했다|하였다|있었다|없었다|먹었다|마셨다|갔다|왔다|봤다|보았다|만났다|들었다|열었다|닫았다|숨겼다|훔쳤다|남겼다|발견됐다|발견되었다|복용했다|처방했다|처방됐다|처방되었다|착용했다|사용했다|만졌다)\b",
        r"\S+(?:했다|하였다|있었다|없었다|먹었다|마셨다|갔다|왔다|봤다|보았다|만났다|들었다|열었다|닫았다|숨겼다|훔쳤다|남겼다|발견됐다|발견되었다|복용했다|처방했다|처방됐다|처방되었다|착용했다|사용했다|만졌다)고\b",
    )
    if any(token in text for token in CASE_CONTEXT_TOKENS) and any(
        re.search(pattern, text) for pattern in factual_predicate_patterns
    ):
        return False
    meta_guidance_patterns = (
        r"^(?:제가\s*)?(?:공개적으로\s*)?(?:말할 수 있는|확인할 수 있는|답할 수 있는)\s*(?:범위|건|것)",
        r"^(?:공개된\s*)?(?:단서|기록|의료 단서|증거)(?:와|부터|를|은|는)\s*(?:대조|확인)",
        r"^(?:그|이|저)\s*(?:단서|질문|기록|와인잔 이야기)(?:만으로|를|은|는|부터|와)",
        r"^(?:단정|추측)(?:하려면|할 수|하고 싶지)",
        r"^(?:같은 말을 반복|방금 말씀드린 범위|몰아붙여도|질문이|그 질문)",
    )
    return any(re.search(pattern, text) for pattern in meta_guidance_patterns)


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
        if re.fullmatch(r".{1,24}로서 조심스럽게 말씀드리면", part):
            return True
        if re.fullmatch(r"(정확히|오해|불쾌하군요) .{1,24}로서 조심스럽게 말씀드리면", part):
            return True
        for role_prefix in ("용의자", "조카", "의사", "가정부", "동업자"):
            prefix = f"{role_prefix}로서 조심스럽게 말씀드리면 "
            if part.startswith(prefix):
                return part_is_safe(part.removeprefix(prefix))
            for style_word in ("정확히", "오해", "불쾌하군요"):
                styled_prefix = f"{style_word} {role_prefix}로서 조심스럽게 말씀드리면 "
                if part.startswith(styled_prefix):
                    return part_is_safe(part.removeprefix(styled_prefix))
        for style_word in ("정확히", "오해", "불쾌하군요"):
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

    safe_parts = [part for part in sentence_parts(generated) if part and part in allowed]
    if safe_parts:
        return " ".join(safe_parts), True

    return allowed, generated != allowed


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
    final_violates = normalize_text(allowed_statement) not in normalize_text(final_text)

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
