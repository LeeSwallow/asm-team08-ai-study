from __future__ import annotations

from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent
from app.ai_engine.schemas.agents import DialogueDirectorPlan
from app.ai_engine.schemas.dialogue import DialogueRequest
from app.ai_engine.agents.character_utils import _choice_index

_PUBLIC_REF_LABELS = {
    "ev_lipstick_glass": "와인잔의 립스틱 자국",
    "ev_study_entry_log": "서재 출입 기록",
    "ev_torn_will": "찢어진 유언장",
    "ev_wine_glass": "와인잔",
    "stmt_visible_hanseoyeon": "제 공개 진술",
    "st_hanseoyeon_room_2200": "제 방에 있었다는 진술",
    "tl_victim_study_2200": "22시 무렵 서재 정황",
    "con_room_claim_vs_entry_log": "방 진술과 출입 기록의 충돌",
}


def _display_focus_term(term: str) -> str:
    if term in _PUBLIC_REF_LABELS:
        return _PUBLIC_REF_LABELS[term]
    if term.startswith(("ev_", "stmt_", "st_", "tl_", "con_")):
        return "그 공개 단서"
    return term


def _join_focus_terms_for_seed(focus_terms: list[str]) -> str:
    focus_terms = [_display_focus_term(term) for term in focus_terms]
    if len(focus_terms) == 1:
        return focus_terms[0]
    if len(focus_terms) == 2:
        left, right = focus_terms
        last = left[-1]
        particle = "와"
        if "가" <= last <= "힣" and (ord(last) - ord("가")) % 28:
            particle = "과"
        return f"{left}{particle} {right}"
    return f"{focus_terms[0]}, {focus_terms[1]} 같은 단서들"


def _public_contradiction_seed(focus_terms: list[str]) -> str:
    if focus_terms:
        focus = _join_focus_terms_for_seed(focus_terms)
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


def _seed_pressure_band(payload: DialogueRequest) -> str:
    raw = (payload.suspect.tensionLevel or payload.suspect.pressureState or "").lower()
    score = payload.suspect.tensionScore if payload.suspect.tensionScore is not None else payload.suspect.pressure
    try:
        numeric = float(score) if score is not None else None
    except (TypeError, ValueError):
        numeric = None
    if raw in {"critical", "broken"} or (numeric is not None and numeric >= 80):
        return "critical"
    if raw in {"high", "pressed"} or (numeric is not None and numeric >= 55):
        return "high"
    if raw == "medium" or (numeric is not None and numeric >= 30):
        return "medium"
    return "low"


def _character_group(payload: DialogueRequest) -> str:
    suspect_id = payload.suspect.id
    if "yoon" in suspect_id:
        return "butler"
    if "park" in suspect_id:
        return "doctor"
    if "choi" in suspect_id:
        return "secretary"
    if "han" in suspect_id or "seo" in suspect_id:
        return "niece"
    return "default"


def _human_deflection_variants(payload: DialogueRequest) -> tuple[str, ...]:
    band = _seed_pressure_band(payload)
    group = _character_group(payload)
    player_text = " ".join(payload.question.text.strip().split())
    compact_player_text = player_text.replace(" ", "")
    if compact_player_text in {"뭐야", "뭐죠", "뭔데", "무슨말"}:
        by_group = {
            "butler": (
                "무슨 말씀인지 분명하지 않습니다. 제가 본 일이라면 구체적으로 물어봐 주십시오.",
                "질문이 너무 짧습니다. 회장님 일이나 제 동선을 묻는 거라면 분명히 말씀해 주십시오.",
            ),
            "niece": (
                "뭐가 뭔데? 물을 거 있으면 제대로 물어.",
                "그렇게 던지지 말고, 뭘 묻는 건지 똑바로 말해.",
            ),
            "doctor": (
                "무슨 의미인지 모호합니다. 의학 기록인지 그날 동선인지 분명히 물어보시죠.",
                "그렇게만 말하면 답할 수 없습니다. 확인하려는 대상을 말해 주세요.",
            ),
            "secretary": (
                "무슨 말씀인지 모르겠습니다. 일정인지 연락 기록인지 구체적으로 물어봐 주세요.",
                "질문을 조금만 분명히 해 주세요. 제가 확인한 업무 기록 범위에서 답하겠습니다.",
            ),
        }
        return by_group.get(group, ("무엇을 묻는지 분명하지 않습니다. 구체적으로 말해 주세요.",))
    if band == "critical":
        by_group = {
            "niece": (
                "지금 장난해? 그런 얘기 할 거면 난 더 말 안 해.",
                "숨 막히게 하지 마. 이상한 소리 말고 사건 얘기나 해.",
            ),
            "butler": (
                "지금은 그런 말씀을 받을 상황이 아닙니다. 제가 본 일만 말씀드리겠습니다.",
                "죄송하지만, 그런 말씀엔 답하지 않겠습니다. 사건과 관련된 것만 물어봐 주십시오.",
            ),
            "doctor": (
                "지금 농담할 때입니까? 제가 확인한 것만 말하겠습니다.",
                "그런 식의 말장난엔 답하지 않겠습니다. 사건 얘기로 돌아가죠.",
            ),
            "secretary": (
                "그런 요청엔 답하지 않겠습니다. 필요한 질문만 해 주세요.",
                "지금 그 얘기를 할 상황은 아니잖아요. 기록과 관련된 것만 말씀드릴게요.",
            ),
        }
        return by_group.get(
            group,
            (
                "잠깐만요. 그건 제가 답할 수 있는 범위가 아닙니다. 몰아붙여도 없는 말은 못 합니다.",
                "숨 좀 고르겠습니다. 그 질문은 제 진술과 이어지지 않습니다.",
            ),
        )
    if band in {"medium", "high"}:
        by_group = {
            "niece": (
                "아니, 지금 장난해? 이상한 소리 말고 사건 얘기나 해.",
                "그런 말에 맞춰줄 생각 없어. 물을 거 있으면 똑바로 물어.",
            ),
            "butler": (
                "그 말씀엔 답하기 어렵습니다. 지금은 사건과 관련된 것만 말씀드리겠습니다.",
                "그런 농담을 주고받을 상황은 아닌 것 같습니다. 제가 본 일만 말씀드리겠습니다.",
            ),
            "doctor": (
                "지금 농담하시는 겁니까? 사건과 관련된 질문이면 답하겠습니다.",
                "그런 말장난엔 답하지 않겠습니다. 필요한 것만 물어보시죠.",
            ),
            "secretary": (
                "그런 요청은 곤란합니다. 사건과 관련된 질문이면 답하겠습니다.",
                "네, 그건 답할 일이 아닌 것 같습니다. 필요한 질문만 해 주세요.",
            ),
        }
        return by_group.get(
            group,
            (
                "그 질문은 제 진술과 바로 이어지지 않네요. 제가 직접 확인한 범위 안에서만 답하겠습니다.",
                "그 부분은 제가 단정할 수 없습니다. 괜히 없는 말을 만들고 싶진 않아요.",
            ),
        )
    low_by_group = {
        "butler": (
            "그 말씀엔 답하기 어렵습니다. 사건과 관련된 것만 말씀드리겠습니다.",
            "그런 이야기를 나눌 상황은 아닌 것 같습니다. 제가 본 일만 말씀드리겠습니다.",
        ),
        "doctor": (
            "지금 농담하시는 겁니까? 사건과 관련된 질문이면 답하겠습니다.",
            "그런 말장난엔 답하지 않겠습니다. 필요한 것만 물어보시죠.",
        ),
        "secretary": (
            "그런 요청은 곤란합니다. 사건과 관련된 질문이면 답하겠습니다.",
            "네, 그건 답할 일이 아닌 것 같습니다. 필요한 질문만 해 주세요.",
        ),
    }
    if group in low_by_group:
        return low_by_group[group]
    return (
        *(
            (
                "지금 장난해? 그런 얘기 할 거면 난 더 말 안 해.",
                "그런 말에 맞춰줄 생각 없어. 물을 거 있으면 똑바로 물어.",
                "아니, 이상한 소리 말고 사건 얘기나 해.",
            )
            if group == "niece"
            else ()
        ),
        "그 질문은 제 진술과 바로 이어지지 않네요. 제가 직접 확인한 범위 안에서만 답하겠습니다.",
        "그 부분은 제가 단정할 수 없습니다. 괜히 없는 말을 만들고 싶진 않아요.",
        "그 얘기는 제가 아는 사건 정황하고는 거리가 있습니다. 제 주변에서 본 일만 말하겠습니다.",
    )


def _small_talk_variants(payload: DialogueRequest) -> tuple[str, ...]:
    band = _seed_pressure_band(payload)
    if band == "critical":
        return (
            "지금 인사 나눌 정신은 없습니다. 그래도 제가 본 일은 말하겠습니다.",
            "예의 차릴 여유가 없네요. 사건과 관련된 기억만 말씀드리겠습니다.",
        )
    return (
        "인사까지 받을 여유는 없네요. 그래도 제가 아는 범위라면 말하겠습니다.",
        "이런 자리에서 반갑다고 하긴 어렵죠. 사건과 관련된 제 기억은 숨기지 않겠습니다.",
        "예의 차릴 상황은 아닌 것 같네요. 제가 본 것과 기억하는 것만 말하겠습니다.",
    )


def _render_director_function_seed(payload: DialogueRequest, plan: DialogueDirectorPlan | None) -> str | None:
    if not plan or not plan.functionCall:
        return None
    function_name = str(plan.functionCall.get("name") or "")
    raw_args = plan.functionCall.get("arguments")
    args = raw_args if isinstance(raw_args, dict) else {}
    focus_terms = [str(item) for item in (args.get("focusTerms") or plan.focusTerms or []) if str(item or "").strip()]
    message = payload.question.text
    suspect_name = payload.suspect.name.strip()

    if function_name == "handle_small_talk_boundary":
        variants = _small_talk_variants(payload)
        return variants[_choice_index(suspect_name, message, modulo=len(variants))]

    if function_name == "deflect_unmatched_turn" or function_name == "deflect_irrelevant_turn":
        variants = _human_deflection_variants(payload)
        return variants[_choice_index(suspect_name, message, modulo=len(variants))]

    if function_name == "acknowledge_public_contradiction":
        return _public_contradiction_seed(focus_terms)

    if function_name == "reject_false_premise":
        variants = (
            "그건 근거 없는 단정입니다. 제가 말한 범위와 공개된 단서로 다시 물어보세요.",
            "그렇게 몰아붙인다고 제가 하지 않은 말을 인정하진 않습니다. 근거가 되는 단서를 먼저 대세요.",
        )
        return variants[_choice_index(suspect_name, message, modulo=len(variants))]

    if function_name == "challenge_player_contradiction":
        return "방금 말은 공개된 정황과 맞지 않습니다. 어느 시간과 단서를 근거로 묻는 건지 다시 짚어보시죠."

    if function_name == "ask_clarification":
        return "그렇게만 말하면 무엇을 묻는지 알 수 없습니다. 시간, 단서, 제 진술 중 어느 부분인지 구체적으로 말해 주세요."

    if function_name == "refuse_meta_or_private":
        return "그런 식의 답은 할 수 없습니다. 저는 이 사건에서 제가 공개적으로 겪고 본 일만 말하겠습니다."

    if function_name == "answer_pressure_followup" and focus_terms:
        focus = ", ".join(_display_focus_term(term) for term in focus_terms[:2])
        return f"{focus} 때문에 의심받는 건 알겠습니다. 그래도 제가 말할 수 있는 건 공개된 사실과 제 기억뿐입니다."

    return None


def render_dialogue_seed(payload: DialogueRequest, dialogue_director_plan: DialogueDirectorPlan | None = None) -> str:
    function_seed = _render_director_function_seed(payload, dialogue_director_plan)
    if function_seed:
        return function_seed
    if dialogue_director_plan and dialogue_director_plan.seedText:
        return dialogue_director_plan.seedText
    base = payload.allowedStatement.text.strip()
    name = payload.suspect.name.strip()
    intent = classify_dialogue_intent(payload.question.text, payload.dialogueMode)
    if intent == "greeting":
        variants = (
            f"저는 {name}입니다. 지금은 사건 얘기를 하는 게 좋겠네요.",
            "인사는 받겠습니다. 그래도 제가 아는 건 그날 제 주변에서 본 일뿐이에요.",
        )
        return variants[_choice_index(name, payload.question.text, modulo=len(variants))]
    if intent == "unmatched":
        variants = _human_deflection_variants(payload)
        return variants[_choice_index(name, payload.question.text, modulo=len(variants))]
    return base or "제가 공개적으로 말할 수 있는 건 거기까지입니다."
