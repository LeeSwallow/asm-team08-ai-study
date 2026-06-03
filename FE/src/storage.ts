import type { GameSessionView } from "./types";

const STORAGE_KEY = "detective-agent-session-v1";

type StoredSession = {
  version: 1;
  sessionId: string;
  source: "api";
  savedAt: string;
};

export function loadStoredSession(): GameSessionView | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession;
    return null;
  } catch {
    return null;
  }
}

export function saveStoredSession(session: GameSessionView): void {
  const payload: StoredSession = {
    version: 1,
    sessionId: session.sessionId,
    source: "api",
    savedAt: new Date().toISOString(),
  };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function loadStoredSessionId(): string | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession;
    return parsed.version === 1 ? parsed.sessionId ?? null : null;
  } catch {
    return null;
  }
}

export function clearStoredSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}
