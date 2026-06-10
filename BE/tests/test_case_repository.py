from app.infra.case_repository import CaseRepository


def test_case_repository_reads_case_from_database(seed_case_database):
    seed_case_database()

    repo = CaseRepository()
    case = repo.get_case("case_001")

    assert case is not None
    assert case.caseId == "case_001"
    assert case.suspects[0].speechStyle["tone"] == "sharp_defensive"
    assert case.suspects[0].speechStyle["register"] == "informal_banmal"
    assert case.suspects[0].personaVariants
