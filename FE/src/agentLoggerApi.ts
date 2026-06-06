import type { AgentLogResponse } from "./agentLogger";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

async function agentLoggerRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.detail?.message ?? payload?.detail?.code ?? `API ${response.status}`;
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function getAgentLogs(): Promise<AgentLogResponse> {
  return agentLoggerRequest<AgentLogResponse>("/api/v1/agent-logs?limit=100");
}

export function clearAgentLogs(): Promise<{ cleared: number }> {
  return agentLoggerRequest<{ cleared: number }>("/api/v1/agent-logs", { method: "DELETE" });
}
