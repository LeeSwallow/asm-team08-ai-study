from __future__ import annotations

import json
from pathlib import Path

from app.ai_engine.agents.character_agent import build_character_agent_input, render_dialogue_seed
from app.ai_engine.agents.dialogue_director_agent import DialogueDirectorAgent
from app.ai_engine.prompts.character_dialogue_builder import build_character_dialogue_prompt
from app.ai_engine.prompts.rule_check_builder import build_rule_check_regen_prompt
from app.ai_engine.schemas.agents import DialogueDirectorInput, DialogueDirectorPlan, DraftCharacterReply, LightRuleCheckInput
from app.ai_engine.schemas.dialogue import DialogueRequest


def _request(
    *,
    suspect_id: str = "char_yoonjaeho",
    suspect_name: str = "윤재호",
    message: str = "갑자기 춤춰봐요.",
    mode: str | None = "unmatched",
    tension_level: str = "low",
    pressure_state: str = "calm",
    emotional_state: str = "neutral",
    tension_score: int = 10,
) -> DialogueRequest:
    return DialogueRequest.model_validate(
        {
            "requestId": "req_seed_quality",
            "sessionId": "sess_seed_quality",
            "caseId": "case_001",
            "dialogueMode": mode,
            "suspect": {
                "id": suspect_id,
                "name": suspect_name,
                "pressureState": pressure_state,
                "emotionalState": emotional_state,
                "tensionLevel": tension_level,
                "tensionScore": tension_score,
                "publicPersona": "오래된 저택의 집사. 정중하지만 불편한 질문에는 말끝이 짧아진다.",
                "speechStyle": {
                    "vocabulary": ["회장님", "제가 기억하기론"],
                    "tone": "formal",
                    "sentenceRhythm": "짧은 구어체. 보고하듯 길게 정리하지 말고, 숨기는 사람처럼 한 박자 늦게 답한다.",
                    "avoid": ["말씀드리자면", "확인하건대"],
                    "sampleLines": ["그건 제가 본 범위 밖입니다.", "회장님 일이라 조심스러울 뿐입니다."],
                },
            },
            "question": {"id": "player_seed_quality", "text": message},
            "allowedStatement": {
                "id": "st_choiyuna_no_wine",
                "text": "네, 저는 그날 와인을 마시지 않았습니다. 립스틱 색도 제 것이 아닙니다.",
                "sourceRefs": {
                    "statementIds": ["st_choiyuna_no_wine"],
                    "evidenceIds": ["ev_wine_glass"],
                    "timelineIds": [],
                },
            },
            "allowedEventPolicy": {
                "relatedStatementIds": ["st_choiyuna_no_wine"],
                "relatedEvidenceIds": ["ev_wine_glass"],
            },
            "characterKnowledgePack": {
                "publicPersona": "오래된 저택의 집사. 정중하지만 불편한 질문에는 말끝이 짧아진다.",
                "speechStyle": {
                    "vocabulary": ["회장님", "제가 기억하기론"],
                    "tone": "formal",
                    "sentenceRhythm": "짧은 구어체. 보고하듯 길게 정리하지 말고, 숨기는 사람처럼 한 박자 늦게 답한다.",
                    "avoid": ["말씀드리자면", "확인하건대"],
                    "sampleLines": ["그건 제가 본 범위 밖입니다.", "회장님 일이라 조심스러울 뿐입니다."],
                },
                "personaVariants": [
                    {
                        "id": "pv_low",
                        "tensionLevels": ["low"],
                        "overlay": {
                            "tone": "controlled",
                            "voice": "예의를 유지하지만 짧게 선을 긋는다.",
                            "styleDirectives": ["한 문장", "정중한 거리감"],
                        },
                    },
                    {
                        "id": "pv_critical",
                        "tensionLevels": ["critical"],
                        "pressureStates": ["broken"],
                        "overlay": {
                            "tone": "frayed",
                            "voice": "숨을 고르고 말끝이 흔들리며, 예의보다 방어가 먼저 나온다.",
                            "styleDirectives": ["짧은 호흡", "감정 균열", "반복 금지"],
                        },
                    },
                ],
            },
            "style": {"tone": "tense", "maxLength": 220},
            "revealAllowed": False,
        }
    )


def test_unmatched_seed_does_not_drag_evidence_context_into_off_topic_deflection() -> None:
    payload = _request(message="갑자기 춤춰봐요.", mode="unmatched")
    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))
    seed = render_dialogue_seed(payload, plan)

    assert plan.strategy == "deflect_unmatched"
    assert "와인" not in seed
    assert "립스틱" not in seed
    assert "상황" in seed or "사건" in seed or "말씀" in seed


def test_tension_overlay_changes_seed_emotional_line_without_new_rules() -> None:
    low = _request(tension_level="low", pressure_state="calm", emotional_state="neutral", tension_score=10)
    critical = _request(tension_level="critical", pressure_state="broken", emotional_state="shaken", tension_score=95)

    low_seed = render_dialogue_seed(low, DialogueDirectorAgent().run(DialogueDirectorInput(payload=low)))
    critical_seed = render_dialogue_seed(critical, DialogueDirectorAgent().run(DialogueDirectorInput(payload=critical)))

    assert low_seed != critical_seed
    assert any(marker in critical_seed for marker in ("장난", "사건 얘기", "답하지 않", "농담", "요청"))


def test_character_groups_use_distinct_low_tension_deflection_seeds() -> None:
    samples = {
        name: render_dialogue_seed(
            _request(suspect_id=suspect_id, suspect_name=name, message="갑자기 춤춰봐요.", mode="unmatched"),
            DialogueDirectorAgent().run(
                DialogueDirectorInput(
                    payload=_request(suspect_id=suspect_id, suspect_name=name, message="갑자기 춤춰봐요.", mode="unmatched")
                )
            ),
        )
        for suspect_id, name in [
            ("char_hanseoyeon", "한서연"),
            ("char_yoonjaeho", "윤재호"),
            ("char_parkmingyu", "박민규"),
            ("char_choiyuna", "최윤아"),
        ]
    }

    assert len(set(samples.values())) == 4
    assert "장난" in samples["한서연"] or "똑바로" in samples["한서연"] or "이상한 소리" in samples["한서연"]
    assert "말씀" in samples["윤재호"] or "상황" in samples["윤재호"]
    assert "농담" in samples["박민규"] or "말장난" in samples["박민규"]
    assert "요청" in samples["최윤아"] or "필요한 질문" in samples["최윤아"]


def test_hanseoyeon_seed_and_prompt_preserve_informal_speech_style() -> None:
    base_payload = _request(
        suspect_id="char_hanseoyeon",
        suspect_name="한서연",
        message="갑자기 춤춰봐요.",
        mode="unmatched",
    )
    base_pack = base_payload.characterKnowledgePack
    assert base_pack is not None
    banmal_style = {
        "register": "informal_banmal",
        "addressStyle": "탐정에게 존댓말하지 말고 반말한다. 다만 비속어는 쓰지 않는다.",
        "vocabulary": ["아니", "그게", "그냥", "웃기네"],
        "sampleLines": ["아니, 그걸 왜 나한테 물어?", "그냥 내 방에 있었다니까."],
        "avoid": ["습니다", "습니까", "말씀드리자면"],
    }
    payload = base_payload.model_copy(
        update={
            "suspect": base_payload.suspect.model_copy(
                update={
                    "publicPersona": "돈과 가족 이야기가 나오면 날카롭게 반말로 쏘아붙이는 조카",
                    "speechStyle": banmal_style,
                }
            ),
            "characterKnowledgePack": base_pack.model_copy(
                update={
                    "publicPersona": "돈과 가족 이야기가 나오면 날카롭게 반말로 쏘아붙이는 조카",
                    "speechStyle": banmal_style,
                }
            ),
        }
    )
    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))
    seed = render_dialogue_seed(payload, plan)
    prompt = build_character_dialogue_prompt(payload, None, plan)
    rendered = str(prompt.model_dump())

    assert any(marker in seed for marker in ("장난", "이상한 소리", "똑바로", "말 안 해"))
    assert "습니다" not in seed
    assert "반말" in rendered
    assert "존댓말하지 말고" in rendered


def test_character_prompt_names_state_specific_emotional_shift_and_human_voice() -> None:
    payload = _request(tension_level="critical", pressure_state="broken", emotional_state="shaken", tension_score=95)
    agent_input = build_character_agent_input(
        payload,
        DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload)),
    )
    prompt = build_character_dialogue_prompt(payload, None, agent_input.dialogueDirectorPlan)
    rendered = str(prompt.model_dump())

    assert "state behavior" in rendered
    assert "sentence rhythm" in rendered
    assert "sample lines" in rendered
    assert "말씀드리자면" in rendered
    assert "짧은 호흡" in rendered
    assert "보고서" in rendered
    assert "사람" in rendered or "구어체" in rendered


def _payload_with_active_overlay_for_seed(
    *,
    mode: str,
    transition: dict | None = None,
) -> DialogueRequest:
    payload = _request(
        suspect_id="char_custom",
        suspect_name="강테스트",
        message="계속 숨기지 말고 말해.",
        mode=mode,
        tension_level="critical",
        pressure_state="broken",
        emotional_state="breakdown",
        tension_score=95,
    )
    base_pack = payload.characterKnowledgePack
    assert base_pack is not None
    return payload.model_copy(
        update={
            "interrogationTransition": transition or {},
            "characterKnowledgePack": base_pack.model_copy(
                update={
                    "activePersonaOverlay": {
                        "id": "custom_breakdown",
                        "tone": "fractured",
                        "voice": "손을 계속 문지르고 숨을 고르며 짧게 끊어 말한다.",
                        "speechStyle": {
                            "sampleLines": [
                                "손이 떨려요. 숨긴 게 있다는 말까지만 하겠습니다.",
                                "잠깐만요, 더 몰면 제가 무너집니다.",
                            ],
                            "avoid": ["정리해서 말씀드리면"],
                        },
                    }
                }
            ),
        }
    )


def test_pressure_followup_seed_does_not_copy_active_persona_overlay_samples() -> None:
    payload = _payload_with_active_overlay_for_seed(mode="pressure_followup")
    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))
    seed = render_dialogue_seed(payload, plan)

    assert seed not in {
        "손이 떨려요. 숨긴 게 있다는 말까지만 하겠습니다.",
        "잠깐만요, 더 몰면 제가 무너집니다.",
    }
    assert "압박" in seed or "의심" in seed


def test_decisive_evidence_seed_does_not_copy_active_persona_overlay_samples() -> None:
    payload = _payload_with_active_overlay_for_seed(mode="evidence_question", transition={"decisiveEvidence": True})
    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))
    seed = render_dialogue_seed(payload, plan)

    assert seed not in {
        "손이 떨려요. 숨긴 게 있다는 말까지만 하겠습니다.",
        "잠깐만요, 더 몰면 제가 무너집니다.",
    }
    assert "단서" in seed or "인정" in seed


def test_case001_each_suspect_has_distinct_emotional_voice_samples_per_tension_stage() -> None:
    case = json.loads(Path("data/cases/case_001.json").read_text(encoding="utf-8"))
    for suspect in case["suspects"]:
        variants = suspect.get("personaVariants") or []
        samples_by_band: dict[str, tuple[str, ...]] = {}
        for variant in variants:
            levels = tuple(variant.get("tensionLevels") or [])
            sample_lines = tuple(((variant.get("overlay") or {}).get("speechStyle") or {}).get("sampleLines") or [])
            for level in levels:
                samples_by_band[level] = sample_lines
        for level in ("low", "medium", "high", "critical"):
            assert level in samples_by_band, f"{suspect['characterId']} missing {level} persona samples"
            assert samples_by_band[level], f"{suspect['characterId']} {level} has no sampleLines"
        assert len({samples_by_band[level] for level in ("low", "medium", "high", "critical")}) == 4, suspect["characterId"]


def test_character_prompt_anchors_final_generation_to_player_question() -> None:
    payload = _request(message="22시 이후 어디에 있었나요?", mode="normal")
    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))
    prompt = build_character_dialogue_prompt(payload, None, plan)
    rendered = str(prompt.model_dump())

    assert "Player Turn" in rendered
    assert "22시 이후 어디에 있었나요?" in rendered
    assert "사용자의 이번 발화에 직접 반응" in rendered
    assert "공개 사실 범위" in rendered


def test_character_prompt_includes_dialogue_history_as_structured_turns() -> None:
    base = _request(message="그 얘기 또 피하지 말고요.", mode="pressure_followup")
    pack = base.characterKnowledgePack
    assert pack is not None
    payload = base.model_copy(
        update={
            "characterKnowledgePack": pack.model_copy(
                update={
                    "recentDialogue": [
                        {"speaker": "player", "text": "22시 이후 어디 있었죠?", "questionId": "q_where_2200"},
                        {"speaker": "suspect", "text": "제 방에 있었습니다.", "statementId": "st_room_2200"},
                        {"speaker": "player", "text": "출입 기록엔 서재라고 나오는데요.", "evidenceIds": ["ev_study_entry_log"]},
                    ]
                }
            )
        }
    )
    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))
    prompt = build_character_dialogue_prompt(payload, None, plan)
    rendered = str(prompt.model_dump())

    assert "Dialogue History" in rendered
    assert "turns" in rendered
    assert "22시 이후 어디 있었죠?" in rendered
    assert "출입 기록엔 서재라고 나오는데요." in rendered
    assert "continuityInstruction" in rendered
    assert "새로 받은 압박" in rendered or "반복하지" in rendered


def test_character_prompt_requires_structured_character_agent_output_contract() -> None:
    payload = _request(message="22시 이후 어디에 있었나요?", mode="normal")
    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))
    prompt = build_character_dialogue_prompt(payload, None, plan)
    rendered = str(prompt.model_dump())

    assert "CharacterAgent Output Contract" in rendered
    assert "speakerIntent" in rendered
    assert "emotionalBeat" in rendered
    assert "continuityMove" in rendered
    assert "finalLine" in rendered
    assert "JSON 객체만 출력" in rendered


def test_reaction_route_plan_carries_player_message_for_question_grounding() -> None:
    payload = _request(message="22시 이후 어디에 있었나요?", mode="normal")
    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))

    assert plan.functionCall is not None
    assert plan.functionCall["arguments"]["playerMessage"] == "22시 이후 어디에 있었나요?"


def test_rule_check_regeneration_prompt_preserves_player_question_anchor() -> None:
    payload = _request(message="22시 이후 어디에 있었나요?", mode="normal")
    draft = DraftCharacterReply(
        requestId=payload.requestId,
        correlationId=payload.correlationId,
        suspectId=payload.suspect.id,
        draftText="그날 일은 저도 혼란스럽습니다.",
        provider="test",
        model="test-model",
    )
    check_input = LightRuleCheckInput(
        requestId=payload.requestId,
        correlationId=payload.correlationId,
        draft=draft,
        characterKnowledgePack=payload.characterKnowledgePack,
        allowedStatement=payload.allowedStatement,
        allowedEventPolicy=payload.allowedEventPolicy,
        suspectName=payload.suspect.name,
        dialogueDirectorPlan=DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload)),
    )

    prompt, _seed = build_rule_check_regen_prompt(check_input, ["seed_verbatim"], payload.allowedStatement.text, 0)
    rendered = str(prompt.model_dump())

    assert "Player Turn" in rendered
    assert "22시 이후 어디에 있었나요?" in rendered
    assert "원문 질문에 대한 응답성을 유지" in rendered


def test_light_rule_check_regenerates_when_route_draft_copies_generated_seed() -> None:
    from app.ai_engine.agents.light_rule_check_agent import LightRuleCheck

    class RecordingRuleCheck(LightRuleCheck):
        def __init__(self) -> None:
            self.regen_calls = 0

        def _regenerate(self, system_prompt, seed: str, model_hint: str) -> str | None:  # type: ignore[override]
            self.regen_calls += 1
            return "그만해. 그런 식으로 몰아붙여도 내가 하지 않은 말까지 맞춰줄 생각 없어."

    payload = _request(
        suspect_id="char_hanseoyeon",
        suspect_name="한서연",
        message="너 범인이지?",
        mode="pressure_followup",
        tension_level="high",
        pressure_state="pressed",
        emotional_state="defensive",
        tension_score=70,
    )
    plan = DialogueDirectorPlan(
        strategy="deflect_irrelevant",
        allowedAdmissionLevel="no_new_fact",
        styleDirectives=["캐릭터 성격에 맞게 짧게 회피한다."],
        forbiddenClaims=["새 사건 사실"],
        functionCall={
            "name": "deflect_irrelevant_turn",
            "arguments": {"playerMessage": payload.question.text, "suspectName": payload.suspect.name},
            "transferTo": "CharacterAgent",
            "reason": "deflect_irrelevant",
        },
        reason="deflect_irrelevant",
    )
    copied_seed = render_dialogue_seed(payload, plan)
    checker = RecordingRuleCheck()

    result = checker.run(
        LightRuleCheckInput(
            requestId=payload.requestId,
            correlationId=payload.correlationId,
            draft=DraftCharacterReply(
                requestId=payload.requestId,
                correlationId=payload.correlationId,
                suspectId=payload.suspect.id,
                draftText=copied_seed,
                provider="test-provider",
                model="test-model",
            ),
            characterKnowledgePack=payload.characterKnowledgePack,
            allowedStatement=payload.allowedStatement,
            allowedEventPolicy=payload.allowedEventPolicy,
            enforceStatementScope=False,
            suspectName=payload.suspect.name,
            dialogueDirectorPlan=plan,
            generatedSeed=copied_seed,
        )
    )

    assert checker.regen_calls == 1
    assert result.finalText != copied_seed
    assert result.safetyFindings["finalTextSource"] == "regenerated_attempt_1"


def test_light_rule_check_regenerates_vulgar_victim_relation_draft() -> None:
    from app.ai_engine.agents.light_rule_check_agent import LightRuleCheck

    class RecordingRuleCheck(LightRuleCheck):
        def __init__(self) -> None:
            self.regen_calls = 0

        def _regenerate(self, system_prompt, seed: str, model_hint: str) -> str | None:  # type: ignore[override]
            self.regen_calls += 1
            return "삼촌이야. 도움 받은 건 맞아. 그 이상으로 말하고 싶진 않아."

    payload = _request(
        suspect_id="char_hanseoyeon",
        suspect_name="한서연",
        message="너랑 회장님이랑 어떤 관계지?",
        mode="case_question",
    ).model_copy(
        update={
            "allowedStatement": _request(
                suspect_id="char_hanseoyeon",
                suspect_name="한서연",
                message="너랑 회장님이랑 어떤 관계지?",
                mode="case_question",
            ).allowedStatement.model_copy(
                update={"text": "삼촌이야. 부모님 돌아가신 뒤 이 집에 들어왔고, 도움을 받은 건 맞아. 그게 다야."}
            )
        }
    )
    checker = RecordingRuleCheck()

    result = checker.run(
        LightRuleCheckInput(
            requestId=payload.requestId,
            correlationId=payload.correlationId,
            draft=DraftCharacterReply(
                requestId=payload.requestId,
                correlationId=payload.correlationId,
                suspectId=payload.suspect.id,
                draftText="… 삼촌이 뭐? 그 인간 나한테 해준 게 뭐가 있다고. 돈이나 처먹었지, 그 이상도 이하도 아냐.",
                provider="test-provider",
                model="test-model",
            ),
            characterKnowledgePack=payload.characterKnowledgePack,
            allowedStatement=payload.allowedStatement,
            allowedEventPolicy=payload.allowedEventPolicy,
            enforceStatementScope=False,
            suspectName=payload.suspect.name,
            dialogueDirectorPlan=DialogueDirectorPlan(strategy="answer_requested_relationship_only"),
            generatedSeed=payload.allowedStatement.text,
        )
    )

    assert checker.regen_calls == 1
    assert "처먹" not in result.finalText
    assert result.safetyFindings["finalTextSource"] == "regenerated_attempt_1"
