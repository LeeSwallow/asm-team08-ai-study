import { useCallback, useEffect, useState } from "react";
import { clearAgentLogs, getAgentLogs } from "../agentLoggerApi";
import type { AgentTrace } from "../agentLogger";

export function useAgentLogs() {
  const [traces, setTraces] = useState<AgentTrace[]>([]);
  const [paused, setPaused] = useState(false);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const result = await getAgentLogs();
      setTraces(result.traces);
      setUpdatedAt(result.generatedAt);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Agent logger를 불러오지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }, []);

  const clear = useCallback(async () => {
    try {
      await clearAgentLogs();
      setTraces([]);
      setUpdatedAt(new Date().toISOString());
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Agent logger를 비우지 못했습니다.");
    }
  }, []);

  useEffect(() => {
    void refresh();
    if (paused) return;
    const timer = window.setInterval(() => void refresh(), 1000);
    return () => window.clearInterval(timer);
  }, [paused, refresh]);

  return { traces, paused, busy, error, updatedAt, setPaused, refresh, clear };
}
