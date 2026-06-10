from __future__ import annotations

from app.ai_engine.core.solution_guard import contains_secret
from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent
from app.ai_engine.schemas.agents import DialogueDirectorInput, DialogueDirectorPlan
from app.ai_engine.schemas.dialogue import DialogueRequest


def _safe_short_text(value: object, max_length: int = 80) -> str:
    text = " ".join(str(value or "").split())
    if contains_secret(text)[0] or any(term in text.lower() for term in ("secret", "solution", "isculprit", "secretnote")):
        return ""
    if len(text) > max_length:
        return text[: max_length - 1].rstrip() + "…"
    return text


def _append_focus_term(terms: list[str], term: str) -> None:
    compact = term.replace(" ", "")
    if not compact:
        return
    for existing in list(terms):
        existing_compact = existing.replace(" ", "")
        if compact == existing_compact or compact in existing_compact:
            return
        if existing_compact in compact:
            terms.remove(existing)
    terms.append(term)


def _join_two_korean_terms(left: str, right: str) -> str:
    last = left[-1]
    particle = "와"
    if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28:
        particle = "과"
    return f"{left}{particle} {right}"


def _mentioned_evidence_terms(payload: DialogueRequest, retrieved_context: object | None) -> list[str]:
    terms: list[str] = []
    matched_ids = set(payload.turnInterpretation.get("mentionedEvidenceIds") or [])
    matched_ids.update(payload.allowedStatement.sourceRefs.evidenceIds)
    matched_ids.update(payload.allowedEventPolicy.relatedEvidenceIds)
    if retrieved_context is not None:
        for evidence in getattr(retrieved_context, "matched_evidence", []) or []:
            evidence_id = str(evidence.get("id") or evidence.get("evidenceId") or "")
            if matched_ids and evidence_id and evidence_id not in matched_ids:
                continue
            name = _safe_short_text(evidence.get("name"), max_length=36)
            if name:
                _append_focus_term(terms, name)
    for fact in getattr(payload.allowedStatement, "sourceFacts", None) or []:
        safe_fact = _safe_short_text(fact, max_length=80)
        if safe_fact.startswith(("저는 ", "제가 ", "내가 ")):
            continue
        if ":" in safe_fact:
            evidence_name = _safe_short_text(safe_fact.split(":", 1)[0], max_length=36)
            if evidence_name:
                _append_focus_term(terms, evidence_name)
        if len(terms) >= 3:
            return terms[:3]
    for term in payload.turnInterpretation.get("focusTerms") or []:
        safe_term = _safe_short_text(term, max_length=24)
        if safe_term:
            _append_focus_term(terms, safe_term)
        if len(terms) >= 3:
            return terms
    if not terms:
        for fact in getattr(payload.allowedStatement, "sourceFacts", None) or []:
            safe_fact = _safe_short_text(fact, max_length=54)
            if safe_fact.startswith(("저는 ", "제가 ", "내가 ")):
                continue
            if safe_fact:
                _append_focus_term(terms, safe_fact)
            if len(terms) >= 3:
                break
    return terms[:3]


def _contradiction_seed(payload: DialogueRequest, focus_terms: list[str]) -> str:
    if focus_terms:
        if len(focus_terms) == 1:
            focus = focus_terms[0]
        elif len(focus_terms) == 2:
            focus = _join_two_korean_terms(focus_terms[0], focus_terms[1])
        else:
            focus = f"{focus_terms[0]}, {focus_terms[1]} 같은 단서들"
        return (
            f"{focus} 때문에 제 말이 흔들린다는 건 알겠습니다. "
            "그래도 그걸 곧바로 인정하라는 건 무리예요. "
            "제가 설명해야 할 부분이 있다는 것까지만 말하겠습니다."
        )
    return (
        "그 단서 때문에 제 말이 흔들린다는 건 알겠습니다. "
        "그래도 그걸 곧바로 인정하라는 건 무리예요. "
        "제가 설명해야 할 부분이 있다는 것까지만 말하겠습니다."
    )


def _dialogue_function(name: str, *, reason: str, **arguments: object) -> dict[str, object]:
    """Public, deterministic function transition selected before generation.

    The function call is a routing/grounding hint only: it never mutates game
    state, never reveals hidden truth, and is executed by CharacterAgent as a
    bounded dialogue move before GameMasterAgent proposes BE-validated events.
    """
    return {
        "name": name,
        "arguments": arguments,
        "transferTo": "CharacterAgent",
        "reason": reason,
    }


class DialogueDirectorAgent:
    """Deterministic turn planner that keeps pressured suspect replies safe and varied."""

    def run(self, agent_input: DialogueDirectorInput) -> DialogueDirectorPlan:
        payload = agent_input.payload
        intent = classify_dialogue_intent(payload.question.text, payload.dialogueMode)
        transition = payload.interrogationTransition or {}
        focus_terms = _mentioned_evidence_terms(payload, agent_input.retrieved_context)

        if intent == "unmatched":
            focus = focus_terms[:2]
            return DialogueDirectorPlan(
                strategy="deflect_unmatched",
                seedText=None,
                allowedAdmissionLevel="no_new_fact",
                styleDirectives=["질문을 되묻지 말고 짧게 방어하되, 같은 문장을 반복하지 않는다."],
                forbiddenClaims=["새 증거, 범행 방식, 범인 단정을 만들지 않는다."],
                focusTerms=focus,
                functionCall=_dialogue_function(
                    "deflect_unmatched_turn",
                    reason="intent_unmatched",
                    suspectName=payload.suspect.name,
                    focusTerms=focus,
                    playerMessage=payload.question.text,
                    admissionLevel="no_new_fact",
                ),
                reason="intent_unmatched",
            )

        if intent == "greeting":
            return DialogueDirectorPlan(
                strategy="small_talk_boundary",
                seedText=None,
                allowedAdmissionLevel="no_new_fact",
                styleDirectives=["인사는 받아도 사건 현장의 긴장을 유지한다.", "새 사건 사실을 만들지 않는다."],
                forbiddenClaims=["비공개 해결 정보", "새 알리바이 창작"],
                functionCall=_dialogue_function(
                    "handle_small_talk_boundary",
                    reason="intent_greeting",
                    suspectName=payload.suspect.name,
                    playerMessage=payload.question.text,
                    pressureState=payload.suspect.pressureState,
                    emotionalState=payload.suspect.emotionalState,
                ),
                reason="intent_greeting",
            )

        if transition.get("decisiveEvidence"):
            return DialogueDirectorPlan(
                strategy="defensive_pressure",
                seedText=_contradiction_seed(payload, focus_terms),
                allowedAdmissionLevel="acknowledge_conflict_only",
                styleDirectives=[
                    "증거와 진술의 충돌은 인정하되 범행, 방법, 동기는 인정하지 않는다.",
                    "플레이어에게 질문으로 되묻지 말고 2~3문장으로 답한다.",
                    "허용된 공개 사실과 언급된 단서 이름만 사용한다.",
                ],
                forbiddenClaims=[
                    "살해했다, 죽였다, 범인이다 같은 자백",
                    "비공개 동기나 비공개 범행 방법",
                    "허용되지 않은 장소 출입 인정",
                ],
                focusTerms=focus_terms,
                functionCall=_dialogue_function(
                    "acknowledge_public_contradiction",
                    reason="decisive_evidence_pressure",
                    focusTerms=focus_terms,
                    suspectName=payload.suspect.name,
                    playerMessage=payload.question.text,
                    admissionLevel="acknowledge_conflict_only",
                ),
                reason="decisive_evidence_pressure",
            )

        if transition.get("move") == "repeat_pressure":
            return DialogueDirectorPlan(
                strategy="controlled_deflection",
                seedText=None,
                allowedAdmissionLevel="public_fact_only",
                styleDirectives=["이전 답변을 그대로 반복하지 말고 공개 사실 범위에서 방어한다."],
                forbiddenClaims=["비공개 해결 정보", "범인 단정", "새 알리바이 창작"],
                focusTerms=focus_terms,
                functionCall=_dialogue_function(
                    "answer_pressure_followup",
                    reason="repeat_pressure",
                    focusTerms=focus_terms,
                    suspectName=payload.suspect.name,
                    playerMessage=payload.question.text,
                    admissionLevel="public_fact_only",
                ),
                reason="repeat_pressure",
            )

        return DialogueDirectorPlan(
            strategy="answer_public_fact",
            seedText=None,
            allowedAdmissionLevel="public_fact_only",
            styleDirectives=["공개 사실을 벗어나지 않는다."],
            forbiddenClaims=["비공개 해결 정보", "범인 단정"],
            focusTerms=focus_terms,
            functionCall=_dialogue_function(
                "answer_public_fact",
                reason="default",
                focusTerms=focus_terms,
                suspectName=payload.suspect.name,
                playerMessage=payload.question.text,
                admissionLevel="public_fact_only",
            ),
            reason="default",
        )
