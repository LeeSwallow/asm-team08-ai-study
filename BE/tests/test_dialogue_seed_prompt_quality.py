from __future__ import annotations

from app.ai_engine.agents.character_agent import build_character_agent_input, render_dialogue_seed
from app.ai_engine.agents.dialogue_director_agent import DialogueDirectorAgent
from app.ai_engine.prompts.character_dialogue_builder import build_character_dialogue_prompt
from app.ai_engine.prompts.rule_check_builder import build_rule_check_regen_prompt
from app.ai_engine.schemas.agents import DialogueDirectorInput, DraftCharacterReply, LightRuleCheckInput
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


def test_character_prompt_anchors_final_generation_to_player_question() -> None:
    payload = _request(message="22시 이후 어디에 있었나요?", mode="normal")
    plan = DialogueDirectorAgent().run(DialogueDirectorInput(payload=payload))
    prompt = build_character_dialogue_prompt(payload, None, plan)
    rendered = str(prompt.model_dump())

    assert "Player Turn" in rendered
    assert "22시 이후 어디에 있었나요?" in rendered
    assert "사용자의 이번 발화에 직접 반응" in rendered
    assert "공개 사실 범위" in rendered


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
