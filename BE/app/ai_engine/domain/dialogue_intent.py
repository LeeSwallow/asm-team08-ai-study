from __future__ import annotations


TYPO_NORMALIZATIONS = {
    "파해자": "피해자",
    "피햬자": "피해자",
    "피해쟈": "피해자",
    "복용 한": "복용한",
    "와인 잔": "와인잔",
    "립 스틱": "립스틱",
}

EVIDENCE_TOKENS = (
    "증거",
    "단서",
    "발소리",
    "복도",
    "기록",
    "목격",
    "설명",
    "와인잔",
    "와인",
    "립스틱",
    "자국",
    "약",
    "약물",
    "복용",
    "처방",
    "의사",
    "의료",
    "피해자",
    "사망",
    "검사",
    "진료",
)

PERSON_OR_RELATION_TOKENS = (
    "누가",
    "누구",
    "다른 사람",
    "관계",
    "아는 사람",
    "같이",
)


def normalize_dialogue_text(question_text: str) -> str:
    normalized = " ".join(question_text.strip().lower().split())
    for source, target in TYPO_NORMALIZATIONS.items():
        normalized = normalized.replace(source, target)
    return normalized


def classify_dialogue_intent(question_text: str, dialogue_mode: str | None = None) -> str:
    mode = (dialogue_mode or "").strip().lower()
    normalized = normalize_dialogue_text(question_text)
    if mode in {"greeting", "small_talk", "small-talk", "greeting/small_talk"}:
        return "greeting"
    if mode in {"unmatched", "clarification", "unmatched/clarification"}:
        return "unmatched"
    if mode in {"evidence", "evidence_question"}:
        return "evidence"
    if mode in {"location_time", "timeline_question", "timeline", "alibi", "alibi_question"}:
        return "location_time"
    if mode in {"accusation", "pressure", "pressure_followup", "accusation/pressure"}:
        return "pressure"

    if any(token in normalized for token in ("안녕", "반가", "처음", "인사")):
        return "greeting"
    if any(token in normalized for token in ("어디", "위치", "장소", "몇 시", "몇시", "22시", "시간", "이후", "전후")):
        return "location_time"
    if any(token in normalized for token in EVIDENCE_TOKENS):
        return "evidence"
    if any(token in normalized for token in PERSON_OR_RELATION_TOKENS) and mode in {"case", "case_question", ""}:
        return "evidence"
    if any(token in normalized for token in ("왜", "거짓", "거짓말", "수상", "압박", "솔직", "정말")):
        return "pressure"
    if mode in {"case", "case_question"}:
        return "case_question"
    return "case_question"
