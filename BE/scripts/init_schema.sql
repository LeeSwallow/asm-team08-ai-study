-- Detective Agent PostgreSQL 스키마 초기화
-- 세션 상태 및 이벤트 저장용 테이블

-- ── 기존 테이블 삭제 (재실행 안전) ─────────────────────────────────────────
DROP TABLE IF EXISTS asked_questions CASCADE;
DROP TABLE IF EXISTS bookmarks CASCADE;
DROP TABLE IF EXISTS notes CASCADE;
DROP TABLE IF EXISTS dialogue_log CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;

-- ── 세션 메인 상태 ─────────────────────────────────────────────────────────
CREATE TABLE sessions (
    session_id                    TEXT        PRIMARY KEY,
    case_id                       TEXT        NOT NULL,
    phase                         TEXT        NOT NULL DEFAULT 'investigation',
    remaining_questions           INTEGER     NOT NULL,
    pressure_by_suspect           JSONB       NOT NULL DEFAULT '{}',

    -- 해금된 ID 목록 (각 타입별 배열)
    unlocked_evidence_ids         TEXT[]      NOT NULL DEFAULT '{}',
    unlocked_record_ids           TEXT[]      NOT NULL DEFAULT '{}',
    unlocked_relation_ids         TEXT[]      NOT NULL DEFAULT '{}',
    unlocked_statement_ids        TEXT[]      NOT NULL DEFAULT '{}',
    unlocked_question_ids         TEXT[]      NOT NULL DEFAULT '{}',

    discovered_contradiction_ids  TEXT[]      NOT NULL DEFAULT '{}',
    newly_unlocked_ids            TEXT[]      NOT NULL DEFAULT '{}',
    selected_suspect_id           TEXT,
    accusation                    JSONB,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 대화 로그 ────────────────────────────────────────────────────────────────
CREATE TABLE dialogue_log (
    id          TEXT        PRIMARY KEY,
    session_id  TEXT        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    suspect_id  TEXT,
    question_id TEXT,
    speaker     TEXT        NOT NULL,   -- 'player' | suspect_id
    text        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX dialogue_log_session_id ON dialogue_log(session_id, created_at);

-- ── 수첩 노트 ────────────────────────────────────────────────────────────────
CREATE TABLE notes (
    id                   TEXT        PRIMARY KEY,
    session_id           TEXT        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    text                 TEXT        NOT NULL,
    tags                 TEXT[]      NOT NULL DEFAULT '{}',
    linked_statement_ids TEXT[]      NOT NULL DEFAULT '{}',
    linked_evidence_ids  TEXT[]      NOT NULL DEFAULT '{}',
    linked_record_ids    TEXT[]      NOT NULL DEFAULT '{}',
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── 북마크 ───────────────────────────────────────────────────────────────────
CREATE TABLE bookmarks (
    id          TEXT        PRIMARY KEY,
    session_id  TEXT        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    target_type TEXT        NOT NULL,   -- 'dialogue' | 'statement' | 'evidence' | 'record' | 'relation'
    target_id   TEXT        NOT NULL,
    note        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── SSE 이벤트 스토어 ─────────────────────────────────────────────────────────
CREATE TABLE events (
    id          TEXT        PRIMARY KEY,
    session_id  TEXT        NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    case_id     TEXT        NOT NULL,
    type        TEXT        NOT NULL,
    payload     JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX events_session_created ON events(session_id, created_at);
CREATE INDEX events_type ON events(type);

-- ── 질문 횟수 추적 ────────────────────────────────────────────────────────────
CREATE TABLE asked_questions (
    session_id  TEXT    NOT NULL,
    question_id TEXT    NOT NULL,
    ask_count   INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (session_id, question_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

-- ── updated_at 자동 갱신 트리거 ──────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER notes_updated_at
    BEFORE UPDATE ON notes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
