from typing import Iterable, List, Set

from app.domain.interrogation_state import emotional_state, pressure_state, tension_level
from app.domain.models import Case, SessionState


def initial_session_state(case: Case, session_id: str) -> SessionState:
    default_suspect_id = _default_selected_suspect_id(case)
    return SessionState(
        sessionId=session_id,
        caseId=case.caseId,
        remainingQuestions=case.questionLimit,
        selectedSuspectId=default_suspect_id,
        unlockedEvidenceIds=[item.evidenceId for item in case.evidence if item.initiallyVisible],
        unlockedRecordIds=[item.recordId for item in case.records if item.initiallyVisible],
        unlockedRelationIds=[item.relationshipId for item in case.relations if item.initiallyVisible],
        unlockedStatementIds=[item.statementId for item in case.statements if item.initiallyVisible],
        unlockedQuestionIds=[item.questionId for item in case.questions if item.initiallyUnlocked],
        pressureBySuspect={suspect.characterId: 0 for suspect in case.suspects},
    )


def _default_selected_suspect_id(case: Case) -> str | None:
    """Pick the first public focus suspect so a new session is immediately playable.

    The selection is public UI state only. It must not derive from private solution
    fields such as culprit/secret/motive.
    """
    if case.storyline:
        for act in case.storyline.acts:
            for suspect_id in act.focusSuspectIds:
                if any(suspect.characterId == suspect_id for suspect in case.suspects):
                    return suspect_id
    return case.suspects[0].characterId if case.suspects else None


def apply_unlocks(session: SessionState, case: Case, ids: Iterable[str]) -> List[str]:
    newly_unlocked: List[str] = []
    known_sets = {
        "evidence": set(session.unlockedEvidenceIds),
        "records": set(session.unlockedRecordIds),
        "relations": set(session.unlockedRelationIds),
        "statements": set(session.unlockedStatementIds),
        "questions": set(session.unlockedQuestionIds),
    }
    case_ids = {
        "evidence": {item.evidenceId for item in case.evidence},
        "records": {item.recordId for item in case.records},
        "relations": {item.relationshipId for item in case.relations},
        "statements": {item.statementId for item in case.statements},
        "questions": {item.questionId for item in case.questions},
    }

    for item_id in ids:
        target = _target_for_id(item_id, case_ids)
        if target and item_id not in known_sets[target]:
            getattr(session, _session_field_for_target(target)).append(item_id)
            known_sets[target].add(item_id)
            newly_unlocked.append(item_id)

    session.newlyUnlockedIds = newly_unlocked
    return newly_unlocked


def visible_session_payload(session: SessionState, case: Case) -> dict:
    visible_evidence = _filter_by_ids(case.evidence, "evidenceId", session.unlockedEvidenceIds)
    visible_records = _filter_by_ids(case.records, "recordId", session.unlockedRecordIds)
    visible_relations = _filter_by_ids(case.relations, "relationshipId", session.unlockedRelationIds)
    visible_statements = _filter_by_ids(case.statements, "statementId", session.unlockedStatementIds)
    visible_questions = _filter_by_ids(case.questions, "questionId", session.unlockedQuestionIds)

    return {
        "sessionId": session.sessionId,
        "caseId": session.caseId,
        "phase": session.phase,
        "remainingQuestions": session.remainingQuestions,
        "selectedSuspectId": session.selectedSuspectId,
        "opening": public_opening(case),
        "storyline": public_storyline(case, session),
        "visibleTimeline": visible_timeline(case, session),
        **current_story_progress(session, case),
        "caseFile": public_case_file(case, session),
        "suspects": [
            {
                "characterId": item.characterId,
                "name": item.name,
                "role": item.role,
                "publicProfile": item.publicProfile,
                "motiveCandidate": item.motiveCandidate,
                "pressure": session.pressureBySuspect.get(item.characterId, 0),
                "pressureState": pressure_state(session.pressureBySuspect.get(item.characterId, 0)),
                "tensionLevel": tension_level(session.pressureBySuspect.get(item.characterId, 0)),
                "emotionalState": emotional_state(session.pressureBySuspect.get(item.characterId, 0)),
                "speechStyle": public_speech_style(item.characterId) | (item.speechStyle or {}),
                "publicTimeline": character_public_timeline(case, session, item.characterId),
            }
            for item in case.suspects
        ],
        "dialogueLog": [_dump(item) for item in session.dialogueLog],
        "notes": [_dump(item) for item in session.notes],
        "bookmarks": [_dump(item) for item in session.bookmarks],
        "evidence": [_dump(item) for item in visible_evidence],
        "records": [_dump(item) for item in visible_records],
        "relations": [_public_relation_detail(case, session, item) for item in visible_relations],
        "relationMap": public_relation_map(case, session),
        "statements": [_dump(item) for item in visible_statements],
        "questions": [_dump(item) for item in visible_questions],
        "unlockedQuestionIds": session.unlockedQuestionIds,
        "askedQuestionCounts": session.askedQuestionCounts,
        "newlyUnlockedIds": session.newlyUnlockedIds,
        "lastDialogueResult": session.lastDialogueResult,
        "lastRuntimeDiagnostics": session.lastRuntimeDiagnostics,
        "runtimeDiagnostics": session.lastRuntimeDiagnostics,
        "discoveredContradictionIds": session.discoveredContradictionIds,
        "pressureBySuspect": session.pressureBySuspect,
        "pressureStates": {
            suspect.characterId: pressure_state(session.pressureBySuspect.get(suspect.characterId, 0))
            for suspect in case.suspects
        },
        "accusationReadiness": public_accusation_readiness(case, session),
        "accusation": session.accusation,
        "notebook": public_notebook(case, session),
        "contradictions": public_contradiction_read_model(case, session),
    }


def public_case_file(case: Case, session: SessionState | None = None) -> dict:
    progress = current_story_progress(session, case) if session is not None else current_story_progress(initial_session_state(case, "preview"), case)
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
        "currentObjective": progress["currentObjective"],
        "currentActId": progress["currentActId"],
        "visibleTimeline": visible_timeline(case, session),
    }


def public_notebook(case: Case, session: SessionState) -> dict:
    evidence = [_public_evidence_detail(case, session, item) for item in _filter_by_ids(case.evidence, "evidenceId", session.unlockedEvidenceIds)]
    statements = [_public_statement_detail(case, session, item) for item in _filter_by_ids(case.statements, "statementId", session.unlockedStatementIds)]
    return {
        "caseFile": public_case_file(case, session),
        "notes": [_dump(item) for item in session.notes],
        "bookmarks": [_dump(item) for item in session.bookmarks],
        "evidence": evidence,
        "records": [_dump(item) for item in _filter_by_ids(case.records, "recordId", session.unlockedRecordIds)],
        "relations": [_public_relation_detail(case, session, item) for item in _filter_by_ids(case.relations, "relationshipId", session.unlockedRelationIds)],
        "relationMap": public_relation_map(case, session),
        "statements": statements,
        "statementsBySuspect": _group_by_key(statements, "characterId"),
        "questionsBySuspect": _group_by_key(
            [_dump(item) for item in _filter_by_ids(case.questions, "questionId", session.unlockedQuestionIds)],
            "characterId",
        ),
        "contradictions": public_contradiction_read_model(case, session),
        "accusationReadiness": public_accusation_readiness(case, session),
    }


def public_accusation_readiness(case: Case, session: SessionState) -> dict:
    required_contradictions = set(case.solution.requiredContradictionIds)
    required_evidence = set(case.solution.requiredEvidenceIds)
    required_statements = set(case.solution.requiredStatementIds)
    missing_contradictions = required_contradictions.difference(session.discoveredContradictionIds)
    missing_evidence = required_evidence.difference(session.unlockedEvidenceIds)
    missing_statements = required_statements.difference(session.unlockedStatementIds)
    return {
        "eligible": not missing_contradictions and not missing_evidence and not missing_statements,
        "missingRequiredContradictionCount": len(missing_contradictions),
        "missingRequiredEvidenceCount": len(missing_evidence),
        "missingRequiredStatementCount": len(missing_statements),
        "discoveredRequiredContradictionCount": len(required_contradictions.intersection(session.discoveredContradictionIds)),
        "requiredContradictionCount": len(required_contradictions),
    }


def public_relation_map(case: Case, session: SessionState) -> dict:
    nodes = [
        {
            "characterId": case.victimId,
            "name": case.victimName,
            "role": "victim",
            "nodeType": "victim",
            "unlocked": True,
        },
        *[
            {
                "characterId": suspect.characterId,
                "name": suspect.name,
                "role": suspect.role,
                "nodeType": "suspect",
                "unlocked": True,
                "pressure": session.pressureBySuspect.get(suspect.characterId, 0),
                "pressureState": pressure_state(session.pressureBySuspect.get(suspect.characterId, 0)),
                "tensionLevel": tension_level(session.pressureBySuspect.get(suspect.characterId, 0)),
            }
            for suspect in case.suspects
        ],
    ]
    return {
        "centerCharacterId": case.victimId,
        "nodes": nodes,
        "edges": [_public_relation_edge(case, session, item) for item in case.relations],
    }


def _public_relation_detail(case: Case, session: SessionState, relation) -> dict:
    edge = _public_relation_edge(case, session, relation)
    return {
        "relationshipId": relation.relationshipId,
        "characterId": relation.characterId,
        "sourceCharacterId": edge["sourceCharacterId"],
        "targetCharacterId": edge["targetCharacterId"],
        "label": edge["label"],
        "description": edge["description"],
        "conflict": edge["conflict"],
        "unlocked": edge["unlocked"],
        "unlockState": edge["unlockState"],
        "evidenceRefs": edge["evidenceRefs"],
        "statementRefs": edge["statementRefs"],
        "recordRefs": edge["recordRefs"],
    }


def _public_relation_edge(case: Case, session: SessionState, relation) -> dict:
    unlocked = relation.relationshipId in session.unlockedRelationIds
    suspect = next((item for item in case.suspects if item.characterId == relation.characterId), None)
    safe_label = relation.description if unlocked else "미확인 관계"
    safe_description = relation.description if unlocked else "아직 공개 단서로 확인되지 않은 관계입니다."
    safe_conflict = relation.conflict if unlocked else ""
    return {
        "relationshipId": relation.relationshipId,
        "sourceCharacterId": case.victimId,
        "targetCharacterId": relation.characterId,
        "sourceName": case.victimName,
        "targetName": suspect.name if suspect else relation.characterId,
        "label": safe_label,
        "description": safe_description,
        "conflict": safe_conflict,
        "unlocked": unlocked,
        "unlockState": "unlocked" if unlocked else "locked",
        "evidenceRefs": _visible_ids_for_character(case.evidence, "evidenceId", session.unlockedEvidenceIds, relation.characterId),
        "statementRefs": _visible_ids_for_character(case.statements, "statementId", session.unlockedStatementIds, relation.characterId),
        "recordRefs": [],
    }


def _visible_ids_for_character(items: list, id_field: str, visible_ids: list[str], character_id: str) -> list[str]:
    refs = []
    for item in items:
        if getattr(item, id_field) not in visible_ids:
            continue
        if getattr(item, "characterId", None) == character_id:
            refs.append(getattr(item, id_field))
    return refs


def public_contradiction_read_model(case: Case, session: SessionState) -> dict:
    visible = []
    discovered = []
    for contradiction in case.contradictions:
        detail = _public_contradiction_detail(case, session, contradiction)
        if detail is None:
            continue
        if contradiction.contradictionId in session.discoveredContradictionIds:
            discovered.append({**detail, "status": "discovered", "submitEligible": True})
        else:
            visible.append({**detail, "status": "candidate", "submitEligible": detail["allRequiredVisible"]})
    return {
        "discoveredIds": list(session.discoveredContradictionIds),
        "discovered": discovered,
        "candidates": visible,
    }


def _public_evidence_detail(case: Case, session: SessionState, evidence) -> dict:
    data = _dump(evidence)
    data["sourceRefs"] = _source_refs_for_id(case, session, evidence.evidenceId)
    data["relatedStatementIds"] = [
        contradiction.requiredStatementIds[0]
        for contradiction in case.contradictions
        if evidence.evidenceId in contradiction.requiredEvidenceIds
        and set(contradiction.requiredStatementIds).issubset(set(session.unlockedStatementIds))
    ]
    data["relatedContradictionIds"] = [
        contradiction.contradictionId
        for contradiction in case.contradictions
        if evidence.evidenceId in contradiction.requiredEvidenceIds
        and _contradiction_has_visible_required_ids(contradiction, session)
    ]
    data["timelineIds"] = [_timeline_public_id(item) for item in visible_timeline(case, session) if item.get("sourceId") == evidence.evidenceId]
    return data


def _public_statement_detail(case: Case, session: SessionState, statement) -> dict:
    data = _dump(statement)
    suspect = next((item for item in case.suspects if item.characterId == statement.characterId), None)
    data["suspectName"] = suspect.name if suspect else statement.characterId
    data["sourceRefs"] = _source_refs_for_id(case, session, statement.statementId)
    data["relatedEvidenceIds"] = [
        evidence_id
        for contradiction in case.contradictions
        if statement.statementId in contradiction.requiredStatementIds
        for evidence_id in contradiction.requiredEvidenceIds
        if evidence_id in session.unlockedEvidenceIds
    ]
    data["relatedContradictionIds"] = [
        contradiction.contradictionId
        for contradiction in case.contradictions
        if statement.statementId in contradiction.requiredStatementIds
        and _contradiction_has_visible_required_ids(contradiction, session)
    ]
    return data


def _public_contradiction_detail(case: Case, session: SessionState, contradiction) -> dict | None:
    has_any_visible = bool(set(contradiction.requiredStatementIds) & set(session.unlockedStatementIds)) or bool(
        set(contradiction.requiredEvidenceIds) & set(session.unlockedEvidenceIds)
    )
    discovered = contradiction.contradictionId in session.discoveredContradictionIds
    if not has_any_visible and not discovered:
        return None
    all_visible = _contradiction_has_visible_required_ids(contradiction, session)
    suspect = next((item for item in case.suspects if item.characterId == contradiction.relatedCharacterId), None)
    return {
        "contradictionId": contradiction.contradictionId,
        "title": contradiction.title,
        "suspectId": contradiction.relatedCharacterId,
        "suspectName": suspect.name if suspect else contradiction.relatedCharacterId,
        "statementIds": [item for item in contradiction.requiredStatementIds if item in session.unlockedStatementIds],
        "evidenceIds": [item for item in contradiction.requiredEvidenceIds if item in session.unlockedEvidenceIds],
        "requiredStatementIds": list(contradiction.requiredStatementIds) if all_visible or discovered else [],
        "requiredEvidenceIds": list(contradiction.requiredEvidenceIds) if all_visible or discovered else [],
        "severity": contradiction.severity,
        "reasonCode": _public_reason_code(contradiction.reasonCode),
        "displayText": contradiction.message if discovered else "제시 가능한 진술과 증거를 조합해 모순 여부를 확인하세요.",
        "allRequiredVisible": all_visible,
    }


def _contradiction_has_visible_required_ids(contradiction, session: SessionState) -> bool:
    return set(contradiction.requiredStatementIds).issubset(set(session.unlockedStatementIds)) and set(
        contradiction.requiredEvidenceIds
    ).issubset(set(session.unlockedEvidenceIds))


def _public_reason_code(reason_code: str) -> str:
    public_codes = {
        "hidden_will_schedule": "call_record_schedule",
    }
    return public_codes.get(reason_code, reason_code)


def _source_refs_for_id(case: Case, session: SessionState, source_id: str) -> dict:
    return {
        "timelineIds": [_timeline_public_id(item) for item in visible_timeline(case, session) if item.get("sourceId") == source_id],
        "contradictionIds": [
            contradiction.contradictionId
            for contradiction in case.contradictions
            if source_id in contradiction.requiredStatementIds or source_id in contradiction.requiredEvidenceIds
            if _contradiction_has_visible_required_ids(contradiction, session)
        ],
    }


def _timeline_public_id(item: dict) -> str:
    return str(item.get("timelineId") or item.get("sourceId") or f"{item.get('time', '')}:{item.get('title', '')}")


def _group_by_key(items: list[dict], key: str) -> dict:
    grouped: dict[str, list[dict]] = {}
    for item in items:
        grouped.setdefault(str(item.get(key) or "unknown"), []).append(item)
    return grouped


def public_speech_style(character_id: str) -> dict:
    styles = {
        "char_hanseoyeon": {"persona": "상속 갈등을 숨기려는 조카", "low": "차갑고 방어적", "high": "말끝이 흔들리고 공격적으로 부정"},
        "char_yoonjaeho": {"persona": "오래된 집사", "low": "공손하고 절제됨", "high": "책임을 회피하며 긴 문장으로 설명"},
        "char_parkmingyu": {"persona": "전문성을 내세우는 주치의", "low": "침착하고 의학적", "high": "권위를 내세우며 예민해짐"},
        "char_choiyuna": {"persona": "일정을 관리한 비서", "low": "정확하고 사무적", "high": "짧게 끊어 말하며 불안"},
    }
    return styles.get(character_id, {"persona": "용의자", "low": "조심스러움", "high": "방어적"})


def character_public_timeline(case: Case, session: SessionState, character_id: str) -> list[dict]:
    visible_statement_ids = {
        statement.statementId
        for statement in case.statements
        if statement.characterId == character_id and statement.statementId in session.unlockedStatementIds
    }
    visible_evidence_ids = set(session.unlockedEvidenceIds)
    related_evidence_ids = {
        evidence_id
        for contradiction in case.contradictions
        if contradiction.relatedCharacterId == character_id
        and set(contradiction.requiredStatementIds) & visible_statement_ids
        for evidence_id in contradiction.requiredEvidenceIds
        if evidence_id in visible_evidence_ids
    }

    events: list[dict] = []
    suspect = next((item for item in case.suspects if item.characterId == character_id), None)
    suspect_name = suspect.name if suspect else character_id
    for statement in case.statements:
        if statement.statementId not in visible_statement_ids:
            continue
        events.append(
            {
                "timelineId": f"ctl_{statement.statementId}",
                "time": statement.timeWindow,
                "title": f"{suspect_name}의 진술",
                "description": statement.text,
                "sourceType": "statement",
                "sourceId": statement.statementId,
                "claimedLocation": statement.location,
                "claimedAction": statement.text,
                "relatedStatementIds": [statement.statementId],
                "relatedEvidenceIds": [
                    evidence_id
                    for contradiction in case.contradictions
                    if statement.statementId in contradiction.requiredStatementIds
                    for evidence_id in contradiction.requiredEvidenceIds
                    if evidence_id in visible_evidence_ids
                ],
                "public": True,
            }
        )

    existing_ids = {event["timelineId"] for event in events}
    for item in visible_timeline(case, session):
        source_id = item.get("sourceId")
        if source_id not in related_evidence_ids:
            continue
        timeline_id = _timeline_public_id(item)
        if timeline_id in existing_ids:
            continue
        events.append(
            {
                **item,
                "timelineId": timeline_id,
                "relatedStatementIds": [
                    statement_id
                    for contradiction in case.contradictions
                    if source_id in contradiction.requiredEvidenceIds
                    for statement_id in contradiction.requiredStatementIds
                    if statement_id in visible_statement_ids
                ],
                "relatedEvidenceIds": [source_id],
                "public": True,
            }
        )
        existing_ids.add(timeline_id)
    return sorted(events, key=lambda item: str(item.get("time") or ""))


def _target_for_id(item_id: str, case_ids: dict[str, Set[str]]) -> str | None:
    for target, ids in case_ids.items():
        if item_id in ids:
            return target
    return None


def _session_field_for_target(target: str) -> str:
    return {
        "evidence": "unlockedEvidenceIds",
        "records": "unlockedRecordIds",
        "relations": "unlockedRelationIds",
        "statements": "unlockedStatementIds",
        "questions": "unlockedQuestionIds",
    }[target]


def _filter_by_ids(items: list, id_field: str, ids: List[str]) -> list:
    order = {item_id: index for index, item_id in enumerate(ids)}
    return sorted(
        [item for item in items if getattr(item, id_field) in order],
        key=lambda item: order[getattr(item, id_field)],
    )


def _dump(item) -> dict:
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return item.dict()

def public_opening(case: Case) -> dict | None:
    return _dump(case.opening) if case.opening else None


def public_storyline(case: Case, session: SessionState | None = None) -> dict | None:
    if not case.storyline:
        return None
    visible_ids = _visible_source_ids(case, session)
    return {
        "publicPremise": case.storyline.publicPremise,
        "acts": [_dump(act) for act in case.storyline.acts],
        "timeline": [_public_timeline_item(item) for item in _visible_timeline(case, session, visible_ids)],
        "cluePaths": [_public_clue_path(path) for path in case.storyline.cluePaths],
    }


def current_story_progress(session: SessionState, case: Case) -> dict:
    if not case.storyline:
        return {"currentObjective": "용의자 진술과 증거를 비교해 모순을 찾으세요.", "currentActId": "investigation"}
    rules = sorted(case.storyline.currentObjectiveRules, key=lambda item: item.priority, reverse=True)
    for rule in rules:
        if _objective_rule_matches(rule, session):
            return {"currentObjective": rule.objective, "currentActId": rule.actId}
    first = case.storyline.acts[0] if case.storyline.acts else None
    return {
        "currentObjective": first.objective if first else "용의자 진술과 증거를 비교해 모순을 찾으세요.",
        "currentActId": first.actId if first else "investigation",
    }


def visible_timeline(case: Case, session: SessionState | None = None) -> list[dict]:
    visible_ids = _visible_source_ids(case, session)
    return [_public_timeline_item(item) for item in _visible_timeline(case, session, visible_ids)]


def _public_timeline_item(item) -> dict:
    data = _dump(item)
    data.pop("hidden", None)
    return data


def _public_clue_path(path) -> dict:
    data = _dump(path)
    data.pop("secretNote", None)
    return data


def _visible_timeline(case: Case, session: SessionState | None, visible_ids: set[str]) -> list:
    if not case.storyline:
        return []
    return [
        item for item in case.storyline.timeline
        if not item.hidden and (not item.unlockCondition or item.unlockCondition in visible_ids)
    ]


def _visible_source_ids(case: Case, session: SessionState | None = None) -> set[str]:
    if session is None:
        ids = {item.evidenceId for item in case.evidence if item.initiallyVisible}
        ids.update(item.recordId for item in case.records if item.initiallyVisible)
        ids.update(item.statementId for item in case.statements if item.initiallyVisible)
        ids.update(item.questionId for item in case.questions if item.initiallyUnlocked)
        ids.update(item.relationshipId for item in case.relations if item.initiallyVisible)
        return ids
    ids = set(session.unlockedEvidenceIds) | set(session.unlockedRecordIds) | set(session.unlockedStatementIds)
    ids |= set(session.unlockedQuestionIds) | set(session.unlockedRelationIds) | set(session.discoveredContradictionIds)
    return ids


def _objective_rule_matches(rule, session: SessionState) -> bool:
    condition = rule.when
    if condition.discoveredContradictionId and condition.discoveredContradictionId not in session.discoveredContradictionIds:
        return False
    if condition.missingContradictionId and condition.missingContradictionId in session.discoveredContradictionIds:
        return False
    if condition.pressureAtLeast:
        suspect_id = condition.pressureAtLeast.get("suspectId")
        value = int(condition.pressureAtLeast.get("value", 0))
        if session.pressureBySuspect.get(suspect_id, 0) < value:
            return False
    return True
