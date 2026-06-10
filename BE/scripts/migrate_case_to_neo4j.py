#!/usr/bin/env python3
"""
PostgreSQL cases table → Neo4j 마이그레이션 스크립트

사용법:
  cd BE
  BE_DATABASE_URL=postgresql://... BE_NEO4J_URI=bolt://localhost:7687 python scripts/migrate_case_to_neo4j.py

또는 docker 환경에서:
  docker compose exec backend python scripts/migrate_case_to_neo4j.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("BE_NEO4J_URI") or os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("BE_NEO4J_USER") or os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("BE_NEO4J_PASSWORD") or os.getenv("NEO4J_PASSWORD", "detective_secret")


def _id(item: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return ""


def _load_cases_from_database() -> list[dict]:
    from app.infra.case_orm import CaseRecord
    from app.infra.db import ensure_schema, get_session_factory

    if not ensure_schema():
        raise RuntimeError("BE_DATABASE_URL is required to load cases")
    session_factory = get_session_factory()
    if session_factory is None:
        raise RuntimeError("database session factory is not configured")
    with session_factory() as db:
        records = db.query(CaseRecord).order_by(CaseRecord.case_id).all()
        return [record.payload for record in records]


def _run_migration(driver: Any, case: dict) -> None:  # noqa: ANN001
    case_id = case["caseId"]
    logger.info("마이그레이션 시작: %s", case_id)

    with driver.session() as session:
        # ── 기존 케이스 데이터 삭제 (idempotent) ────────────────────────────
        session.run("MATCH (n {caseId: $caseId}) DETACH DELETE n", caseId=case_id)
        logger.info("  기존 노드 삭제 완료")

        # ── Case 노드 ────────────────────────────────────────────────────────
        session.run(
            """
            CREATE (c:Case {
                caseId: $caseId, sceneId: $sceneId, title: $title, summary: $summary,
                victimId: $victimId, victimName: $victimName,
                incidentTime: $incidentTime, incidentLocation: $incidentLocation,
                questionLimit: $questionLimit
            })
            """,
            caseId=case_id,
            sceneId=case.get("sceneId", ""),
            title=case.get("title", ""),
            summary=case.get("summary", ""),
            victimId=case.get("victimId", ""),
            victimName=case.get("victimName", ""),
            incidentTime=case.get("incidentTime", ""),
            incidentLocation=case.get("incidentLocation", ""),
            questionLimit=case.get("questionLimit", 12),
        )
        logger.info("  Case 노드 생성")

        # ── Character 노드 ────────────────────────────────────────────────────
        for char in case.get("suspects", []):
            session.run(
                """
                CREATE (ch:Character {
                    caseId: $caseId,
                    characterId: $characterId, name: $name, role: $role,
                    publicPersona: $publicPersona,
                    isCulprit: $isCulprit,
                    secret: $secret
                })
                WITH ch
                MATCH (c:Case {caseId: $caseId})
                CREATE (c)-[:HAS_CHARACTER]->(ch)
                """,
                caseId=case_id,
                characterId=_id(char, "id", "characterId"),
                name=char.get("name", ""),
                role=char.get("role", ""),
                publicPersona=char.get("publicProfile") or char.get("publicPersona", ""),
                isCulprit=bool(char.get("isCulprit", False)),
                secret=char.get("secret", ""),
            )

            # speechStyle JSON 저장 (별도 프로퍼티)
            speech_style = json.dumps(char.get("speechStyle", {}), ensure_ascii=False)
            session.run(
                "MATCH (ch:Character {caseId: $caseId, characterId: $cId}) SET ch.speechStyle = $ss",
                caseId=case_id, cId=_id(char, "id", "characterId"), ss=speech_style,
            )
        logger.info("  Character 노드 %d개 생성", len(case.get("suspects", [])))

        # ── Evidence 노드 ────────────────────────────────────────────────────
        for ev in case.get("evidence", []):
            session.run(
                """
                CREATE (e:Evidence {
                    caseId: $caseId,
                    evidenceId: $evidenceId, name: $name, type: $type,
                    description: $description, foundAt: $foundAt,
                    timeWindow: $timeWindow, initiallyVisible: $initiallyVisible,
                    unlockCondition: $unlockCondition
                })
                WITH e
                MATCH (c:Case {caseId: $caseId})
                CREATE (c)-[:HAS_EVIDENCE]->(e)
                """,
                caseId=case_id,
                evidenceId=_id(ev, "id", "evidenceId"),
                name=ev.get("name", ""),
                type=ev.get("type", ""),
                description=ev.get("description", ""),
                foundAt=ev.get("foundAt", ""),
                timeWindow=ev.get("timeWindow", ""),
                initiallyVisible=bool(ev.get("initiallyVisible", True)),
                unlockCondition=ev.get("unlockCondition", ""),
            )
        logger.info("  Evidence 노드 %d개 생성", len(case.get("evidence", [])))

        # ── Record 노드 ──────────────────────────────────────────────────────
        for rec in case.get("records", []):
            session.run(
                """
                CREATE (r:Record {
                    caseId: $caseId,
                    recordId: $recordId, name: $name, description: $description,
                    timeWindow: $timeWindow, initiallyVisible: $initiallyVisible
                })
                WITH r
                MATCH (c:Case {caseId: $caseId})
                CREATE (c)-[:HAS_RECORD]->(r)
                """,
                caseId=case_id,
                recordId=_id(rec, "id", "recordId"),
                name=rec.get("name", ""),
                description=rec.get("description", ""),
                timeWindow=rec.get("timeWindow", ""),
                initiallyVisible=bool(rec.get("initiallyVisible", True)),
            )
        logger.info("  Record 노드 %d개 생성", len(case.get("records", [])))

        # ── Statement 노드 ────────────────────────────────────────────────────
        for st in case.get("statements", []):
            session.run(
                """
                CREATE (s:Statement {
                    caseId: $caseId,
                    statementId: $statementId, text: $text,
                    questionText: $questionText,
                    timeWindow: $timeWindow, location: $location,
                    initiallyVisible: $initiallyVisible,
                    unlockCondition: $unlockCondition,
                    characterId: $characterId
                })
                WITH s
                MATCH (c:Case {caseId: $caseId})
                CREATE (c)-[:HAS_STATEMENT]->(s)
                """,
                caseId=case_id,
                statementId=_id(st, "id", "statementId"),
                text=st.get("text", ""),
                questionText=st.get("questionText", ""),
                timeWindow=st.get("timeWindow", ""),
                location=st.get("location", ""),
                initiallyVisible=bool(st.get("initiallyVisible", True)),
                unlockCondition=st.get("unlockCondition", ""),
                characterId=st.get("characterId", ""),
            )
            # MADE_STATEMENT 관계
            if st.get("characterId"):
                session.run(
                    """
                    MATCH (ch:Character {caseId: $caseId, characterId: $cId})
                    MATCH (s:Statement {caseId: $caseId, statementId: $sId})
                    CREATE (ch)-[:MADE_STATEMENT]->(s)
                    """,
                    caseId=case_id, cId=st["characterId"], sId=_id(st, "id", "statementId"),
                )
        logger.info("  Statement 노드 %d개 생성", len(case.get("statements", [])))

        # ── Question 노드 ────────────────────────────────────────────────────
        for q in case.get("questions", []):
            session.run(
                """
                CREATE (q:Question {
                    caseId: $caseId,
                    questionId: $questionId, text: $text, answer: $answer,
                    initiallyUnlocked: $initiallyUnlocked,
                    characterId: $characterId,
                    unlockCondition: $unlockCondition
                })
                WITH q
                MATCH (c:Case {caseId: $caseId})
                CREATE (c)-[:HAS_QUESTION]->(q)
                """,
                caseId=case_id,
                questionId=_id(q, "id", "questionId"),
                text=q.get("text", ""),
                answer=q.get("answer", ""),
                initiallyUnlocked=bool(q.get("initiallyUnlocked", True)),
                characterId=q.get("characterId", ""),
                unlockCondition=q.get("unlockCondition", ""),
            )
            # HAS_QUESTION 관계
            if q.get("characterId"):
                session.run(
                    """
                    MATCH (ch:Character {caseId: $caseId, characterId: $cId})
                    MATCH (q:Question {caseId: $caseId, questionId: $qId})
                    MERGE (ch)-[:HAS_QUESTION]->(q)
                    """,
                    caseId=case_id, cId=q["characterId"], qId=_id(q, "id", "questionId"),
                )
            # UNLOCKS 관계 (질문 → 진술/증거/레코드)
            for unlocked_id in q.get("unlocksStatementIds", []):
                session.run(
                    """
                    MATCH (q:Question {caseId: $caseId, questionId: $qId})
                    MATCH (s:Statement {caseId: $caseId, statementId: $sId})
                    CREATE (q)-[:UNLOCKS]->(s)
                    """,
                    caseId=case_id, qId=_id(q, "id", "questionId"), sId=unlocked_id,
                )
            for unlocked_id in q.get("unlocksEvidenceIds", []):
                session.run(
                    """
                    MATCH (q:Question {caseId: $caseId, questionId: $qId})
                    MATCH (e:Evidence {caseId: $caseId, evidenceId: $eId})
                    CREATE (q)-[:UNLOCKS]->(e)
                    """,
                    caseId=case_id, qId=_id(q, "id", "questionId"), eId=unlocked_id,
                )
        logger.info("  Question 노드 %d개 생성", len(case.get("questions", [])))

        # ── Contradiction 노드 ───────────────────────────────────────────────
        for con in case.get("contradictions", []):
            session.run(
                """
                CREATE (con:Contradiction {
                    caseId: $caseId,
                    contradictionId: $contradictionId, title: $title,
                    message: $message, reasonCode: $reasonCode,
                    severity: $severity, pressureDelta: $pressureDelta
                })
                WITH con
                MATCH (c:Case {caseId: $caseId})
                CREATE (c)-[:HAS_CONTRADICTION]->(con)
                """,
                caseId=case_id,
                contradictionId=_id(con, "id", "contradictionId"),
                title=con.get("title", ""),
                message=con.get("message", ""),
                reasonCode=con.get("reasonCode", ""),
                severity=con.get("severity", "supporting"),
                pressureDelta=int(con.get("pressureDelta", 0)),
            )
            # ABOUT 관계
            if con.get("relatedCharacterId"):
                session.run(
                    """
                    MATCH (con:Contradiction {caseId: $caseId, contradictionId: $conId})
                    MATCH (ch:Character {caseId: $caseId, characterId: $cId})
                    CREATE (con)-[:ABOUT]->(ch)
                    """,
                    caseId=case_id, conId=_id(con, "id", "contradictionId"), cId=con["relatedCharacterId"],
                )
            # REQUIRES_STATEMENT 관계
            for st_id in con.get("requiredStatementIds", []):
                session.run(
                    """
                    MATCH (con:Contradiction {caseId: $caseId, contradictionId: $conId})
                    MATCH (s:Statement {caseId: $caseId, statementId: $sId})
                    CREATE (con)-[:REQUIRES_STATEMENT]->(s)
                    """,
                    caseId=case_id, conId=_id(con, "id", "contradictionId"), sId=st_id,
                )
            # REQUIRES_EVIDENCE 관계
            for ev_id in con.get("requiredEvidenceIds", []):
                session.run(
                    """
                    MATCH (con:Contradiction {caseId: $caseId, contradictionId: $conId})
                    MATCH (e:Evidence {caseId: $caseId, evidenceId: $evId})
                    CREATE (con)-[:REQUIRES_EVIDENCE]->(e)
                    """,
                    caseId=case_id, conId=_id(con, "id", "contradictionId"), evId=ev_id,
                )
            # UNLOCKS 관계 (모순 → 진술/증거/질문/레코드)
            # flat unlockedIds 배열 또는 타입별 분리 배열 모두 지원
            flat_ids = con.get("unlockedIds", [])
            all_unlocked_typed = (
                [(uid, "Statement", "statementId") for uid in con.get("unlockedStatementIds", [])]
                + [(uid, "Evidence", "evidenceId") for uid in con.get("unlockedEvidenceIds", [])]
                + [(uid, "Question", "questionId") for uid in con.get("unlockedQuestionIds", [])]
                + [(uid, "Record", "recordId") for uid in con.get("unlockedRecordIds", [])]
            )
            # flat 배열을 prefix로 타입 추론
            _prefix_map = {"st_": "Statement", "ev_": "Evidence", "q_": "Question", "rec_": "Record"}
            for uid in flat_ids:
                for prefix, label in _prefix_map.items():
                    if uid.startswith(prefix):
                        prop_map = {"Statement": "statementId", "Evidence": "evidenceId",
                                    "Question": "questionId", "Record": "recordId"}
                        all_unlocked_typed.append((uid, label, prop_map[label]))
                        break
            all_unlocked = all_unlocked_typed
            for uid, label, prop in all_unlocked:
                session.run(
                    f"""
                    MATCH (con:Contradiction {{caseId: $caseId, contradictionId: $conId}})
                    MATCH (n:{label} {{caseId: $caseId, {prop}: $nId}})
                    CREATE (con)-[:UNLOCKS]->(n)
                    """,
                    caseId=case_id, conId=_id(con, "id", "contradictionId"), nId=uid,
                )
        logger.info("  Contradiction 노드 %d개 생성", len(case.get("contradictions", [])))

        # ── DeceptionArc 노드 ────────────────────────────────────────────────
        deception_graph = case.get("deceptionGraph", {})
        suspect_arcs = deception_graph.get("suspectArcs", []) if isinstance(deception_graph, dict) else []
        for arc in suspect_arcs:
            arc_id = _id(arc, "arcId", "id")
            if not arc_id:
                continue
            stages_json = json.dumps(arc.get("stages", []), ensure_ascii=False)
            session.run(
                """
                CREATE (da:DeceptionArc {
                    caseId: $caseId,
                    arcId: $arcId,
                    suspectId: $suspectId,
                    arcType: $arcType,
                    lieGoal: $lieGoal,
                    publicLie: $publicLie,
                    concealedTruth: $concealedTruth,
                    collapseDisclosure: $collapseDisclosure,
                    collapseQuestionId: $collapseQuestionId,
                    stagesJson: $stagesJson
                })
                WITH da
                MATCH (c:Case {caseId: $caseId})
                CREATE (c)-[:HAS_DECEPTION_ARC]->(da)
                """,
                caseId=case_id,
                arcId=arc_id,
                suspectId=arc.get("suspectId", ""),
                arcType=arc.get("arcType", ""),
                lieGoal=arc.get("lieGoal", ""),
                publicLie=arc.get("publicLie", ""),
                concealedTruth=arc.get("concealedTruth", ""),
                collapseDisclosure=arc.get("collapseDisclosure", ""),
                collapseQuestionId=arc.get("collapseQuestionId", ""),
                stagesJson=stages_json,
            )
            if arc.get("suspectId"):
                session.run(
                    """
                    MATCH (da:DeceptionArc {caseId: $caseId, arcId: $arcId})
                    MATCH (ch:Character {caseId: $caseId, characterId: $suspectId})
                    CREATE (ch)-[:CONCEALS]->(da)
                    """,
                    caseId=case_id,
                    arcId=arc_id,
                    suspectId=arc.get("suspectId"),
                )
            for ev_id in arc.get("evidenceIds", []):
                session.run(
                    """
                    MATCH (da:DeceptionArc {caseId: $caseId, arcId: $arcId})
                    MATCH (e:Evidence {caseId: $caseId, evidenceId: $evidenceId})
                    CREATE (da)-[:SUPPORTED_BY]->(e)
                    """,
                    caseId=case_id,
                    arcId=arc_id,
                    evidenceId=ev_id,
                )
            for st_id in arc.get("statementIds", []):
                session.run(
                    """
                    MATCH (da:DeceptionArc {caseId: $caseId, arcId: $arcId})
                    MATCH (s:Statement {caseId: $caseId, statementId: $statementId})
                    CREATE (da)-[:SUPPORTED_BY]->(s)
                    """,
                    caseId=case_id,
                    arcId=arc_id,
                    statementId=st_id,
                )
            for con_id in arc.get("contradictionIds", []):
                session.run(
                    """
                    MATCH (da:DeceptionArc {caseId: $caseId, arcId: $arcId})
                    MATCH (con:Contradiction {caseId: $caseId, contradictionId: $contradictionId})
                    CREATE (da)-[:PRESSURED_BY]->(con)
                    """,
                    caseId=case_id,
                    arcId=arc_id,
                    contradictionId=con_id,
                )
            if arc.get("collapseQuestionId"):
                session.run(
                    """
                    MATCH (da:DeceptionArc {caseId: $caseId, arcId: $arcId})
                    MATCH (q:Question {caseId: $caseId, questionId: $questionId})
                    CREATE (da)-[:COLLAPSES_VIA]->(q)
                    """,
                    caseId=case_id,
                    arcId=arc_id,
                    questionId=arc.get("collapseQuestionId"),
                )
        logger.info("  DeceptionArc 노드 %d개 생성", len(suspect_arcs))

        # ── TimelineEvent 노드 ───────────────────────────────────────────────
        storyline = case.get("storyline", {})
        timeline_events = storyline.get("timeline", []) if isinstance(storyline, dict) else []
        for te in timeline_events:
            session.run(
                """
                CREATE (t:TimelineEvent {
                    caseId: $caseId,
                    timelineId: $timelineId, time: $time,
                    title: $title, description: $description,
                    sourceType: $sourceType, hidden: $hidden,
                    unlockCondition: $unlockCondition
                })
                WITH t
                MATCH (c:Case {caseId: $caseId})
                CREATE (c)-[:HAS_TIMELINE_EVENT]->(t)
                """,
                caseId=case_id,
                timelineId=te.get("id", ""),
                time=te.get("time", ""),
                title=te.get("title", ""),
                description=te.get("description", ""),
                sourceType=te.get("sourceType", ""),
                hidden=bool(te.get("hidden", False)),
                unlockCondition=te.get("unlockCondition", ""),
            )
        logger.info("  TimelineEvent 노드 %d개 생성", len(timeline_events))

        # ── Relationship 노드 (인물-인물 / 인물-피해자 관계) ────────────────
        for rel in case.get("relations", []):
            session.run(
                """
                CREATE (r:Relationship {
                    caseId: $caseId,
                    relationshipId: $relationshipId,
                    characterId: $characterId,
                    relatedCharacterId: $relatedCharacterId,
                    description: $description,
                    conflict: $conflict,
                    initiallyVisible: $initiallyVisible
                })
                WITH r
                MATCH (c:Case {caseId: $caseId})
                CREATE (c)-[:HAS_RELATIONSHIP]->(r)
                """,
                caseId=case_id,
                relationshipId=_id(rel, "id", "relationshipId"),
                characterId=rel.get("characterId", ""),
                relatedCharacterId=rel.get("relatedCharacterId", ""),
                description=rel.get("description", ""),
                conflict=rel.get("conflict", ""),
                initiallyVisible=bool(rel.get("initiallyVisible", False)),
            )
            # RELATED_TO 엣지: Character → Character/Victim
            if rel.get("characterId") and rel.get("relatedCharacterId"):
                session.run(
                    """
                    MATCH (a:Character {caseId: $caseId, characterId: $charA})
                    OPTIONAL MATCH (b:Character {caseId: $caseId, characterId: $charB})
                    WITH a, b
                    WHERE b IS NOT NULL
                    CREATE (a)-[:RELATED_TO {
                        relationshipId: $relId,
                        description: $desc,
                        initiallyVisible: $vis
                    }]->(b)
                    """,
                    caseId=case_id,
                    charA=rel["characterId"],
                    charB=rel["relatedCharacterId"],
                    relId=_id(rel, "id", "relationshipId"),
                    desc=rel.get("description", ""),
                    vis=bool(rel.get("initiallyVisible", False)),
                )
        logger.info("  Relationship 노드 %d개 생성", len(case.get("relations", [])))

        # ── INVOLVES 엣지 (Evidence → Character) ────────────────────────────
        for ev in case.get("evidence", []):
            ev_id_val = _id(ev, "id", "evidenceId")
            for char_id in ev.get("relatedCharacterIds", []):
                session.run(
                    """
                    MATCH (e:Evidence {caseId: $caseId, evidenceId: $evId})
                    MATCH (ch:Character {caseId: $caseId, characterId: $charId})
                    CREATE (e)-[:INVOLVES]->(ch)
                    """,
                    caseId=case_id,
                    evId=ev_id_val,
                    charId=char_id,
                )
        logger.info("  INVOLVES 엣지 생성 완료")

        # ── Relations (IN_RELATION) ──────────────────────────────────────────
        for rel in case.get("relations", []):
            from_id = rel.get("relatedCharacterId") or rel.get("fromCharacterId") or case.get("victimId", "")
            to_id = rel.get("characterId") or rel.get("toCharacterId", "")
            if from_id and to_id:
                session.run(
                    """
                    MATCH (a:Character {caseId: $caseId, characterId: $fromId})
                    MATCH (b:Character {caseId: $caseId, characterId: $toId})
                    CREATE (a)-[:IN_RELATION {
                        relationshipId: $relId,
                        description: $desc,
                        conflict: $conflict,
                        initiallyVisible: $visible
                    }]->(b)
                    """,
                    caseId=case_id,
                    fromId=from_id,
                    toId=to_id,
                    relId=rel.get("id", ""),
                    desc=rel.get("description", ""),
                    conflict=rel.get("conflict", ""),
                    visible=bool(rel.get("initiallyVisible", True)),
                )
        logger.info("  Relation 엣지 %d개 생성", len(case.get("relations", [])))

        # ── Solution 노드 (내부 전용) ─────────────────────────────────────────
        sol = case.get("solution", {})
        if sol:
            session.run(
                """
                CREATE (sol:Solution {
                    caseId: $caseId,
                    culpritId: $culpritId,
                    motive: $motive,
                    method: $method,
                    requiredContradictionIds: $requiredContradictionIds,
                    requiredEvidenceIds: $requiredEvidenceIds,
                    requiredStatementIds: $requiredStatementIds
                })
                WITH sol
                MATCH (c:Case {caseId: $caseId})
                CREATE (c)-[:HAS_SOLUTION]->(sol)
                """,
                caseId=case_id,
                culpritId=sol.get("culpritId", ""),
                motive=sol.get("motive", ""),
                method=sol.get("method", ""),
                requiredContradictionIds=sol.get("requiredContradictionIds", []),
                requiredEvidenceIds=sol.get("requiredEvidenceIds", []),
                requiredStatementIds=sol.get("requiredStatementIds", []),
            )
            logger.info("  Solution 노드 생성")

    logger.info("마이그레이션 완료: %s", case_id)


def main() -> None:
    try:
        from neo4j import GraphDatabase  # type: ignore[import]
    except ImportError:
        logger.error("neo4j 패키지가 설치되지 않았습니다. pip install neo4j")
        sys.exit(1)

    cases = _load_cases_from_database()
    if not cases:
        logger.error("PostgreSQL cases 테이블에 케이스가 없습니다")
        sys.exit(1)

    logger.info("Neo4j URI: %s", NEO4J_URI)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        logger.info("Neo4j 연결 확인")
        for case in cases:
            case_id = case.get("caseId", "unknown")
            try:
                _run_migration(driver, case)
            except Exception as exc:
                logger.error("케이스 %s 마이그레이션 실패: %s", case_id, exc, exc_info=True)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
