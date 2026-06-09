from __future__ import annotations

import re

from app.ai_engine.schemas.retrieval import QuestionEntities


_TIME_PATTERNS = re.compile(
    r"(\d{1,2}:\d{2})|(\d{1,2}시(?:\s*\d{1,2}분)?)"
    r"|(오전|오후|저녁|밤|새벽|낮|아침)"
    r"|(사건\s*(?:당일|직후|직전|전|후))",
    re.IGNORECASE,
)

_LOCATION_TOKENS = (
    "서재", "방", "복도", "주방", "욕실", "거실", "정원", "차고",
    "현관", "계단", "2층", "1층", "3층", "저택", "밖", "외부", "현장",
)

_EVIDENCE_TOKENS = (
    "와인잔", "와인", "립스틱", "자국", "약", "약물", "처방",
    "출입기록", "출입 기록", "회중시계", "유언장", "통화기록", "통화 기록",
    "부검", "정전", "약상자",
)


def extract_question_entities(question_text: str, allowed_statement_text: str = "") -> QuestionEntities:
    combined = f"{question_text} {allowed_statement_text}"

    time_expressions = list({m.group(0) for m in _TIME_PATTERNS.finditer(combined) if m.group(0).strip()})
    location_terms = [tok for tok in _LOCATION_TOKENS if tok in combined]
    evidence_terms = [tok for tok in _EVIDENCE_TOKENS if tok in combined]

    return QuestionEntities(
        time_expressions=time_expressions,
        location_terms=location_terms,
        evidence_terms=evidence_terms,
    )
