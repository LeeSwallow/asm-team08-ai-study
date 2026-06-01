export type LogLevel = "info" | "warn" | "error";

export type FrontendLogEvent = {
  service?: "frontend";
  level?: LogLevel;
  sessionId?: string;
  caseId?: string;
  component: string;
  action: string;
  eventId?: string;
  eventType?: string;
  suspectId?: string;
  durationMs?: number;
  connectionState?: "connecting" | "open" | "closed" | "error";
  fallbackUsed?: boolean;
  reason?: string;
  textLength?: number;
};

type LogSink = (event: Required<Pick<FrontendLogEvent, "service">> & FrontendLogEvent & { timestamp: string }) => void;

const defaultSink: LogSink = (event) => {
  const { level = "info" } = event;
  const safeEvent = { ...event, service: "frontend" as const };
  if (level === "error") console.error("[frontend]", safeEvent);
  else if (level === "warn") console.warn("[frontend]", safeEvent);
  else console.info("[frontend]", safeEvent);
};

let sink: LogSink = defaultSink;

export function setLogSink(nextSink: LogSink) {
  sink = nextSink;
}

export function logEvent(event: FrontendLogEvent) {
  sink({ ...event, service: "frontend", timestamp: new Date().toISOString() });
}

export function createActionTimer(base: Omit<FrontendLogEvent, "durationMs">) {
  const startedAt = performance.now();
  return (event: Partial<FrontendLogEvent> = {}) => {
    logEvent({ ...base, ...event, durationMs: Math.round(performance.now() - startedAt) });
  };
}
