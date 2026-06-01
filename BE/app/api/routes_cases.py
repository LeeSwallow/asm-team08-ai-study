from fastapi import APIRouter, Depends

from app.api.deps import get_case_repository
from app.core.errors import not_found
from app.infra.case_repository import CaseRepository
from app.domain.case_engine import public_case_file, public_opening, public_storyline, visible_timeline

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("")
def list_cases(case_repo: CaseRepository = Depends(get_case_repository)):
    return [
        {
            "caseId": case.caseId,
            "sceneId": case.sceneId,
            "title": case.title,
            "summary": case.summary,
            "victimName": case.victimName,
            "incidentTime": case.incidentTime,
            "incidentLocation": case.incidentLocation,
            "questionLimit": case.questionLimit,
            "opening": public_opening(case),
        }
        for case in case_repo.list_cases()
    ]


@router.get("/{case_id}")
def get_case(case_id: str, case_repo: CaseRepository = Depends(get_case_repository)):
    case = case_repo.get_case(case_id)
    if case is None:
        raise not_found("Case not found")
    return {
        "caseId": case.caseId,
        "sceneId": case.sceneId,
        "title": case.title,
        "summary": case.summary,
        "victimId": case.victimId,
        "victimName": case.victimName,
        "incidentTime": case.incidentTime,
        "incidentLocation": case.incidentLocation,
        "questionLimit": case.questionLimit,
        "opening": public_opening(case),
        "caseFile": public_case_file(case),
        "storyline": public_storyline(case),
        "visibleTimeline": visible_timeline(case),
        "suspects": [
            {
                "characterId": item.characterId,
                "name": item.name,
                "role": item.role,
                "publicProfile": item.publicProfile,
                "motiveCandidate": item.motiveCandidate,
            }
            for item in case.suspects
        ],
        "evidence": [_dump(item) for item in case.evidence if item.initiallyVisible],
        "records": [_dump(item) for item in case.records if item.initiallyVisible],
        "relations": [_dump(item) for item in case.relations if item.initiallyVisible],
        "statements": [_dump(item) for item in case.statements if item.initiallyVisible],
        "questions": [_dump(item) for item in case.questions if item.initiallyUnlocked],
    }


def _dump(item) -> dict:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return item.dict()
