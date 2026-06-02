-- Detective Agent PostgreSQL schema
-- Runtime persistence is database-only. Case, session, and event aggregates are
-- stored as JSONB payloads and validated at the application boundary.

DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS sessions CASCADE;
DROP TABLE IF EXISTS cases CASCADE;

CREATE TABLE cases (
    case_id TEXT PRIMARY KEY,
    payload JSONB NOT NULL
);

CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE RESTRICT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX sessions_case_id ON sessions(case_id);

CREATE TABLE events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE RESTRICT,
    type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX events_session_id ON events(session_id);
CREATE INDEX events_case_id ON events(case_id);
CREATE INDEX events_type ON events(type);
CREATE INDEX events_session_created ON events(session_id, created_at, id);

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
