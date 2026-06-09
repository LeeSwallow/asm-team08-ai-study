from __future__ import annotations

from app.ai_engine.domain.dialogue_intent import classify_dialogue_intent
from app.ai_engine.schemas.agents import DialogueDirectorPlan
from app.ai_engine.schemas.dialogue import DialogueRequest
from app.ai_engine.agents.character_utils import _choice_index


def _join_focus_terms_for_seed(focus_terms: list[str]) -> str:
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
        variants = (
            "인사까지 받을 여유는 없네요. 그래도 제가 아는 범위라면 말하겠습니다.",
            "이런 자리에서 반갑다고 하긴 어렵죠. 사건과 관련된 제 기억은 숨기지 않겠습니다.",
            "예의 차릴 상황은 아닌 것 같네요. 제가 본 것과 기억하는 것만 말하겠습니다.",
        )
        return variants[_choice_index(suspect_name, message, modulo=len(variants))]

    if function_name == "deflect_unmatched_turn" or function_name == "deflect_irrelevant_turn":
        if focus_terms:
            focus = ", ".join(focus_terms[:2])
            variants = (
                f"{focus} 얘기라면 제가 직접 본 범위까지만 말할 수 있습니다. 그 밖을 단정하진 않겠습니다.",
                f"{focus}만으로는 제가 더 보탤 말이 많지 않아요. 제가 겪은 일과 연결되는 부분만 답하겠습니다.",
            )
        else:
            variants = (
                "그렇게 넓게 몰아가면 제 진술이 흐려집니다. 제 행적과 제가 본 것만 말하겠습니다.",
                "그 질문은 제 진술과 바로 이어지지 않네요. 제가 직접 확인한 범위 안에서만 답하겠습니다.",
                "그 부분은 제가 단정할 수 없습니다. 괜히 없는 말을 만들고 싶진 않아요.",
            )
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
        focus = ", ".join(focus_terms[:2])
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
        variants = (
            "그 질문은 제 진술과 바로 이어지지 않네요. 제가 직접 확인한 범위 안에서만 답하겠습니다.",
            "그 부분은 제가 단정할 수 없습니다. 괜히 없는 말을 만들고 싶진 않아요.",
        )
        return variants[_choice_index(name, payload.question.text, modulo=len(variants))]
    return base or "제가 공개적으로 말할 수 있는 건 거기까지입니다."
