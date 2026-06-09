from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ai_engine.core.guard import normalize_text
from app.ai_engine.schemas.agents import CheckedCharacterReply, DialogueDirectorPlan
from app.ai_engine.schemas.dialogue import DialogueRequest


_TIME_PATTERN = re.compile(r"(?<!\d)(\d{1,2})(?::|시\s*)(\d{1,2})?\s*분?")
_NEGATION_PATTERN = re.compile(r"(?:않|아니|못|없|안\s)")

_LOCATION_PATTERNS = {
    "location:study": ("서재",),
    "location:hallway": ("복도",),
    "location:control_room": ("관리실",),
    "location:reception_room": ("응접실",),
    "location:guest_room": ("손님방",),
    "location:bedroom": ("침실",),
    "location:own_room": ("제 방", "자기 방"),
    "location:mansion": ("저택",),
    "location:garden": ("정원",),
    "location:kitchen": ("주방",),
    "location:living_room": ("거실",),
    "location:entrance": ("현관",),
    "location:stairs": ("계단",),
    "location:outside": ("외부", "밖으로", "밖에"),
    "location:scene": ("현장",),
}

_LOCATION_ASSERTION_PATTERN = re.compile(
    r"(?:있었|있습니다|있어요|없었|갔|왔|들어갔|나갔|머물|향했|도착)"
)

_OBJECT_PATTERNS = {
    "object:victim": ("피해자", "회장님"),
    "object:door": ("문이", "문을", "서재 문"),
    "object:wine": ("와인", "와인잔"),
    "object:lipstick": ("립스틱",),
    "object:ring": ("반지",),
    "object:medicine": ("약을", "약은", "약이", "약상자", "약물", "복용분", "복용"),
    "object:medical_record": ("의료 기록", "건강 기록"),
    "object:schedule": ("일정 서류", "일정표"),
    "object:will": ("유언장",),
    "object:key": ("열쇠",),
    "object:call": ("통화", "전화", "연락"),
    "object:entry_record": ("출입 기록", "출입기록", "카드 기록"),
    "object:blackout": ("정전", "전등"),
}

# These patterns intentionally exclude emotion, sleep, hesitation, and generic
# discourse such as "다시 정리하면". They represent high-confidence case claims.
_CLAIM_PATTERNS = {
    "claim:discover": ("발견했", "발견했습니다"),
    "claim:organize_materials": ("자료를 정리", "서류를 정리", "기록을 정리"),
    "claim:drink": ("마셨", "마시지", "마신"),
    "claim:touch": ("손댔", "손대지", "손을 댔"),
    "claim:meet": ("만났", "만나지", "면담했"),
    "claim:argue": ("다퉜", "다투지", "언쟁"),
    "claim:enter": ("들어갔", "들어가지", "출입했"),
    "claim:leave": ("귀가했", "자리를 비웠", "자리 비웠", "나갔"),
    "claim:open_door": ("문을 열었", "문을 열어", "문 열었"),
    "claim:close_door": ("문을 닫았", "문을 닫아", "문 닫았"),
    "claim:door_open": ("문이 열려", "문은 열려", "문이 열린", "문은 열린"),
    "claim:door_closed": ("문이 닫혀", "문은 닫혀", "문이 닫힌", "문은 닫힌", "닫혀 있어야"),
    "claim:take_medicine": ("복용했", "투여했"),
    "claim:meeting": ("회의 후", "회의를 했", "회의했습니다"),
    "claim:instruction": ("지시사항", "지시를 받", "지시했"),
    "claim:call": ("통화했", "전화했", "연락했"),
    "claim:wait": ("기다렸",),
    "claim:move_up": ("올라갔",),
    "claim:move_down": ("내려갔",),
}

_CONCRETE_PREFIXES = ("time:", "location_claim:", "claim:")
_MIN_ANCHOR_COVERAGE = 0.4


@dataclass(frozen=True)
class GroundingCheckResult:
    checked_reply: CheckedCharacterReply
    checked: bool
    repaired: bool
    issues: list[str] = field(default_factory=list)
    missing_anchor_facts: list[str] = field(default_factory=list)
    unsupported_facts: list[str] = field(default_factory=list)
    anchor_coverage: float = 1.0

    def diagnostics(self) -> dict[str, object]:
        safety = self.checked_reply.safetyFindings
        return {
            "checked": self.checked,
            "repaired": self.repaired,
            "basis": "allowed_statement_claim",
            "repairReason": safety.get("blockedReason") if self.repaired else None,
            "finalTextSource": safety.get("finalTextSource") or "provider",
            "issues": self.issues,
            "missingAnchorFacts": self.missing_anchor_facts,
            "unsupportedFacts": self.unsupported_facts,
            "anchorCoverage": round(self.anchor_coverage, 3),
        }


def _time_atoms(text: str) -> set[str]:
    atoms: set[str] = set()
    normalized = normalize_text(text)
    for match in _TIME_PATTERN.finditer(normalized):
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        prefix = normalized[max(0, match.start() - 4) : match.start()]
        if hour < 12 and any(term in prefix for term in ("밤", "저녁", "오후")):
            hour += 12
        atoms.add(f"time:{hour:02d}:{minute:02d}")
    return atoms


def _pattern_atoms(text: str, patterns: dict[str, tuple[str, ...]]) -> set[str]:
    normalized = normalize_text(text)
    return {
        atom
        for atom, candidates in patterns.items()
        if any(candidate in normalized for candidate in candidates)
    }


def _location_claim_atoms(text: str) -> set[str]:
    normalized = normalize_text(text)
    atoms: set[str] = set()
    for location_atom, candidates in _LOCATION_PATTERNS.items():
        for candidate in candidates:
            for match in re.finditer(rf"{re.escape(candidate)}(?:에|에서|로|으로)", normalized):
                tail = normalized[match.end() : match.end() + 24]
                if _LOCATION_ASSERTION_PATTERN.search(tail):
                    atoms.add(location_atom.replace("location:", "location_claim:", 1))
                    break
            if location_atom.replace("location:", "location_claim:", 1) in atoms:
                break
    return atoms


def _fact_atoms(text: str, *, include_negation: bool = True) -> set[str]:
    atoms = {
        *_time_atoms(text),
        *_pattern_atoms(text, _LOCATION_PATTERNS),
        *_location_claim_atoms(text),
        *_pattern_atoms(text, _OBJECT_PATTERNS),
        *_pattern_atoms(text, _CLAIM_PATTERNS),
    }
    if include_negation and _NEGATION_PATTERN.search(normalize_text(text)):
        atoms.add("polarity:negative")
    return atoms


def _allowed_fact_text(payload: DialogueRequest) -> str:
    source_facts = getattr(payload.allowedStatement, "sourceFacts", None) or []
    safe_source_facts = source_facts if isinstance(source_facts, list) else []
    return " ".join([payload.allowedStatement.text, *(str(item) for item in safe_source_facts)])


def _question_required_facts(question: str, anchor_atoms: set[str]) -> set[str]:
    normalized = normalize_text(question)
    question_atoms = _fact_atoms(question, include_negation=False)
    required: set[str] = set()

    if "언제" in normalized or "몇 시" in normalized or "몇시" in normalized:
        required.update(atom for atom in anchor_atoms if atom.startswith("time:"))
    if any(term in normalized for term in ("어디", "장소", "동선", "행적")):
        required.update(atom for atom in anchor_atoms if atom.startswith("location_claim:"))

    required.update(
        atom
        for atom in anchor_atoms & question_atoms
        if atom.startswith(("object:", "claim:"))
    )
    if "polarity:negative" in anchor_atoms and any(atom.startswith("object:") for atom in required):
        required.add("polarity:negative")
    return required


def _coverage(anchor_atoms: set[str], answer_atoms: set[str]) -> float:
    if not anchor_atoms:
        return 1.0
    return len(anchor_atoms & answer_atoms) / len(anchor_atoms)


def _should_check(
    payload: DialogueRequest,
    plan: DialogueDirectorPlan | None,
    checked_reply: CheckedCharacterReply,
) -> bool:
    if checked_reply.degraded or not checked_reply.finalText.strip():
        return False
    if payload.dialogueMode in {"small_talk", "unmatched"}:
        return False
    if plan and plan.seedText:
        return False
    refs = payload.allowedStatement.sourceRefs
    policy = payload.allowedEventPolicy
    return bool(
        refs.statementIds
        or refs.evidenceIds
        or refs.timelineIds
        or refs.questionIds
        or refs.contradictionIds
        or getattr(payload.allowedStatement, "sourceFacts", None)
        or policy.relatedStatementIds
        or policy.relatedQuestionIds
        or policy.relatedEvidenceIds
        or policy.relatedTimelineEventIds
        or policy.relatedContradictionIds
    )


class GroundingCheckAgent:
    """Validate final dialogue against the allowed claim, not hidden truth."""

    def run(
        self,
        payload: DialogueRequest,
        checked_reply: CheckedCharacterReply,
        plan: DialogueDirectorPlan | None = None,
    ) -> GroundingCheckResult:
        if not _should_check(payload, plan, checked_reply):
            return GroundingCheckResult(checked_reply=checked_reply, checked=False, repaired=False)

        allowed_text = _allowed_fact_text(payload)
        anchor_atoms = _fact_atoms(allowed_text)
        answer_atoms = _fact_atoms(checked_reply.finalText)
        allowed_atoms = anchor_atoms

        concrete_answer_atoms = {
            atom for atom in answer_atoms if atom.startswith(_CONCRETE_PREFIXES)
        }
        unsupported = sorted(concrete_answer_atoms - allowed_atoms)
        required = _question_required_facts(payload.question.text, anchor_atoms)
        missing = sorted(required - answer_atoms)
        coverage = _coverage(anchor_atoms, answer_atoms)

        issues: list[str] = []
        if unsupported:
            issues.append("unsupported_concrete_claim")
        if missing:
            issues.append("required_anchor_claim_missing")
        if anchor_atoms and coverage < _MIN_ANCHOR_COVERAGE:
            issues.append("anchor_claim_coverage_too_low")
            missing = sorted(set(missing) | (anchor_atoms - answer_atoms))

        if not issues:
            return GroundingCheckResult(
                checked_reply=checked_reply,
                checked=True,
                repaired=False,
                anchor_coverage=coverage,
            )

        safe_seed = payload.allowedStatement.text.strip()
        safety = {
            **checked_reply.safetyFindings,
            "repaired": True,
            "blocked": False,
            "blockedReason": "claim_grounding_repaired",
            "providerDraftRepaired": True,
            "providerDraftBlockedReason": "claim_grounding_repaired",
            "finalTextSource": "public_seed_after_claim_grounding",
            "groundingIssues": issues,
            "groundingMissingAnchorFacts": missing,
            "groundingUnsupportedFacts": unsupported,
            "groundingAnchorCoverage": round(coverage, 3),
        }
        repaired_reply = checked_reply.model_copy(
            update={
                "finalText": safe_seed,
                "repairedText": safe_seed,
                "blockedText": checked_reply.finalText,
                "repaired": True,
                "blocked": False,
                "blockedReason": "claim_grounding_repaired",
                "safetyFindings": safety,
            }
        )
        return GroundingCheckResult(
            checked_reply=repaired_reply,
            checked=True,
            repaired=True,
            issues=issues,
            missing_anchor_facts=missing,
            unsupported_facts=unsupported,
            anchor_coverage=coverage,
        )
