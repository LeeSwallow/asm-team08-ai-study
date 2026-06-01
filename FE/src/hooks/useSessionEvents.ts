import { useEffect } from "react";
import { getSession, sessionEventsUrl } from "../api";
import { logEvent } from "../utils/observability";
import type { GameSessionView } from "../types";

export function useSessionEvents(session: GameSessionView | null, onSessionUpdate: (session: GameSessionView) => void) {
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
        eventType = data.type ?? data.eventType ?? eventType;
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
