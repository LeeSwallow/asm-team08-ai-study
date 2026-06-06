export type AgentTraceStatus = "running" | "completed" | "repaired" | "fallback" | "warning";

export type AgentTraceEvent = {
  sequence: number;
  recordedAt: string;
  traceId: string;
  requestId?: string | null;
  sessionId?: string | null;
  caseId?: string | null;
  graph?: string | null;
  suspectId?: string | null;
  suspectName?: string | null;
  dialogueMode?: string | null;
  questionPreview?: string | null;
  node: string;
  activity: string;
  provider?: string | null;
  model?: string | null;
  latencyMs: number;
  fallbackUsed: boolean;
  repaired: boolean;
  reason?: string | null;
  proposedEventCount: number;
  level: "info" | "warning";
};

export type AgentTrace = {
  traceId: string;
  requestId?: string | null;
  sessionId?: string | null;
  caseId?: string | null;
  graph?: string | null;
  suspectId?: string | null;
  suspectName?: string | null;
  dialogueMode?: string | null;
  questionPreview?: string | null;
  startedAt: string;
  completedAt?: string | null;
  lastSequence: number;
  status: AgentTraceStatus;
  nodeCount: number;
  totalLatencyMs: number;
  provider?: string | null;
  model?: string | null;
  fallbackUsed: boolean;
  repaired: boolean;
  events: AgentTraceEvent[];
};

export type AgentLogResponse = {
  enabled: boolean;
  generatedAt: string;
  capacity: number;
  traces: AgentTrace[];
};
