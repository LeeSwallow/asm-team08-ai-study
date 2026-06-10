from __future__ import annotations

import logging
import re

from app.ai_engine.core.config import settings
from app.ai_engine.core.dialogue_guard import guard_dialogue_text
from app.ai_engine.core.text_normalization import normalize_text
from app.ai_engine.core.llm import ChainedLLM, get_llm
from app.ai_engine.prompts.rule_check_builder import build_rule_check_regen_prompt
from app.ai_engine.schemas.agents import CheckedCharacterReply, LightRuleCheckInput
from app.ai_engine.schemas.prompts import PromptInput

logger = logging.getLogger(__name__)

# 분위기를 깨는 패턴 (영어 정중 표현, 챗봇 투 등)
_ATMOSPHERE_BREAK_PATTERNS = re.compile(
    r"\b(sure|okay|ok|of course|certainly|i understand|i'll help|hello there|got it)\b"
    r"|죄송합니다만, 저는 AI|저는 언어 모델|도움을 드리기|지원해 드리기",
    re.IGNORECASE,
)
_SCRIPT_DIRECTION_PATTERNS = re.compile(r"\([^)]{1,50}\)|（[^）]{1,50}）|\[[^\]]{1,50}\]")
_VULGAR_STYLE_PATTERNS = re.compile(r"처먹|쳐먹|꺼져|닥쳐|새끼|년놈")
_HARD_QUALITY_ISSUES = {
    "self_third_person",
    "script_direction",
    "atmosphere_break",
    "forbidden_style_token",
    "forbidden_answer_plan_phrase",
    "near_duplicate_recent_reply",
    "vulgar_style_token",
}

def _quality_issues(
    text: str,
    seed_text: str,
    agent_input: LightRuleCheckInput,
    *,
    safety_findings: dict | None = None,
) -> list[str]:
    """텍스트 품질을 평가하여 문제 코드 목록을 반환한다. 빈 목록 = 품질 양호."""
    issues: list[str] = []
    safety_findings = safety_findings or {}
    if safety_findings.get("repaired") and safety_findings.get("blockedReason") == "case_fact_scope_repaired":
        issues.append("case_fact_scope_repaired")

    # 텍스트가 너무 짧음 (seed 이하)
    if len(text.strip()) < max(20, len(seed_text.strip()) // 2):
        issues.append("too_short")

    # LLM이 seed를 그대로 반환 (아무것도 추가하지 않음)
    if normalize_text(text) == normalize_text(seed_text):
        issues.append("seed_verbatim")

    # 캐릭터 말투 습관(tic/prefix)이 있는데 응답에 전혀 없음
    voice = getattr(agent_input.draft, "voice", {}) or {}
    speech_style = voice.get("speechStyle") or {}
    avoid = speech_style.get("avoid") or speech_style.get("avoidPhrases") or []
    if isinstance(avoid, list):
        hard_avoid_terms = [str(item).strip() for item in avoid if str(item or "").strip()]
        if any(term and term in text for term in hard_avoid_terms):
            issues.append("forbidden_style_token")
    tic = str(speech_style.get("tic") or speech_style.get("prefix") or "").strip()
    if tic and len(tic) <= 24 and tic not in text:
        # intent가 greeting/unmatched가 아닌 경우에만
        intent = agent_input.intent or ""
        if intent not in {"greeting", "unmatched"}:
            issues.append("no_style_tic")

    # 게임 분위기 파괴 표현 감지
    if _ATMOSPHERE_BREAK_PATTERNS.search(text):
        issues.append("atmosphere_break")
    if _SCRIPT_DIRECTION_PATTERNS.search(text):
        issues.append("script_direction")
    if _VULGAR_STYLE_PATTERNS.search(text):
        issues.append("vulgar_style_token")

    plan = agent_input.dialogueDirectorPlan
    answer_plan = dict(plan.answerPlan) if plan and plan.answerPlan else {}
    forbidden_surface_phrases = [
        str(item).strip()
        for item in (answer_plan.get("forbiddenSurfacePhrases") or [])
        if str(item or "").strip()
    ]
    if any(phrase in text for phrase in forbidden_surface_phrases):
        issues.append("forbidden_answer_plan_phrase")
    recent_dialogue = answer_plan.get("recentDialogue") or []
    if isinstance(recent_dialogue, list):
        normalized_text = normalize_text(text)
        for item in recent_dialogue[-6:]:
            prior = item.get("text") if isinstance(item, dict) else None
            if not isinstance(prior, str) or not prior.strip():
                continue
            normalized_prior = normalize_text(prior)
            if normalized_prior == normalized_text:
                issues.append("near_duplicate_recent_reply")
                break
            if len(normalized_text) >= 18 and (
                normalized_text in normalized_prior or normalized_prior in normalized_text
            ):
                issues.append("near_duplicate_recent_reply")
                break

    if plan and plan.strategy == "answer_requested_relationship_only":
        normalized_text = normalize_text(text)
        normalized_seed = normalize_text(seed_text)
        unsupported_relation_terms = ("사업", "눌러앉", "그날 밤", "따로 만난", "동선", "범행", "갈등")
        required_relation_terms = [term for term in ("삼촌", "부모", "도움") if term in normalized_seed]
        missing_required = required_relation_terms and not all(term in normalized_text for term in required_relation_terms[:2])
        if missing_required or any(term in normalized_text and term not in normalized_seed for term in unsupported_relation_terms):
            issues.append("relationship_scope_drift")

    suspect_name = str(getattr(agent_input, "suspectName", "") or "").strip()
    if suspect_name:
        given_name = suspect_name[1:] if len(suspect_name) >= 3 else suspect_name
        third_person_terms = [suspect_name]
        if given_name:
            third_person_terms.extend(
                [
                    f"{given_name} 누나",
                    f"{given_name} 형",
                    f"{given_name} 씨",
                    f"{given_name}님",
                    f"{given_name}은",
                    f"{given_name}는",
                    f"{given_name}이",
                    f"{given_name}가",
                    f"{given_name}의",
                ]
            )
        if any(term and term in text for term in third_person_terms):
            issues.append("self_third_person")

    return issues




class LightRuleCheck:
    """Chaining quality filter: 보안 검사 + 분위기/캐릭터 품질 평가 + LLM 재생성."""

    def run(self, agent_input: LightRuleCheckInput) -> CheckedCharacterReply:
        draft_text = agent_input.draft.draftText

        # ── Phase 1: 보안 검사 (항상 실행, 재생성 후에도 반드시 통과해야 함) ──
        checked = self._security_check(agent_input, draft_text)

        # provider 장애나 완전 차단인 경우 즉시 반환
        if agent_input.draft.degraded or (checked.blocked and not checked.repaired):
            return checked

        seed_approx = (
            agent_input.generatedSeed.strip()
            if agent_input.generatedSeed
            else agent_input.dialogueDirectorPlan.seedText.strip()
            if agent_input.dialogueDirectorPlan and agent_input.dialogueDirectorPlan.seedText
            else agent_input.allowedStatement.text.strip()
        )
        voice = getattr(agent_input.draft, "voice", {}) or {}
        speech_style = voice.get("speechStyle") or {}
        tic = str(speech_style.get("tic") or speech_style.get("prefix") or "").strip()
        if tic and not seed_approx.startswith(tic):
            seed_approx = f"{tic} {seed_approx}".strip()

        preflight_issues = _quality_issues(
            checked.finalText,
            seed_approx,
            agent_input,
            safety_findings=checked.safetyFindings,
        )
        if (
            agent_input.dialogueDirectorPlan
            and agent_input.dialogueDirectorPlan.strategy
            in {
                "defensive_pressure",
                "deflect_unmatched",
                "deflect_irrelevant",
                "reject_false_premise",
                "challenge_player_contradiction",
                "react_to_valid_pressure",
                "ask_clarification",
                "refuse_meta_or_private",
            }
            and "seed_verbatim" not in preflight_issues
            and not (_HARD_QUALITY_ISSUES & set(preflight_issues))
        ):
            return checked

        # ── Phase 2: 품질 평가 ───────────────────────────────────────────────
        issues = preflight_issues or _quality_issues(checked.finalText, seed_approx, agent_input)
        if not issues:
            return checked

        logger.info(
            "light_rule_check quality issues → regenerate",
            extra={
                "service": "backend",
                "issues": issues,
                "attempt": 0,
                "suspectId": agent_input.draft.suspectId,
            },
        )

        # ── Phase 3: LLM 재생성 루프 ────────────────────────────────────────
        best_checked = checked
        for attempt in range(settings.light_rule_check_max_regen_attempts):
            system_prompt, seed = build_rule_check_regen_prompt(agent_input, issues, seed_approx, attempt)
            regen_text = self._regenerate(system_prompt, seed, agent_input.draft.model or "")
            if regen_text is None:
                break

            regen_checked = self._security_check(agent_input, regen_text)
            new_issues = _quality_issues(regen_checked.finalText, seed_approx, agent_input)

            # 보안 통과 + 품질 개선된 경우
            if not regen_checked.blocked or regen_checked.repaired:
                quality_improved = len(new_issues) < len(issues)
                regen_safety = {
                    **regen_checked.safetyFindings,
                    "regenerated": True,
                    "regenerationAttempts": attempt + 1,
                    "qualityIssuesResolved": [i for i in issues if i not in new_issues],
                    "finalTextSource": f"regenerated_attempt_{attempt + 1}",
                }
                regen_checked = regen_checked.model_copy(update={"safetyFindings": regen_safety})

                if not new_issues or quality_improved:
                    logger.info(
                        "light_rule_check regeneration succeeded",
                        extra={
                            "service": "backend",
                            "attempt": attempt + 1,
                            "remainingIssues": new_issues,
                            "suspectId": agent_input.draft.suspectId,
                        },
                    )
                    return regen_checked

                # 아직 품질 문제가 있지만 이전보다는 나음 → best 갱신
                if quality_improved:
                    best_checked = regen_checked
                    issues = new_issues

        # 모든 재생성 시도 후에도 품질 문제 → 최선 버전 반환
        remaining_issues = _quality_issues(best_checked.finalText, seed_approx, agent_input)
        if _HARD_QUALITY_ISSUES & set(remaining_issues):
            fallback_text = _quality_fallback_text(agent_input, seed_approx)
            fallback_checked = self._security_check(agent_input, fallback_text)
            fallback_safety = {
                **fallback_checked.safetyFindings,
                "regenerated": True,
                "regenerationAttempts": settings.light_rule_check_max_regen_attempts,
                "qualityFallback": True,
                "qualityIssuesResolved": list(_HARD_QUALITY_ISSUES & set(remaining_issues)),
                "finalTextSource": "quality_fallback_after_regeneration",
            }
            return fallback_checked.model_copy(update={"safetyFindings": fallback_safety})

        logger.info(
            "light_rule_check regeneration exhausted, using best version",
            extra={
                "service": "backend",
                "attempts": settings.light_rule_check_max_regen_attempts,
                "suspectId": agent_input.draft.suspectId,
            },
        )
        return best_checked

    def _security_check(self, agent_input: LightRuleCheckInput, text: str) -> CheckedCharacterReply:
        """guard_dialogue_text를 실행하고 CheckedCharacterReply를 반환한다."""
        final_text, safety = guard_dialogue_text(
            text,
            agent_input.allowedStatement.text,
            reveal_allowed=agent_input.revealAllowed,
            enforce_statement_scope=agent_input.enforceStatementScope,
            allowed_context_terms=tuple(agent_input.allowedContextTerms),
        )
        repaired_text = final_text if safety.repaired else None
        blocked_text = text if safety.blocked_reason else None
        blocked = bool(safety.leaks_solution or safety.violates_case_facts)
        return CheckedCharacterReply(
            requestId=agent_input.requestId or agent_input.draft.requestId,
            correlationId=agent_input.correlationId or agent_input.draft.correlationId,
            suspectId=agent_input.draft.suspectId,
            finalText=final_text,
            repairedText=repaired_text,
            blockedText=blocked_text,
            repaired=safety.repaired,
            blocked=blocked,
            blockedReason=safety.blocked_reason,
            usedRefs=agent_input.draft.usedRefs,
            sourceRefs=agent_input.draft.sourceRefs,
            personaOverlayId=agent_input.draft.personaOverlayId,
            safetyFindings={
                "leaksSolution": safety.leaks_solution,
                "violatesCaseFacts": safety.violates_case_facts,
                "blockedTerms": list(safety.blocked_terms),
                "repaired": safety.repaired,
                "blocked": blocked,
                "blockedReason": safety.blocked_reason,
                "finalTextSource": "provider",
            },
            fallbackUsed=agent_input.draft.fallbackUsed,
            degraded=agent_input.draft.degraded,
            provider=agent_input.draft.provider,
            model=agent_input.draft.model,
            errorType=agent_input.draft.errorType,
        )

    def _regenerate(self, system_prompt: PromptInput, seed: str, model_hint: str) -> str | None:
        """LLM을 호출하여 재생성된 텍스트를 반환한다. 실패 시 None."""
        try:
            llm = get_llm()
            regen = llm.complete(system_prompt, seed_text=seed, max_length=200)
            if isinstance(llm, ChainedLLM) and llm.used_fallback_on_last_call:
                logger.info("light_rule_check regen used fallback provider")
            return regen if regen and regen.strip() else None
        except Exception as exc:
            logger.warning(
                "light_rule_check regen failed",
                extra={"service": "backend", "reason": type(exc).__name__},
            )
            return None


def _quality_fallback_text(agent_input: LightRuleCheckInput, seed_text: str) -> str:
    voice = getattr(agent_input.draft, "voice", {}) or {}
    speech_style = voice.get("speechStyle") or {}
    sample_lines = speech_style.get("sampleLines") or speech_style.get("samples") or []
    avoid = speech_style.get("avoid") or speech_style.get("avoidPhrases") or []
    avoid_terms = [str(item).strip() for item in avoid if str(item or "").strip()] if isinstance(avoid, list) else []
    if isinstance(sample_lines, list):
        for sample in sample_lines:
            text = str(sample or "").strip()
            if text and not any(term and term in text for term in avoid_terms):
                return text
    seed = _SCRIPT_DIRECTION_PATTERNS.sub("", seed_text).strip()
    seed = re.sub(r"\s{2,}", " ", seed)
    tone_meta = getattr(agent_input.draft, "tone", {}) or {}
    style_tone = str(tone_meta.get("styleTone") or "")
    pressure = str(tone_meta.get("pressureState") or "")
    if style_tone == "evidence_shock":
        prefix = "잠깐만요."
    elif pressure in {"pressed", "broken"}:
        prefix = "아니요."
    else:
        prefix = "그건 아닙니다."
    if not seed:
        return f"{prefix} 제가 공개적으로 말할 수 있는 건 거기까지예요."
    return f"{prefix} {seed}"
