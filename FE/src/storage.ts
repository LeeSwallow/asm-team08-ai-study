import type { GameSessionView } from "./types";

const STORAGE_KEY = "detective-agent-session-v1";

type StoredSession = {
  version: 1;
  sessionId: string;
  source: "api" | "local";
  session?: GameSessionView;
  savedAt: string;
};

export function loadStoredSession(): GameSessionView | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession;
    if (parsed.version !== 1 || parsed.source !== "local") return null;
    return parsed.session ?? null;
  } catch {
    return null;
  }
}

export function saveStoredSession(session: GameSessionView): void {
  const payload: StoredSession = {
    version: 1,
    sessionId: session.sessionId,
    source: session.source === "local" || session.sessionId.startsWith("mock_") ? "local" : "api",
    session: session.source === "local" || session.sessionId.startsWith("mock_") ? session : undefined,
    savedAt: new Date().toISOString(),
  };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

export function loadStoredSessionId(): string | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession;
    return parsed.version === 1 ? parsed.sessionId ?? parsed.session?.sessionId ?? null : null;
  } catch {
    return null;
  }
}

export function clearStoredSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}
