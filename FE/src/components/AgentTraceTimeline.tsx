import type { AgentTrace, AgentTraceEvent } from "../agentLogger";

function eventStatus(event: AgentTraceEvent) {
  if (event.fallbackUsed) return "fallback";
  if (event.level === "warning") return "warning";
  if (event.repaired) return "repaired";
  return "completed";
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    fractionalSecondDigits: 3,
    hour12: false,
  }).format(new Date(value));
}

export function AgentTraceTimeline({ trace }: { trace: AgentTrace }) {
  return (
    <section className="agent-trace-detail" aria-label="선택한 Agent trace">
      <header className="agent-situation">
        <div>
          <span>대화 상황</span>
          <strong>{trace.suspectName ?? "시스템"} · {trace.dialogueMode ?? trace.graph ?? "agent flow"}</strong>
          <p>{trace.questionPreview ?? "대화 입력 미리보기가 없는 실행입니다."}</p>
        </div>
        <dl>
          <div><dt>요청</dt><dd>{trace.requestId ?? trace.traceId}</dd></div>
          <div><dt>Provider</dt><dd>{trace.provider ?? "deterministic"}</dd></div>
          <div><dt>총 노드</dt><dd>{trace.nodeCount}</dd></div>
          <div><dt>누적 시간</dt><dd>{trace.totalLatencyMs.toLocaleString()} ms</dd></div>
        </dl>
      </header>

      <ol className="agent-node-timeline">
        {trace.events.map((event, index) => {
          const status = eventStatus(event);
          return (
            <li key={event.sequence} className={`agent-node-step status-${status}`}>
              <div className="agent-step-rail" aria-hidden="true">
                <span>{String(index + 1).padStart(2, "0")}</span>
              </div>
              <div className="agent-step-copy">
                <header>
                  <div>
                    <strong>{event.node}</strong>
                    <span className={`agent-status agent-status-${status}`}>{status}</span>
                  </div>
                  <time>{formatTime(event.recordedAt)}</time>
                </header>
                <p>{event.activity}</p>
                <footer>
                  <span>{event.latencyMs.toLocaleString()} ms</span>
                  <span>{event.provider ?? "deterministic"}{event.model ? ` / ${event.model}` : ""}</span>
                  {event.proposedEventCount ? <span>이벤트 제안 {event.proposedEventCount}건</span> : null}
                  {event.reason ? <span className="agent-step-reason">{event.reason}</span> : null}
                </footer>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
