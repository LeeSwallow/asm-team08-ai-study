from __future__ import annotations

import re


GENERIC_CASE_TOKENS = {
    "사건",
    "피해자",
    "용의자",
    "서재",
    "방",
    "기록",
    "단서",
    "증거",
    "현장",
    "흔적",
    "흔적이",
    "불명",
    "전후",
    "발견",
    "발견됐다",
    "있다",
    "없다",
}


def normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def text_tokens(value: str | None) -> set[str]:
    normalized = normalize_text(value)
    return {
        token
        for token in re.split(r"[^0-9a-zA-Z가-힣]+", normalized)
        if len(token) >= 2
    }


def meaningful_tokens(value: str | None) -> set[str]:
    return {
        token
        for token in text_tokens(value)
        if token not in GENERIC_CASE_TOKENS and not token.isdigit()
    }


def overlap_score(message: str, *texts: str | None) -> int:
    message_tokens = text_tokens(message)
    if not message_tokens:
        return 0
    best = 0
    compact_message = normalize_text(message).replace(" ", "")
    for text in texts:
        text_tokens_for_item = text_tokens(text)
        compact_text = normalize_text(text).replace(" ", "")
        score = len(message_tokens & text_tokens_for_item)
        if compact_text and compact_text in compact_message:
            score += 3
        best = max(best, score)
    return best


def evidence_mention_score(player_message: str, evidence: object) -> int:
    message = normalize_text(player_message)
    compact_message = message.replace(" ", "")
    name = str(getattr(evidence, "name", "") or "")
    description = str(getattr(evidence, "description", "") or "")
    found_at = str(getattr(evidence, "foundAt", "") or "")

    score = 0
    compact_name = normalize_text(name).replace(" ", "")
    if compact_name and compact_name in compact_message:
        score += 5
    name_score = len(text_tokens(message) & meaningful_tokens(name)) * 3
    description_score = len(text_tokens(message) & meaningful_tokens(description)) * 2
    score += name_score
    score += description_score
    if name_score or description_score:
        score += len(text_tokens(message) & meaningful_tokens(found_at)) * 1
    return score


def evidence_is_mentioned(player_message: str, evidence: object) -> bool:
    return evidence_mention_score(player_message, evidence) >= 2
