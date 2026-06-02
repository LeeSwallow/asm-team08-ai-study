# DB Export Contract

Editor 승인 후 case package에서 DB 산출물을 만든다.

## 1. PostgreSQL data.sql

기존 schema:
- `BE/scripts/init_schema.sql`
- `cases(case_id TEXT PRIMARY KEY, payload JSONB NOT NULL)`
- `sessions`, `events`는 런타임 상태이므로 기본 seed에서는 만들지 않는다.

목표 `data.sql`:

```sql
BEGIN;

INSERT INTO cases (case_id, payload)
VALUES ('case_...', '<case-json>'::jsonb)
ON CONFLICT (case_id) DO UPDATE
SET payload = EXCLUDED.payload;

COMMIT;
```

규칙:
- JSON은 minified 가능하지만 원본 `case.json`도 함께 보관한다.
- private fields는 DB 내부 payload에는 존재할 수 있으나 public projection 테스트가 반드시 필요하다.
- seed는 idempotent 해야 한다.

## 2. Neo4j Cypher

두 가지 방식 지원:
1. `BE/scripts/migrate_case_to_neo4j.py`를 case JSON 다중 파일 입력으로 확장
2. `case_package/neo4j.cypher`를 생성

필수 노드/관계:
- `Case`
- `Character`
- `Evidence`
- `Record`
- `Statement`
- `Question`
- `Contradiction`
- `TimelineEvent`
- `Act`
- `Solution` internal
- `HAS_*`, `MADE_STATEMENT`, `HAS_QUESTION`, `UNLOCKS`, `REQUIRES_STATEMENT`, `REQUIRES_EVIDENCE`, `ABOUT`, `SOURCED_FROM`, `TRIGGERED_BY`

추가 권장:
- `Relationship`
- `Fact`
- `MotiveChain`
- `OpportunityChain`
- `CoverUpAction`
- `FalseLead`

## 3. Validation Gates

컴파일 전:
- all IDs unique
- all refs resolve
- all contradiction required IDs exist
- all unlock IDs exist
- public timeline excludes hidden entries
- each suspect has pressure styles and defense arc
- each suspect has at least one outgoing/incoming usefulness edge

컴파일 후:
- `python -m json.tool case_package/case.json`
- `psql -f BE/scripts/init_schema.sql && psql -f case_package/data.sql` in test DB
- Neo4j import dry run or test container import
- public projection leak scan for forbidden keys/tokens

Forbidden public key/value fragments:
- secret
- solution
- isCulprit
- hiddenTruth
- privateTimeline
- privateMotive
- actualAction
- secretNote
- finalVerdict
