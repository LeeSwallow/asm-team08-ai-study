import { useEffect } from "react";
import { getSession, sessionEventsUrl } from "../api";
import { logEvent } from "../utils/observability";
import type { GameEventFeedItem, GameSessionView } from "../types";

function feedItemFromSse(event: MessageEvent): GameEventFeedItem | null {
  try {
    const data = JSON.parse(event.data) as { id?: string; type?: string; eventType?: string; createdAt?: string; payload?: Record<string, unknown> };
    const type = data.type ?? data.eventType ?? event.type;
    const payload = data.payload ?? {};
    const text = typeof payload.text === "string" ? payload.text : undefined;
    const contradictionId = typeof payload.contradictionId === "string" ? payload.contradictionId : undefined;
    const evidenceId = typeof payload.evidenceId === "string" ? payload.evidenceId : undefined;
    const sourceId = typeof payload.sourceId === "string" ? payload.sourceId : undefined;
    const titles: Record<string, string> = {
      NOTE_FACT_ADDED: "단서 기록",
      NOTE_CONTRADICTION_CANDIDATE_ADDED: "모순 후보",
      EVIDENCE_UNLOCKED: "증거 해금",
      TIMELINE_EVENT_REVEALED: "타임라인 갱신",
      VISUAL_STATE_CHANGED: "심문 반응",
      BOOKMARK_SUGGESTED: "북마크 제안",
    };
    return {
      id: data.id ?? event.lastEventId ?? `${type}_${Date.now()}`,
      type,
      title: titles[type] ?? type,
      message: text ?? contradictionId ?? evidenceId ?? sourceId ?? type,
      createdAt: data.createdAt,
      payload,
    };
  } catch {
    return null;
  }
}

export function useSessionEvents(
  session: GameSessionView | null,
  onSessionUpdate: (session: GameSessionView) => void,
  onFeedEvent?: (event: GameEventFeedItem) => void,
) {
  useEffect(() => {
    if (!session) return;
    if (session.source === "local" || session.sessionId.startsWith("mock_")) {
      logEvent({
        level: "warn",
        component: "SessionEvents",
        action: "sse_skipped_for_local_fallback",
        sessionId: session.sessionId,
        caseId: session.caseId,
        connectionState: "closed",
        fallbackUsed: true,
      });
      return;
    }

    let closed = false;
    let refreshQueued = false;
    const eventSource = new EventSource(sessionEventsUrl(session.sessionId, session.runtimeDiagnostics?.lastEventId));

    logEvent({
      level: "info",
      component: "SessionEvents",
      action: "sse_open",
      sessionId: session.sessionId,
      caseId: session.caseId,
      connectionState: "connecting",
    });

    eventSource.onopen = () => {
      logEvent({
        level: "info",
        component: "SessionEvents",
        action: "sse_connected",
        sessionId: session.sessionId,
        caseId: session.caseId,
        connectionState: "open",
      });
    };

    const handleEvent = (event: MessageEvent) => {
      let eventType = "message";
      try {
        const data = JSON.parse(event.data) as { id?: string; type?: string; eventType?: string };
        eventType = data.type ?? data.eventType ?? event.type ?? eventType;
        const feedItem = feedItemFromSse(event);
        if (feedItem) onFeedEvent?.(feedItem);
        logEvent({
          level: "info",
          component: "SessionEvents",
          action: "sse_event_received",
          sessionId: session.sessionId,
          caseId: session.caseId,
          eventId: data.id ?? event.lastEventId,
          eventType,
          connectionState: "open",
        });
      } catch (error) {
        logEvent({
          level: "error",
          component: "SessionEvents",
          action: "sse_parse_failure",
          sessionId: session.sessionId,
          caseId: session.caseId,
          eventId: event.lastEventId,
          eventType,
          connectionState: "open",
          reason: error instanceof Error ? error.message : "unknown",
        });
      }

      if (refreshQueued) return;
      refreshQueued = true;
      window.setTimeout(() => {
        if (closed) return;
        getSession(session.sessionId, session)
          .then(onSessionUpdate)
          .catch((error: unknown) => {
            logEvent({
              level: "error",
              component: "SessionEvents",
              action: "sse_session_refresh_failed",
              sessionId: session.sessionId,
              caseId: session.caseId,
              eventId: event.lastEventId,
              eventType,
              connectionState: "open",
              reason: error instanceof Error ? error.message : "unknown",
            });
          })
          .finally(() => {
            refreshQueued = false;
          });
      }, 120);
    };
    eventSource.onmessage = handleEvent;
    [
      "NOTE_FACT_ADDED",
      "NOTE_CONTRADICTION_CANDIDATE_ADDED",
      "NOTE_CREATED",
      "NOTE_UPDATED",
      "NOTE_DELETED",
      "EVIDENCE_UNLOCKED",
      "TIMELINE_EVENT_REVEALED",
      "TENSION_CHANGED",
      "VISUAL_STATE_CHANGED",
      "BOOKMARK_SUGGESTED",
      "DEBUG_SESSION_UPDATED",
    ].forEach((eventName) => eventSource.addEventListener(eventName, handleEvent));

    eventSource.onerror = () => {
      logEvent({
        level: "warn",
        component: "SessionEvents",
        action: "sse_closed_or_retrying",
        sessionId: session.sessionId,
        caseId: session.caseId,
        connectionState: "error",
      });
    };

    return () => {
      closed = true;
      eventSource.close();
      logEvent({
        level: "warn",
        component: "SessionEvents",
        action: "sse_closed",
        sessionId: session.sessionId,
        caseId: session.caseId,
        connectionState: "closed",
      });
    };
  }, [session?.sessionId]);
}
