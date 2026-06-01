import json
from pathlib import Path
from typing import Dict, List

from app.domain.models import Case


class CaseRepository:
    def __init__(self, cases_dir: Path):
        self.cases_dir = cases_dir
        self._cache: Dict[str, Case] = {}

    def list_cases(self) -> List[Case]:
        self._load_all()
        return sorted(self._cache.values(), key=lambda item: item.caseId)

    def get_case(self, case_id: str) -> Case | None:
        self._load_all()
        return self._cache.get(case_id)

    def _load_all(self) -> None:
        if self._cache:
            return
        for path in sorted(self.cases_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            if hasattr(Case, "model_validate"):
                case = Case.model_validate(data)
            else:
                case = Case.parse_obj(data)
            self._cache[case.caseId] = case
