import type { AccusationPayload, CaseSummary, GameSessionView } from "./types";
import { askMockQuestion, submitMockAccusation, submitMockContradiction } from "./mockData";
import { normalizeCase, normalizeSession, type BackendCase, type BackendSession } from "./adapters/sessionAdapter";
import { logEvent } from "./utils/observability";
import { sanitizePublicDiagnosticValue } from "./utils/publicDiagnostics";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export function sessionEventsUrl(sessionId: string, lastEventId?: string) {
  const query = lastEventId ? `?lastEventId=${encodeURIComponent(lastEventId)}` : "";
  return `${API_BASE}/api/v1/sessions/${sessionId}/events${query}`;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API ${response.status}: ${path}`);
  }

  return response.json() as Promise<T>;
}

function logApiFallback(action: string, reason: unknown, session?: GameSessionView) {
  logEvent({
    level: "warn",
    component: "ApiClient",
    action,
    sessionId: session?.sessionId,
    caseId: session?.caseId,
    fallbackUsed: true,
    reason: reason instanceof Error ? reason.message : "unknown",
  });
}

function isLocalSession(session: GameSessionView) {
  return session.source === "local" || session.sessionId.startsWith("mock_");
}

function degradedSession(session: GameSessionView, action: string, error: unknown): GameSessionView {
  const reason = sanitizePublicDiagnosticValue(error instanceof Error ? error.message : "unknown") ?? "unknown";
  return {
    ...session,
    runtimeDiagnostics: {
      ...(session.runtimeDiagnostics ?? { source: "api" }),
      source: "api",
      fallbackUsed: true,
      degraded: true,
      blockedReason: reason,
      safety: "api_failure/no_local_progress",
    },
    dialogueLog: [
      ...session.dialogueLog,
      {
        id: `diag_${action}_${Date.now()}`,
        speaker: "system",
        text: `${action}: API 실패로 세션 진행을 변경하지 않았습니다. LOCAL/MOCK 진행은 적용되지 않았습니다.`,
        tag: "DEGRADED",
        important: true,
      },
    ],
  };
}

export async function getCases(): Promise<CaseSummary[]> {
  try {
    const cases = await request<BackendCase[]>("/api/v1/cases");
    return cases.map(normalizeCase);
  } catch (error) {
    logApiFallback("cases_api_failed", error);
    throw error;
  }
}

export async function createSession(caseId: string): Promise<GameSessionView> {
  try {
    return normalizeSession(
      await request<BackendSession>("/api/v1/sessions", {
        method: "POST",
        body: JSON.stringify({ caseId }),
      }),
    );
  } catch (error) {
    logApiFallback("fallback_create_session", error);
    throw error;
  }
}

export async function getSession(sessionId: string, storedSession?: GameSessionView | null): Promise<GameSessionView> {
  if (sessionId.startsWith("mock_")) {
    if (storedSession) return storedSession;
    throw new Error("Local session state is required for local sessions.");
  }

  return normalizeSession(await request<BackendSession>(`/api/v1/sessions/${sessionId}`));
}

export async function askQuestion(
  session: GameSessionView,
  suspectId: string,
  questionText: string,
): Promise<GameSessionView> {
  try {
    return normalizeSession(
      await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/dialogue`, {
        method: "POST",
        body: JSON.stringify({ suspectId, message: questionText }),
      }),
    );
  } catch (error) {
    logApiFallback("fallback_ask_question", error, session);
    return isLocalSession(session) ? askMockQuestion(session, suspectId, questionText) : degradedSession(session, "dialogue", error);
  }
}

export async function submitContradiction(
  session: GameSessionView,
  statementIds: string[],
  evidenceIds: string[],
): Promise<GameSessionView> {
  if (!session.selectedSuspectId) {
    return degradedSession(session, "contradiction", new Error("suspect selection required"));
  }
  try {
    return normalizeSession(
      await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/contradictions`, {
        method: "POST",
        body: JSON.stringify({ suspectId: session.selectedSuspectId, statementIds, evidenceIds }),
      }),
    );
  } catch (error) {
    logApiFallback("fallback_submit_contradiction", error, session);
    return isLocalSession(session) ? submitMockContradiction(session, statementIds, evidenceIds) : degradedSession(session, "contradiction", error);
  }
}

export async function createNote(
  session: GameSessionView,
  text: string,
  linkedStatementIds: string[] = [],
  linkedEvidenceIds: string[] = [],
  linkedRecordIds: string[] = [],
): Promise<GameSessionView> {
  return normalizeSession(
    await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/notes`, {
      method: "POST",
      body: JSON.stringify({
        text,
        tags: ["player-note"],
        linkedStatementIds,
        linkedEvidenceIds,
        linkedRecordIds,
      }),
    }),
  );
}

export async function deleteNote(session: GameSessionView, noteId: string): Promise<GameSessionView> {
  return normalizeSession(
    await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/notes/${noteId}`, {
      method: "DELETE",
    }),
  );
}

export async function updateNote(
  session: GameSessionView,
  noteId: string,
  text: string,
  linkedStatementIds: string[] = [],
  linkedEvidenceIds: string[] = [],
  linkedRecordIds: string[] = [],
): Promise<GameSessionView> {
  return normalizeSession(
    await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/notes/${noteId}`, {
      method: "PUT",
      body: JSON.stringify({ text, tags: ["player-note"], linkedStatementIds, linkedEvidenceIds, linkedRecordIds }),
    }),
  );
}

export async function debugSetPressure(
  session: GameSessionView,
  suspectId: string,
  pressure: number,
): Promise<GameSessionView> {
  return normalizeSession(
    await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/debug/pressure`, {
      method: "POST",
      body: JSON.stringify({ suspectId, pressure }),
    }),
  );
}

export async function debugUnlock(session: GameSessionView, target: "evidence" | "relations" | "timeline" | "notes" | "all"): Promise<GameSessionView> {
  return normalizeSession(
    await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/debug/unlock`, {
      method: "POST",
      body: JSON.stringify({ target }),
    }),
  );
}

export async function submitAccusation(
  session: GameSessionView,
  payload: AccusationPayload,
): Promise<GameSessionView> {
  try {
    return normalizeSession(
      await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/accusation`, {
        method: "POST",
        body: JSON.stringify({
          suspectId: payload.suspectId,
          motive: payload.motive,
          method: payload.method,
          evidenceIds: payload.evidenceIds,
          statementIds: payload.statementIds ?? [],
          contradictionIds: payload.contradictionIds ?? session.foundContradictionIds,
        }),
      }),
    );
  } catch (error) {
    logApiFallback("fallback_submit_accusation", error, session);
    return isLocalSession(session) ? submitMockAccusation(session, payload) : degradedSession(session, "accusation", error);
  }
}
