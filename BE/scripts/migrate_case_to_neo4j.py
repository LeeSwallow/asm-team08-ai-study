#!/usr/bin/env python3
"""
case_001.json → Neo4j 마이그레이션 스크립트

사용법:
  cd BE
  BE_NEO4J_URI=bolt://localhost:7687 python scripts/migrate_case_to_neo4j.py

또는 docker 환경에서:
  docker compose exec backend python scripts/migrate_case_to_neo4j.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "cases"
NEO4J_URI = os.getenv("BE_NEO4J_URI") or os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("BE_NEO4J_USER") or os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("BE_NEO4J_PASSWORD") or os.getenv("NEO4J_PASSWORD", "detective_secret")


def _load_case(case_id: str) -> dict:
    path = DATA_DIR / f"{case_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"케이스 파일 없음: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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
                characterId=char["id"],
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
                caseId=case_id, cId=char["id"], ss=speech_style,
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
                evidenceId=ev["id"],
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
                recordId=rec["id"],
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
                statementId=st["id"],
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
                    caseId=case_id, cId=st["characterId"], sId=st["id"],
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
                questionId=q["id"],
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
                    caseId=case_id, cId=q["characterId"], qId=q["id"],
                )
            # UNLOCKS 관계 (질문 → 진술/증거/레코드)
            for unlocked_id in q.get("unlocksStatementIds", []):
                session.run(
                    """
                    MATCH (q:Question {caseId: $caseId, questionId: $qId})
                    MATCH (s:Statement {caseId: $caseId, statementId: $sId})
                    CREATE (q)-[:UNLOCKS]->(s)
                    """,
                    caseId=case_id, qId=q["id"], sId=unlocked_id,
                )
            for unlocked_id in q.get("unlocksEvidenceIds", []):
                session.run(
                    """
                    MATCH (q:Question {caseId: $caseId, questionId: $qId})
                    MATCH (e:Evidence {caseId: $caseId, evidenceId: $eId})
                    CREATE (q)-[:UNLOCKS]->(e)
                    """,
                    caseId=case_id, qId=q["id"], eId=unlocked_id,
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
                contradictionId=con["id"],
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
                    caseId=case_id, conId=con["id"], cId=con["relatedCharacterId"],
                )
            # REQUIRES_STATEMENT 관계
            for st_id in con.get("requiredStatementIds", []):
                session.run(
                    """
                    MATCH (con:Contradiction {caseId: $caseId, contradictionId: $conId})
                    MATCH (s:Statement {caseId: $caseId, statementId: $sId})
                    CREATE (con)-[:REQUIRES_STATEMENT]->(s)
                    """,
                    caseId=case_id, conId=con["id"], sId=st_id,
                )
            # REQUIRES_EVIDENCE 관계
            for ev_id in con.get("requiredEvidenceIds", []):
                session.run(
                    """
                    MATCH (con:Contradiction {caseId: $caseId, contradictionId: $conId})
                    MATCH (e:Evidence {caseId: $caseId, evidenceId: $evId})
                    CREATE (con)-[:REQUIRES_EVIDENCE]->(e)
                    """,
                    caseId=case_id, conId=con["id"], evId=ev_id,
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
                    caseId=case_id, conId=con["id"], nId=uid,
                )
        logger.info("  Contradiction 노드 %d개 생성", len(case.get("contradictions", [])))

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

        # ── Relations (IN_RELATION) ──────────────────────────────────────────
        for rel in case.get("relations", []):
            from_id = rel.get("characterId") or rel.get("fromCharacterId", "")
            to_id = rel.get("relatedCharacterId") or rel.get("toCharacterId", "")
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

    case_files = sorted(DATA_DIR.glob("*.json"))
    if not case_files:
        logger.error("케이스 파일이 없습니다: %s", DATA_DIR)
        sys.exit(1)

    logger.info("Neo4j URI: %s", NEO4J_URI)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        logger.info("Neo4j 연결 확인")
        for path in case_files:
            case_id = path.stem
            try:
                case = _load_case(case_id)
                _run_migration(driver, case)
            except Exception as exc:
                logger.error("케이스 %s 마이그레이션 실패: %s", case_id, exc, exc_info=True)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
