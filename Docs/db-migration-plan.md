# DB 마이그레이션 및 KnowledgeRetriever 설계 계획

작성일: 2026-06-01  
상태: 미구현 (설계 확정, 구현 대기)

---

## 1. 현재 문제

### 1-1. case_001.json 구조가 Mock-like인 이유

```
CharacterAgent  ← pack.visibleTimeline[:4] 텍스트만, 질문과 무관하게 항상 앞 4개
LightRuleCheck  ← allowedStatement.text 포함 여부 + 금지어 패턴만, 타임라인 일관성 검증 없음
GameMasterAgent ← allowedEventPolicy.relatedEvidenceIds ID 플래그만, 실제 내용 미참조
```

케이스 데이터 자체는 **그래프 구조**다. 모순(Contradiction)은 진술(Statement)과 증거(Evidence)를 엣지로 잇는 노드이고, 해금 체인도 그래프 순회다. 이를 JSON 배열로 관리하면 케이스 작성과 확장이 점점 어려워진다.

```
Contradiction(con_room_claim_vs_entry_log)
  -[:REQUIRES_STATEMENT]→ Statement(st_hanseoyeon_room_2200)  "22:00 방에 있었다"
  -[:REQUIRES_EVIDENCE]→  Evidence(ev_study_entry_log)        "22:02 서재 출입 기록"
  -[:UNLOCKS]→            Statement(st_hanseoyeon_pressure)
  -[:UNLOCKS]→            Question(q_hanseoyeon_after_pressure)
  -[:UNLOCKS]→            Evidence(ev_torn_will)
```

### 1-2. 세션 데이터 문제

현재 세션 상태는 JSON 파일로 관리되어 동시성, 쿼리, 이벤트 스트리밍에 한계가 있다.

---

## 2. 목표 아키텍처

```
┌─────────────────────────────┐    ┌──────────────────────────────┐
│  Neo4j (케이스 지식 그래프)    │    │  PostgreSQL (세션/이벤트 상태)  │
│                             │    │                              │
│  Character, Statement,      │    │  sessions, events,           │
│  Evidence, Record,          │    │  dialogue_logs, notes        │
│  Contradiction, Question,   │    │                              │
│  TimelineEvent, Act         │    │  (선택) pgvector 익스텐션으로  │
│                             │    │  임베딩 컬럼 추가 가능         │
│  + Neo4j 5.x Vector Index   │    │                              │
│    (Statement/Evidence 임베딩) │    │                              │
└─────────────────────────────┘    └──────────────────────────────┘
            ↑                                    ↑
            │                                    │
     KnowledgeRetriever                  SessionRepository
     (Cypher 쿼리 기반)                   (SQL 기반)
            │
     CharacterAgent
     LightRuleCheck
     GameMasterAgent
```

---

## 3. Neo4j 스키마

### 3-1. 노드

```cypher
// 케이스 루트
(:Case {
  caseId:            STRING,   // 'case_001'
  sceneId:           STRING,
  title:             STRING,
  summary:           STRING,
  victimId:          STRING,
  victimName:        STRING,
  incidentTime:      STRING,   // '22:00~22:10'
  incidentLocation:  STRING,
  questionLimit:     INTEGER
})

// 용의자/피해자
(:Character {
  characterId:   STRING,   // 'char_hanseoyeon'
  name:          STRING,
  role:          STRING,   // '조카', '의사' 등
  publicProfile: STRING,
  // secret, isCulprit → 절대 노출 금지. Neo4j에는 저장하되 공개 API에서 제거
  isCulprit:     BOOLEAN,  // 내부 전용 플래그
  secret:        STRING    // 내부 전용
})

// 용의자 진술
(:Statement {
  statementId:      STRING,   // 'st_hanseoyeon_room_2200'
  text:             STRING,   // '저는 22:00에 제 방에 있었어요.'
  questionText:     STRING,   // '22:00에 어디 있었나요?'
  timeWindow:       STRING,   // '22:00'
  location:         STRING,   // '자기 방'
  initiallyVisible: BOOLEAN,
  embedding:        LIST<FLOAT>  // Neo4j Vector Index용 (추후 추가)
})

// 물적 증거
(:Evidence {
  evidenceId:       STRING,   // 'ev_study_entry_log'
  name:             STRING,
  type:             STRING,   // 'physical', 'document'
  description:      STRING,
  foundAt:          STRING,
  timeWindow:       STRING,
  reliability:      FLOAT,    // 0.0~1.0
  initiallyVisible: BOOLEAN,
  embedding:        LIST<FLOAT>  // 추후 추가
})

// 기록/문서 증거
(:Record {
  recordId:         STRING,
  name:             STRING,
  description:      STRING,
  timeWindow:       STRING,
  initiallyVisible: BOOLEAN
})

// 모순 (Statement + Evidence 충돌 지점)
(:Contradiction {
  contradictionId: STRING,   // 'con_room_claim_vs_entry_log'
  title:           STRING,
  message:         STRING,   // 공개 판정 메시지
  reasonCode:      STRING,   // 'time_location_conflict'
  severity:        STRING,   // 'core', 'supporting'
  pressureDelta:   INTEGER
})

// 질문
(:Question {
  questionId:        STRING,
  text:              STRING,
  answer:            STRING,
  initiallyUnlocked: BOOLEAN,
  embedding:         LIST<FLOAT>  // 추후 추가
})

// 타임라인 이벤트 (공개 사건 타임라인)
(:TimelineEvent {
  timelineId:      STRING,
  time:            STRING,   // '22:02'
  title:           STRING,
  description:     STRING,
  sourceType:      STRING,   // 'evidence', 'statement'
  hidden:          BOOLEAN,
  unlockCondition: STRING    // 조건부 공개
})

// 스토리 막
(:Act {
  actId:          STRING,   // 'alibi_collection'
  title:          STRING,
  objective:      STRING,
  entryCondition: STRING    // 'start', contradiction ID, etc.
})

// 해결책 (내부 전용 - 공개 API 노출 금지)
(:Solution {
  caseId:                    STRING,
  culpritId:                 STRING,
  motive:                    STRING,
  method:                    STRING,
  requiredContradictionIds:  LIST<STRING>,
  requiredEvidenceIds:       LIST<STRING>,
  requiredStatementIds:      LIST<STRING>,
  endings:                   MAP   // {correct, partial, wrong}
})
```

### 3-2. 관계

```cypher
// 캐릭터 → 진술
(Character)-[:MADE_STATEMENT]->(Statement)

// 캐릭터 → 질문
(Character)-[:HAS_QUESTION]->(Question)

// 캐릭터 → 캐릭터 (관계도)
(Character)-[:IN_RELATION {
  relationshipId:   STRING,
  description:      STRING,
  conflict:         STRING,
  initiallyVisible: BOOLEAN
}]->(Character)

// 질문 해금 체인
(Question)-[:UNLOCKS]->(Statement)
(Question)-[:UNLOCKS]->(Evidence)
(Question)-[:UNLOCKS]->(Record)
(Question)-[:UNLOCKS]->(Question)

// 모순 요건
(Contradiction)-[:REQUIRES_STATEMENT]->(Statement)
(Contradiction)-[:REQUIRES_EVIDENCE]->(Evidence)
(Contradiction)-[:ABOUT]->(Character)

// 모순 해금 체인
(Contradiction)-[:UNLOCKS]->(Statement)
(Contradiction)-[:UNLOCKS]->(Evidence)
(Contradiction)-[:UNLOCKS]->(Question)
(Contradiction)-[:UNLOCKS]->(Record)

// 타임라인 출처
(TimelineEvent)-[:SOURCED_FROM]->(Evidence)
(TimelineEvent)-[:SOURCED_FROM]->(Statement)

// 스토리 막 진입 조건
(Act)-[:TRIGGERED_BY]->(Contradiction)

// 케이스 루트
(Case)-[:HAS_CHARACTER]->(Character)
(Case)-[:HAS_EVIDENCE]->(Evidence)
(Case)-[:HAS_RECORD]->(Record)
(Case)-[:HAS_CONTRADICTION]->(Contradiction)
(Case)-[:HAS_SOLUTION]->(Solution)
(Case)-[:HAS_ACT]->(Act)
(Case)-[:HAS_TIMELINE_EVENT]->(TimelineEvent)
```

---

## 4. PostgreSQL 스키마 (세션 상태)

```sql
-- 세션 메인 상태
CREATE TABLE sessions (
    session_id          TEXT        PRIMARY KEY,
    case_id             TEXT        NOT NULL,
    phase               TEXT        NOT NULL DEFAULT 'investigation',
    remaining_questions INTEGER     NOT NULL,
    pressure_by_suspect JSONB       NOT NULL DEFAULT '{}',
    unlocked_ids        JSONB       NOT NULL DEFAULT '[]',  -- 모든 해금 ID 통합
    discovered_contradiction_ids TEXT[] NOT NULL DEFAULT '{}',
    selected_suspect_id TEXT,
    accusation          JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 대화 로그
CREATE TABLE dialogue_log (
    id          TEXT        PRIMARY KEY,
    session_id  TEXT        NOT NULL REFERENCES sessions(session_id),
    suspect_id  TEXT,
    question_id TEXT,
    speaker     TEXT        NOT NULL,
    text        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 노트
CREATE TABLE notes (
    id                    TEXT        PRIMARY KEY,
    session_id            TEXT        NOT NULL REFERENCES sessions(session_id),
    text                  TEXT        NOT NULL,
    tags                  TEXT[]      NOT NULL DEFAULT '{}',
    linked_statement_ids  TEXT[]      NOT NULL DEFAULT '{}',
    linked_evidence_ids   TEXT[]      NOT NULL DEFAULT '{}',
    linked_record_ids     TEXT[]      NOT NULL DEFAULT '{}',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 북마크
CREATE TABLE bookmarks (
    id          TEXT        PRIMARY KEY,
    session_id  TEXT        NOT NULL REFERENCES sessions(session_id),
    target_type TEXT        NOT NULL,
    target_id   TEXT        NOT NULL,
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- SSE 이벤트 스토어
CREATE TABLE events (
    id          TEXT        PRIMARY KEY,
    session_id  TEXT        NOT NULL REFERENCES sessions(session_id),
    case_id     TEXT        NOT NULL,
    type        TEXT        NOT NULL,
    payload     JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX events_session_id_created_at ON events(session_id, created_at);

-- 질문 사용 횟수
CREATE TABLE asked_questions (
    session_id  TEXT    NOT NULL,
    question_id TEXT    NOT NULL,
    ask_count   INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (session_id, question_id)
);
```

---

## 5. KnowledgeRetriever 설계

### 5-1. 인터페이스

```python
@dataclass
class QuestionEntities:
    time_expressions: list[str]    # ['22:00', '22시', '밤']
    location_terms:   list[str]    # ['서재', '방', '복도']
    evidence_terms:   list[str]    # ['와인잔', '약', '출입기록']
    suspect_names:    list[str]    # ['한서연', '박민규']

@dataclass
class RetrievedContext:
    matched_timeline_events: list[dict]    # 질문 시간대와 겹치는 타임라인
    matched_evidence:        list[dict]    # 질문에 언급된 증거
    matched_statements:      list[dict]    # 관련 진술 (시간/장소 매칭)
    related_contradictions:  list[dict]    # 위 증거/진술을 포함하는 모순
    alibi_summary:           str | None   # "22:00 자기 방 (공개 알리바이)"
    fact_boundary:           str          # allowedStatement.text
    retrieval_debug:         dict         # 어떤 엔티티로 매칭됐는지 (로그용)

class KnowledgeRetriever:
    def __init__(self, neo4j_driver): ...
    def retrieve(self, payload: DialogueRequest) -> RetrievedContext: ...
```

### 5-2. 핵심 Cypher 쿼리

```cypher
-- ① 용의자 + 시간대 → 알리바이 진술 + 충돌 증거
MATCH (c:Character {characterId: $suspectId})-[:MADE_STATEMENT]->(s:Statement)
WHERE s.timeWindow IN $timeExpressions
  AND NOT s.statementId IN $hiddenStatementIds
OPTIONAL MATCH (con:Contradiction)-[:REQUIRES_STATEMENT]->(s),
               (con)-[:REQUIRES_EVIDENCE]->(e:Evidence)
WHERE NOT con.contradictionId IN $notYetVisibleContradictions
RETURN s, collect(DISTINCT con) AS contradictions, collect(DISTINCT e) AS evidence

-- ② 질문에 언급된 증거 이름 → 관련 모순 전체 탐색
MATCH (e:Evidence)
WHERE any(term IN $evidenceTerms WHERE toLower(e.name) CONTAINS term
          OR toLower(e.description) CONTAINS term)
  AND e.evidenceId IN $unlockedEvidenceIds
OPTIONAL MATCH (con:Contradiction)-[:REQUIRES_EVIDENCE]->(e),
               (con)-[:REQUIRES_STATEMENT]->(s:Statement)
RETURN e, collect(DISTINCT con) AS contradictions, collect(DISTINCT s) AS statements

-- ③ 공개 타임라인에서 해당 시간대 이벤트 조회
MATCH (t:TimelineEvent)
WHERE t.hidden = false
  AND t.time IN $timeExpressions
OPTIONAL MATCH (t)-[:SOURCED_FROM]->(src)
RETURN t, collect(src) AS sources

-- ④ 특정 모순 발견 시 해금되는 모든 것 (unlock chain)
MATCH (con:Contradiction {contradictionId: $contradictionId})-[:UNLOCKS]->(unlocked)
RETURN labels(unlocked)[0] AS nodeType, unlocked

-- ⑤ 용의자 공개 지식 패키지 빌드 (CharacterAgent용)
MATCH (c:Character {characterId: $suspectId})
OPTIONAL MATCH (c)-[:MADE_STATEMENT]->(s:Statement)
  WHERE s.statementId IN $unlockedStatementIds
OPTIONAL MATCH (c)-[:HAS_QUESTION]->(q:Question)
  WHERE q.questionId IN $unlockedQuestionIds
OPTIONAL MATCH (c)-[:IN_RELATION]->(other:Character)
RETURN c, collect(DISTINCT s) AS statements,
       collect(DISTINCT q) AS questions,
       collect(DISTINCT other) AS relatedCharacters
```

### 5-3. 그래프에서의 위치

```python
# dialogue_graph.py
def run_dialogue_graph(payload: DialogueRequest) -> DialogueResponse:
    state = run_langgraph_or_pipeline(
        {"payload": payload},
        [
            ("load_context",        load_context),
            ("validate_scope",      validate_scope),
            ("KnowledgeRetriever",  retrieve_context),   # ← 신규
            ("CharacterAgent",      generate_response),
            ("LightRuleCheck",      guard_response),
            ("GameMasterAgent",     propose_events),
            ("format_response",     format_response),
        ],
    )
```

`retrieve_context` 노드:
```python
def retrieve_context(state: dict) -> dict:
    payload: DialogueRequest = state["payload"]
    retrieved = retriever.retrieve(payload)   # Cypher 쿼리 실행
    return {"retrieved_context": retrieved}
```

이후 `CharacterAgent`가 `state["retrieved_context"]`로 구조화된 데이터에 접근:
- 현재: `pack.visibleTimeline[:4]` (고정 슬라이싱)
- 개선 후: `retrieved.matched_timeline_events` (질문 관련 이벤트만)

`LightRuleCheck`가 타임라인 일관성 검증:
- 현재: `allowedStatement.text` 포함 여부만
- 개선 후: 캐릭터의 `claimedLocation`이 공개 타임라인과 일치하는지 확인

---

## 6. 구현 단계

### Phase 1 — 인프라 및 마이그레이션

- [ ] `docker-compose.yml`에 Neo4j, PostgreSQL 서비스 추가
- [ ] `BE/scripts/migrate_case_to_neo4j.py` — case_001.json → Cypher `CREATE` 스크립트 생성
- [ ] `BE/scripts/migrate_sessions_to_pg.py` — 기존 JSON 세션 파일 → PostgreSQL
- [ ] BE `pyproject.toml`에 `neo4j`, `psycopg[binary]` 의존성 추가
- [ ] `BE/app/infra/case_graph.py` — Neo4j 드라이버 래퍼 및 연결 관리
- [ ] `BE/app/infra/session_db.py` — PostgreSQL asyncpg/psycopg 세션 저장소

### Phase 2 — 저장소 교체

- [ ] `CaseRepository` → Neo4j 기반으로 교체 (`get_case()` → Cypher 쿼리)
- [ ] `SessionRepository` → PostgreSQL 기반으로 교체
- [ ] `EventRepository` → PostgreSQL `events` 테이블 기반으로 교체
- [ ] 기존 스모크 테스트 통과 확인 (인터페이스 동일 유지)

### Phase 3 — KnowledgeRetriever 구현

- [ ] `BE/app/ai_engine/application/knowledge_retriever.py` 신규 작성
- [ ] `QuestionEntities`, `RetrievedContext` 데이터 클래스 정의
- [ ] 엔티티 추출: 시간 표현, 장소 어휘, 증거 명칭 (기존 `guard.py` 패턴 재활용)
- [ ] 5개 핵심 Cypher 쿼리 구현
- [ ] `dialogue_graph.py`에 `retrieve_context` 노드 추가
- [ ] `CharacterAgent`가 `retrieved_context`로 프롬프트 컨텍스트 빌드
- [ ] `LightRuleCheck`에 타임라인 일관성 검증 추가 (공개 데이터 기준)

### Phase 4 — 임베딩 검색 추가 (선택)

- [ ] Statement/Evidence/Question 텍스트 → 임베딩 생성 (Solar Embedding API 또는 OpenAI)
- [ ] Neo4j Vector Index 생성
- [ ] KnowledgeRetriever에 벡터 유사도 검색 쿼리 추가
- [ ] 키워드 매칭 + 벡터 검색 하이브리드 랭킹

### Phase 5 — case_001 구체화

- [ ] 캐릭터별 개인 타임라인 확장 (현재 global timeline만 있음)
- [ ] 진술 수 확장 (현재 9개 → 목표 20개 이상)
- [ ] 증거 수 확장 (현재 8개 → 목표 15개 이상)
- [ ] 모순 경로 추가 (현재 4개 → 목표 6~8개, 핵심 2개 + 보조 4~6개)
- [ ] 각 용의자별 서브플롯 진술 추가
- [ ] Neo4j에서 직접 Cypher로 데이터 작성 (JSON 대비 구조 직관적)

---

## 7. docker-compose 변경안

```yaml
services:
  neo4j:
    image: neo4j:5.x
    environment:
      NEO4J_AUTH: neo4j/detective_secret
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
    ports:
      - "7474:7474"   # Browser
      - "7687:7687"   # Bolt
    volumes:
      - neo4j_data:/data

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB:       detective_db
      POSTGRES_USER:     detective
      POSTGRES_PASSWORD: detective_secret
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build:
      context: ./BE
    env_file:
      - ./.secret/.env
    environment:
      AI_LLM_PROVIDER:      upstage
      AI_UPSTAGE_MODEL_NAME: solar-pro
      AI_MODEL_NAME:         gpt-4o-mini
      BE_NEO4J_URI:          bolt://neo4j:7687
      BE_NEO4J_USER:         neo4j
      BE_NEO4J_PASSWORD:     detective_secret
      BE_DATABASE_URL:       postgresql://detective:detective_secret@postgres:5432/detective_db
      BE_DEBUG_TOOLS_ENABLED: "true"
    depends_on:
      - neo4j
      - postgres

  frontend:
    ...  # 변경 없음

volumes:
  neo4j_data:
  postgres_data:
  backend-sessions:  # Phase 2 완료 후 제거
```

---

## 8. 결정 근거 요약

| 항목 | 현재 | 변경 후 |
|---|---|---|
| 케이스 데이터 저장 | JSON 파일 | Neo4j 그래프 |
| 세션 상태 저장 | JSON 파일 | PostgreSQL |
| 모순 조회 | in-memory 순회 | Cypher 그래프 순회 |
| 해금 체인 조회 | in-memory 순회 | Cypher UNLOCKS 엣지 순회 |
| KnowledgeRetriever | payload 텍스트 파싱 | Cypher 구조 쿼리 |
| 임베딩 검색 | 없음 | Neo4j Vector Index (Phase 4) |
| 케이스 작성 | JSON 배열 편집 | Cypher 노드/엣지 추가 |

케이스 데이터는 본질적으로 **속성 그래프**다. 모순, 해금 체인, 타임라인 출처 추적이 모두 그래프 순회로 자연스럽게 표현되며, KnowledgeRetriever의 핵심 쿼리들이 Cypher에서 SQL의 재귀 CTE보다 훨씬 읽기 쉽고 유지보수하기 좋다.
