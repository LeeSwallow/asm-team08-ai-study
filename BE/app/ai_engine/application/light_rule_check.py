from __future__ import annotations

import logging
import re

from app.ai_engine.application.dialogue_director_agent import DIRECTOR_SEED_STRATEGIES, NO_NEW_FACT_STRATEGIES
from app.ai_engine.core.guard import guard_dialogue_text, normalize_text
from app.ai_engine.core.llm import ChainedLLM, get_llm
from app.ai_engine.schemas.agents import CheckedCharacterReply, LightRuleCheckInput

logger = logging.getLogger(__name__)

# 재생성을 최대 2번까지 시도한다
_MAX_REGEN_ATTEMPTS = 2

# 분위기를 깨는 패턴 (영어 정중 표현, 챗봇 투 등)
_ATMOSPHERE_BREAK_PATTERNS = re.compile(
    r"\b(sure|okay|ok|of course|certainly|i understand|i'll help|hello there|got it)\b"
    r"|죄송합니다만, 저는 AI|저는 언어 모델|도움을 드리기|지원해 드리기",
    re.IGNORECASE,
)
_SCRIPT_DIRECTION_PATTERNS = re.compile(r"\([^)]{1,50}\)|（[^）]{1,50}）|\[[^\]]{1,50}\]")
_HARD_QUALITY_ISSUES = {"self_third_person", "script_direction", "atmosphere_break"}

def _quality_issues(
    text: str,
    seed_text: str,
    agent_input: LightRuleCheckInput,
) -> list[str]:
    """텍스트 품질을 평가하여 문제 코드 목록을 반환한다. 빈 목록 = 품질 양호."""
    issues: list[str] = []

    # 텍스트가 너무 짧음 (seed 이하)
    if len(text.strip()) < max(20, len(seed_text.strip()) // 2):
        issues.append("too_short")

    # LLM이 seed를 그대로 반환 (아무것도 추가하지 않음)
    if normalize_text(text) == normalize_text(seed_text):
        issues.append("seed_verbatim")

    # 캐릭터 말투 습관(tic/prefix)이 있는데 응답에 전혀 없음
    voice = getattr(agent_input.draft, "voice", {}) or {}
    speech_style = voice.get("speechStyle") or {}
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


def _build_regen_prompt(
    agent_input: LightRuleCheckInput,
    issues: list[str],
    seed_text: str,
    attempt: int,
) -> tuple[str, str]:
    """재생성 시스템 프롬프트와 seed를 반환한다."""
    pack = agent_input.characterKnowledgePack
    draft = agent_input.draft

    # 캐릭터 정보
    voice = getattr(draft, "voice", {}) or {}
    speech_style = voice.get("speechStyle") or {}
    tic = str(speech_style.get("tic") or speech_style.get("prefix") or "").strip()
    vocab = speech_style.get("vocabulary") or []
    if isinstance(vocab, list):
        vocab_str = ", ".join(str(v) for v in vocab[:3])
    else:
        vocab_str = ""

    tone_meta = getattr(draft, "tone", {}) or {}
    persona_meta = getattr(draft, "persona", {}) or {}
    base_persona = str(persona_meta.get("basePersona") or "").strip()
    if len(base_persona) > 80:
        base_persona = base_persona[:79] + "…"

    # 품질 실패 이유 (한국어)
    issue_map = {
        "too_short": "답변이 너무 짧고 불완전합니다.",
        "seed_verbatim": "LLM이 기본 텍스트를 그대로 반환했습니다. 캐릭터의 목소리로 자연스럽게 다시 표현해야 합니다.",
        "no_style_tic": f"캐릭터의 말투 습관({tic})이 응답에 없습니다. 자연스럽게 포함하세요.",
        "atmosphere_break": "응답이 탐정 누아르 분위기를 벗어났습니다. 용의자 심문 맥락으로 유지하세요.",
        "self_third_person": "용의자가 자기 자신을 제3자나 가족 호칭으로 불렀습니다. 반드시 1인칭으로 말해야 합니다.",
        "script_direction": "괄호 지문이나 대본식 행동 묘사가 섞였습니다. 말풍선 대사만 남겨야 합니다.",
    }
    fail_reasons = "\n".join(f"- {issue_map.get(i, i)}" for i in issues)

    # 관련 맥락 요약 (retrieved_context가 있는 경우)
    context_lines: list[str] = []
    retrieved = getattr(agent_input, "retrieved_context", None)
    if retrieved and not retrieved.is_empty():
        if retrieved.matched_timeline_events:
            for ev in retrieved.matched_timeline_events[:2]:
                context_lines.append(f"- 공개 타임라인: {ev.get('time', '')} {ev.get('title', '')}")
        if retrieved.matched_evidence:
            for ev in retrieved.matched_evidence[:2]:
                context_lines.append(f"- 언급된 증거: {ev.get('name', '')} — {ev.get('description', '')[:60]}")
        if retrieved.matched_statements:
            for st in retrieved.matched_statements[:1]:
                context_lines.append(f"- 관련 진술: {st.get('text', '')[:80]}")

    context_block = "\n".join(context_lines) if context_lines else "(없음)"
    source_facts = getattr(agent_input.allowedStatement, "sourceFacts", None) or []
    if isinstance(source_facts, list):
        source_fact_lines = [f"- 공개 사실: {str(item)[:100]}" for item in source_facts[:3] if str(item or "").strip()]
        if source_fact_lines:
            context_block = "\n".join([context_block, *source_fact_lines]) if context_block != "(없음)" else "\n".join(source_fact_lines)
    tic_directive = f"말투 습관: {tic}" if tic else ""
    vocab_directive = f"주요 어휘: {vocab_str}" if vocab_str else ""
    style_directives = "\n".join(d for d in [tic_directive, vocab_directive] if d) or "(기본 스타일)"
    tension = tone_meta.get("tensionLevel", "normal")
    pressure = tone_meta.get("pressureState", "normal")

    system = f"""당신은 탐정 누아르 추리 게임의 용의자입니다.
이전 답변에 다음 문제가 있었습니다:
{fail_reasons}

캐릭터 정보:
- 이름: {getattr(agent_input, "suspectName", None) or "(미지정)"}
- 페르소나: {base_persona or '(미지정)'}
- {style_directives}
- 긴장 수준: {tension}, 압박 상태: {pressure}

공개 맥락:
{context_block}

허용된 공개 사실을 벗어나지 말고, 용의자가 심문 중 직접 말하는 대사로 다시 답하세요.
자기 이름을 제3자처럼 말하지 말고, 증거 소유자를 공개 사실 없이 새로 만들지 마세요.
재시도: {attempt + 1}"""

    return system, seed_text


class LightRuleCheck:
    """Chaining quality filter: 보안 검사 + 분위기/캐릭터 품질 평가 + LLM 재생성."""

    def run(self, agent_input: LightRuleCheckInput) -> CheckedCharacterReply:
        draft_text = agent_input.draft.draftText

        # ── Phase 1: 보안 검사 (항상 실행, 재생성 후에도 반드시 통과해야 함) ──
        checked = self._security_check(agent_input, draft_text)

        director_plan = agent_input.dialogueDirectorPlan
        if director_plan and director_plan.strategy in NO_NEW_FACT_STRATEGIES and director_plan.seedText:
            safe_seed = self._security_check(agent_input, director_plan.seedText)
            if normalize_text(checked.finalText) != normalize_text(safe_seed.finalText):
                safety = {
                    **safe_seed.safetyFindings,
                    "repaired": True,
                    "blocked": False,
                    "blockedReason": "no_new_fact_scope_repaired",
                    "providerDraftRepaired": True,
                    "providerDraftBlockedReason": "no_new_fact_scope_repaired",
                    "finalTextSource": "dialogue_director_no_new_fact_seed",
                }
                return safe_seed.model_copy(
                    update={
                        "repaired": True,
                        "blocked": False,
                        "blockedReason": "no_new_fact_scope_repaired",
                        "repairedText": safe_seed.finalText,
                        "blockedText": draft_text,
                        "safetyFindings": safety,
                    }
                )
            safety = {
                **checked.safetyFindings,
                "finalTextSource": "dialogue_director_no_new_fact_seed",
            }
            return checked.model_copy(update={"safetyFindings": safety})

        # provider 장애나 완전 차단인 경우 즉시 반환
        if agent_input.draft.degraded or (checked.blocked and not checked.repaired):
            return checked

        if (
            director_plan
            and director_plan.strategy in DIRECTOR_SEED_STRATEGIES
        ):
            return checked

        # ── Phase 2: 품질 평가 ───────────────────────────────────────────────
        # seed_text를 재구성하기 위해 voice metadata 활용
        voice = getattr(agent_input.draft, "voice", {}) or {}
        speech_style = voice.get("speechStyle") or {}
        tic = str(speech_style.get("tic") or speech_style.get("prefix") or "").strip()
        seed_approx = (
            agent_input.dialogueDirectorPlan.seedText.strip()
            if agent_input.dialogueDirectorPlan and agent_input.dialogueDirectorPlan.seedText
            else agent_input.allowedStatement.text.strip()
        )
        if tic and not seed_approx.startswith(tic):
            seed_approx = f"{tic} {seed_approx}".strip()

        issues = _quality_issues(checked.finalText, seed_approx, agent_input)
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
        for attempt in range(_MAX_REGEN_ATTEMPTS):
            system_prompt, seed = _build_regen_prompt(agent_input, issues, seed_approx, attempt)
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
                "regenerationAttempts": _MAX_REGEN_ATTEMPTS,
                "qualityFallback": True,
                "qualityIssuesResolved": list(_HARD_QUALITY_ISSUES & set(remaining_issues)),
                "finalTextSource": "quality_fallback_after_regeneration",
            }
            return fallback_checked.model_copy(update={"safetyFindings": fallback_safety})

        logger.info(
            "light_rule_check regeneration exhausted, using best version",
            extra={
                "service": "backend",
                "attempts": _MAX_REGEN_ATTEMPTS,
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

    def _regenerate(self, system_prompt: str, seed: str, model_hint: str) -> str | None:
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
