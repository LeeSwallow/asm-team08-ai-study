import { useEffect, useMemo, useState } from "react";
import type { AgentTrace, AgentTraceStatus } from "../agentLogger";
import { AgentTraceTimeline } from "../components/AgentTraceTimeline";
import { useAgentLogs } from "../hooks/useAgentLogs";
import { caseListPath } from "../routing";

type AgentLoggerPageProps = {
  onNavigate: (path: string) => void;
};

const statusOptions: Array<{ value: AgentTraceStatus | "all"; label: string }> = [
  { value: "all", label: "전체 상태" },
  { value: "running", label: "실행 중" },
  { value: "completed", label: "완료" },
  { value: "repaired", label: "복구됨" },
  { value: "fallback", label: "Fallback" },
  { value: "warning", label: "주의" },
];

function traceMatches(trace: AgentTrace, search: string, status: AgentTraceStatus | "all") {
  const normalized = search.trim().toLowerCase();
  if (status !== "all" && trace.status !== status) return false;
  if (!normalized) return true;
  return [
    trace.suspectName,
    trace.dialogueMode,
    trace.questionPreview,
    trace.sessionId,
    trace.requestId,
    trace.provider,
  ].some((value) => value?.toLowerCase().includes(normalized));
}

function formatClock(value?: string | null) {
  if (!value) return "--:--:--";
  return new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(new Date(value));
}

export function AgentLoggerPage({ onNavigate }: AgentLoggerPageProps) {
  const { traces, paused, busy, error, updatedAt, setPaused, refresh, clear } = useAgentLogs();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<AgentTraceStatus | "all">("all");
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const filtered = useMemo(() => traces.filter((trace) => traceMatches(trace, search, status)), [search, status, traces]);
  const selected = filtered.find((trace) => trace.traceId === selectedTraceId) ?? filtered[0] ?? null;

  useEffect(() => {
    if (selected && selected.traceId !== selectedTraceId) setSelectedTraceId(selected.traceId);
  }, [selected, selectedTraceId]);

  const nodeCount = traces.reduce((sum, trace) => sum + trace.nodeCount, 0);
  const runningCount = traces.filter((trace) => trace.status === "running").length;
  const attentionCount = traces.filter((trace) => ["warning", "fallback", "repaired"].includes(trace.status)).length;

  return (
    <main className="agent-logger-page">
      <header className="agent-logger-header">
        <div className="agent-logger-title">
          <span className={`agent-live-dot ${paused ? "paused" : ""}`} aria-hidden="true" />
          <div>
            <p>DETECTIVE AGENT OBSERVABILITY</p>
            <h1>Agent Logger</h1>
          </div>
        </div>
        <div className="agent-logger-actions">
          <span>마지막 갱신 {formatClock(updatedAt)}</span>
          <button type="button" onClick={() => setPaused(!paused)}>{paused ? "자동 갱신 시작" : "자동 갱신 일시정지"}</button>
          <button type="button" onClick={() => void refresh()}>지금 갱신</button>
          <button type="button" className="danger" onClick={() => void clear()}>로그 비우기</button>
          <button type="button" onClick={() => onNavigate(caseListPath())}>게임 화면</button>
        </div>
      </header>

      <section className="agent-logger-summary" aria-label="Agent logger 요약">
        <div><span>최근 대화 Trace</span><strong>{traces.length}</strong></div>
        <div><span>기록된 노드</span><strong>{nodeCount}</strong></div>
        <div><span>현재 실행 중</span><strong>{runningCount}</strong></div>
        <div><span>복구·주의 흐름</span><strong>{attentionCount}</strong></div>
      </section>

      <section className="agent-logger-toolbar" aria-label="Trace 필터">
        <label>
          <span>대화·용의자·세션 검색</span>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="예: 한서연, timeline_question" />
        </label>
        <label>
          <span>상태</span>
          <select value={status} onChange={(event) => setStatus(event.target.value as AgentTraceStatus | "all")}>
            {statusOptions.map((option) => <option value={option.value} key={option.value}>{option.label}</option>)}
          </select>
        </label>
        <div className="agent-logger-connection">
          <span className={`agent-live-dot ${error || paused ? "paused" : ""}`} aria-hidden="true" />
          <strong>{error ? "연결 확인 필요" : paused ? "자동 갱신 중지" : "실시간 수신 중"}</strong>
          <small>{error ?? "플레이 중 새 Agent 실행이 자동으로 표시됩니다."}</small>
        </div>
      </section>

      <section className="agent-logger-workspace">
        <aside className="agent-trace-list" aria-label="최근 Agent trace 목록">
          <header><strong>대화 실행 흐름</strong><span>{filtered.length}건</span></header>
          <div>
            {filtered.map((trace) => (
              <button
                type="button"
                key={trace.traceId}
                className={selected?.traceId === trace.traceId ? "active" : ""}
                onClick={() => setSelectedTraceId(trace.traceId)}
              >
                <span className={`agent-status agent-status-${trace.status}`}>{trace.status}</span>
                <strong>{trace.suspectName ?? "시스템"} · {trace.dialogueMode ?? trace.graph}</strong>
                <p>{trace.questionPreview ?? trace.requestId ?? trace.traceId}</p>
                <footer><span>{formatClock(trace.startedAt)}</span><span>{trace.nodeCount} nodes</span><span>{trace.totalLatencyMs} ms</span></footer>
              </button>
            ))}
            {!busy && filtered.length === 0 ? (
              <div className="agent-logger-empty">
                <strong>표시할 Agent trace가 없습니다.</strong>
                <p>게임 화면에서 용의자에게 질문하면 실행 흐름이 여기에 나타납니다.</p>
              </div>
            ) : null}
          </div>
        </aside>
        <div className="agent-trace-stage">
          {selected ? <AgentTraceTimeline trace={selected} /> : (
            <div className="agent-logger-empty">
              <strong>{busy ? "Agent trace를 불러오는 중입니다." : "대화 실행을 기다리고 있습니다."}</strong>
              <p>게임을 플레이하면서 이 화면을 함께 띄우면 Agent별 역할과 실행 순서를 확인할 수 있습니다.</p>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
