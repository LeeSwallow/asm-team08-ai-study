import type { AccusationPayload, CaseDetail, CaseSummary, GameSessionView, NoteEntry } from "./types";
import { askMockQuestion, submitMockAccusation, submitMockContradiction } from "./mockData";
import { normalizeCase, normalizeSession, type BackendCase, type BackendSession } from "./adapters/sessionAdapter";
import { logEvent } from "./utils/observability";
import { sanitizePublicDiagnosticValue } from "./utils/publicDiagnostics";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export type BookmarkTarget = "dialogue" | "statement" | "evidence" | "record" | "relation";

export type NotesListResponse = {
  sessionId: string;
  caseId: string;
  notes: NoteEntry[];
  notebook?: unknown;
  lastEventId?: string;
};

export type SessionAssistantResponse = Record<string, unknown>;

type BackendCaseDetail = BackendCase & {
  opening?: CaseDetail["opening"];
  storyline?: { publicPremise?: string };
  suspects?: unknown[];
  evidence?: unknown[];
  records?: unknown[];
  statements?: unknown[];
};

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

export async function getCaseDetail(caseId: string): Promise<CaseDetail> {
  const item = await request<BackendCaseDetail>(`/api/v1/cases/${caseId}`);
  const summary = normalizeCase(item);
  return {
    ...summary,
    opening: item.opening,
    publicPremise: item.storyline?.publicPremise,
    suspectCount: item.suspects?.length ?? 0,
    visibleEvidenceCount: item.evidence?.length ?? 0,
    visibleRecordCount: item.records?.length ?? 0,
    visibleStatementCount: item.statements?.length ?? 0,
  };
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
  questionId?: string,
): Promise<GameSessionView> {
  try {
    return normalizeSession(
      await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/dialogue`, {
        method: "POST",
        body: JSON.stringify({ suspectId, message: questionText, questionId }),
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
  const selectedStatements = session.statements.filter((item) => statementIds.includes(item.id));
  const selectedEvidence = session.evidence.filter((item) => evidenceIds.includes(item.id));
  const statementText = selectedStatements.map((item) => item.text).join(" / ");
  const evidenceText = selectedEvidence.map((item) => `${item.title}: ${item.description}`).join(" / ");
  const message = `선택한 진술 "${statementText || statementIds.join(", ")}"은 선택한 증거 "${evidenceText || evidenceIds.join(", ")}"와 모순입니다.`;
  try {
    return normalizeSession(
      await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/dialogue`, {
        method: "POST",
        body: JSON.stringify({ suspectId: session.selectedSuspectId, message }),
      }),
    );
  } catch (error) {
    logApiFallback("fallback_submit_contradiction", error, session);
    return isLocalSession(session) ? submitMockContradiction(session, statementIds, evidenceIds) : degradedSession(session, "contradiction", error);
  }
}

export async function listNotes(session: GameSessionView): Promise<NotesListResponse> {
  return request<NotesListResponse>(`/api/v1/sessions/${session.sessionId}/notes`);
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

export async function createBookmark(
  session: GameSessionView,
  targetType: BookmarkTarget,
  targetId: string,
  note?: string,
): Promise<GameSessionView> {
  return normalizeSession(
    await request<BackendSession>(`/api/v1/sessions/${session.sessionId}/bookmarks`, {
      method: "POST",
      body: JSON.stringify({ targetType, targetId, note }),
    }),
  );
}

export async function summarizeNotes(session: GameSessionView, note = ""): Promise<SessionAssistantResponse> {
  return request<SessionAssistantResponse>(`/api/v1/sessions/${session.sessionId}/notes/summary`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}

export async function getSessionSummary(session: GameSessionView): Promise<SessionAssistantResponse> {
  return request<SessionAssistantResponse>(`/api/v1/sessions/${session.sessionId}/summary`);
}

export async function getSessionHint(session: GameSessionView): Promise<SessionAssistantResponse> {
  return request<SessionAssistantResponse>(`/api/v1/sessions/${session.sessionId}/hint`);
}

export async function getSessionEnding(session: GameSessionView): Promise<SessionAssistantResponse> {
  return request<SessionAssistantResponse>(`/api/v1/sessions/${session.sessionId}/ending`);
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
