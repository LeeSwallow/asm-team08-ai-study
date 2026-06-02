from __future__ import annotations

from app.domain.models import Case


def case_from_payload(payload: dict) -> Case:
    if hasattr(Case, "model_validate"):
        return Case.model_validate(payload)
    return Case.parse_obj(payload)


def case_to_payload(case: Case) -> dict:
    if hasattr(case, "model_dump"):
        return case.model_dump(mode="json")
    return case.dict()
