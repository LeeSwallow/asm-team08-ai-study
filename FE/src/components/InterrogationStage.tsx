import { backgroundAsset, suspectAsset } from "../constants/presentation";
import type { DialogueLogItem, DialogueRuntimeDiagnostics, GameEventFeedItem, Suspect, VisualState } from "../types";

type InterrogationStageProps = {
  selectedSuspect?: Suspect;
  suspects: Suspect[];
  latestAnswer: string;
  dialogueLog: DialogueLogItem[];
  eventFeed: GameEventFeedItem[];
  draftQuestion: string;
  questionHint?: string;
  busy: boolean;
  remainingQuestions: number;
  visualState?: VisualState;
  runtimeDiagnostics?: DialogueRuntimeDiagnostics;
  onDraftQuestionChange: (value: string) => void;
  onSubmitQuestion: () => void;
  onPresentEvidence: () => void;
};

export function InterrogationStage({
  selectedSuspect,
  suspects,
  latestAnswer,
  dialogueLog,
  eventFeed,
  draftQuestion,
  questionHint,
  busy,
  remainingQuestions,
  visualState,
  runtimeDiagnostics,
  onDraftQuestionChange,
  onSubmitQuestion,
  onPresentEvidence,
}: InterrogationStageProps) {
  const tensionLevel = visualState?.tensionLevel ?? "unknown";
  const visualAppliesToSelected = Boolean(
    selectedSuspect && (!visualState?.suspectId || visualState.suspectId === selectedSuspect.id),
  );
  const expression = visualAppliesToSelected ? (visualState?.expression ?? selectedSuspect?.expression ?? "neutral") : (selectedSuspect?.expression ?? "neutral");
  const emotion = visualAppliesToSelected ? (visualState?.emotionalState ?? selectedSuspect?.emotion ?? "guarded") : (selectedSuspect?.emotion ?? "guarded");
  const pressure = selectedSuspect?.pressure ?? 0;
  const stageBackground = backgroundAsset(visualState?.backgroundId);
  const diagnosticTone = runtimeDiagnostics?.source === "local" || runtimeDiagnostics?.fallbackUsed ? "fallback" : "api";
  const diagnosticLabel = (value: string | number | null | undefined, fallback: string) => {
    const missing = value === null || value === undefined || value === "";
    return <span className={missing ? "diagnostic-missing" : undefined}>{missing ? fallback : value}</span>;
  };
  const matchedPublicRefs = [
    runtimeDiagnostics?.matchedQuestionId,
    ...(runtimeDiagnostics?.matchedEvidenceIds ?? []),
    ...(runtimeDiagnostics?.matchedStatementIds ?? []),
    ...(runtimeDiagnostics?.matchedRecordIds ?? []),
    ...(runtimeDiagnostics?.matchedRefs ?? []),
  ].filter((item): item is string => Boolean(item));
  const proposedCount = runtimeDiagnostics?.proposedEventsCount;
  const appliedCount = runtimeDiagnostics?.appliedEventsCount;
  const noProgressEvents = proposedCount === 0 && appliedCount === 0;
  const suspectById = new Map(suspects.map((suspect) => [suspect.id, suspect]));
  const suspectByName = new Map(suspects.map((suspect) => [suspect.name, suspect]));
  const isActiveSuspectTurn = (item: DialogueLogItem) => {
    if (!selectedSuspect) return true;
    if (item.suspectId) return item.suspectId === selectedSuspect.id;
    if (item.speaker === "player" || item.speaker === "system" || item.speaker === "rule_engine") return false;
    return item.speaker === selectedSuspect.name;
  };
  const visibleDialogue = dialogueLog.filter(isActiveSuspectTurn).slice(-8);
  const speakerFor = (item: DialogueLogItem) => {
    if (item.speaker === "player") return { kind: "detective", name: "탐정", role: "질문", avatar: "探", suspect: undefined as Suspect | undefined };
    if (item.speaker === "system" || item.speaker === "rule_engine") return { kind: "system", name: "기록", role: item.tag, avatar: "※", suspect: undefined as Suspect | undefined };
    const suspect = (item.suspectId && suspectById.get(item.suspectId)) || suspectByName.get(item.speaker) || selectedSuspect;
    return {
      kind: "suspect",
      name: suspect?.name ?? item.speaker,
      role: suspect?.role ?? "용의자",
      avatar: suspect?.name.slice(0, 1) ?? "?",
      suspect,
    };
  };

  return (
    <section className="panel interrogation-panel" aria-labelledby="stage-title">
      <h2 id="stage-title">
        심문 대상: <span>{selectedSuspect?.name ?? "용의자 선택 필요"}</span> <small>({selectedSuspect?.role ?? "미선택"})</small>
      </h2>
      <div className="interrogation-meta" aria-label="AI/세션 상태">
        <span className={`runtime-badge ${diagnosticTone}`}>{runtimeDiagnostics?.source === "api" ? "API 연결" : "LOCAL/MOCK"}</span>
        <span>intent: {diagnosticLabel(runtimeDiagnostics?.intent ?? runtimeDiagnostics?.dialogueMode, "AI intent 미분류")}</span>
        <span>matched refs: {matchedPublicRefs.length > 0 ? matchedPublicRefs.join(", ") : <span className="diagnostic-missing">공개 근거 미연결</span>}</span>
        <span>provider: {diagnosticLabel(runtimeDiagnostics?.provider, "provider 미수신")}{runtimeDiagnostics?.model ? `/${runtimeDiagnostics.model}` : ""}</span>
        <span className={runtimeDiagnostics?.degraded ? "diagnostic-alert" : undefined}>degraded: {runtimeDiagnostics?.degraded ? "yes" : "no"}</span>
        <span className={runtimeDiagnostics?.fallbackUsed ? "diagnostic-alert" : undefined}>fallback: {runtimeDiagnostics?.fallbackUsed ? "yes" : "no"}</span>
        <span>safety: {diagnosticLabel(runtimeDiagnostics?.safety, "safety 미수신")}</span>
        {runtimeDiagnostics?.blockedReason ? <span>blocked: {runtimeDiagnostics.blockedReason}</span> : null}
        <span>remaining: {runtimeDiagnostics?.previousRemainingQuestions ?? "?"}→{runtimeDiagnostics?.remainingQuestions ?? remainingQuestions} ({runtimeDiagnostics?.remainingQuestionsDelta ?? 0})</span>
        <span>state: {runtimeDiagnostics?.emotionalState ?? emotion}/{runtimeDiagnostics?.tensionLevel ?? tensionLevel}</span>
        <span>events: {noProgressEvents ? <span className="diagnostic-missing">이 턴에서 진행 이벤트 없음</span> : <>{diagnosticLabel(proposedCount, "proposed ?")}/{diagnosticLabel(appliedCount, "applied ?")}</>}</span>
        <span>eventId: {diagnosticLabel(runtimeDiagnostics?.lastEventId, "SSE event 미수신")}</span>
      </div>

      <div
        className={`cinematic-stage tension-${tensionLevel} expression-${expression}`}
        style={stageBackground ? { backgroundImage: `linear-gradient(90deg, rgba(0,0,0,.82), rgba(0,0,0,.12) 48%, rgba(0,0,0,.22)), linear-gradient(180deg, rgba(0,0,0,.04), rgba(0,0,0,.76)), url(${stageBackground})` } : undefined}
      >
        <img className="stage-character" src={suspectAsset(selectedSuspect?.id, expression)} alt={`${selectedSuspect?.name ?? "용의자"} ${expression} 표정 만화 일러스트`} />
        <div className="tension-meter" aria-label={`긴장도 ${pressure}% ${tensionLevel}`}>
          <span>긴장도</span>
          <div><i style={{ width: `${Math.min(100, Math.max(0, pressure))}%` }} /></div>
          <b>{tensionLevel}</b>
          <em>{emotion} / {expression}</em>
        </div>
        <div className="interrogation-target-card" aria-label="현재 심문 대상">
          <span>질문 대상</span>
          <strong>{selectedSuspect ? `${selectedSuspect.name} (${selectedSuspect.role})` : "미선택"}</strong>
          <em>{selectedSuspect ? selectedSuspect.id : "왼쪽 용의자를 선택해야 질문할 수 있습니다."}</em>
        </div>
        <aside className="gm-event-feed" aria-label="GameMaster 이벤트 피드" aria-live="polite">
          {eventFeed.slice(-4).map((item) => (
            <article key={item.id} className={`gm-feed-item ${item.type.toLowerCase()}`}>
              <strong>{item.title}</strong>
              <p>{item.message}</p>
            </article>
          ))}
        </aside>
        <div className="lamp-glow" aria-hidden="true" />
        <div className="scene-dialogue-log bubble-transcript" aria-label="턴별 대화 말풍선" aria-live="polite">
          {visibleDialogue.length > 0 ? visibleDialogue.map((item) => {
            const speaker = speakerFor(item);
            const isDetective = speaker.kind === "detective";
            const isSystem = speaker.kind === "system";
            return (
              <article key={item.id} className={`turn-bubble ${isDetective ? "detective" : isSystem ? "system" : "suspect"}`}>
                {!isDetective && !isSystem ? (
                  <img src={suspectAsset(speaker.suspect?.id, speaker.suspect?.expression ?? "neutral")} alt={`${speaker.name} 만화 초상`} />
                ) : (
                  <span className="turn-avatar" aria-hidden="true">{speaker.avatar}</span>
                )}
                <div>
                  <header>
                    <strong>{speaker.name}</strong>
                    <em>{speaker.role}{item.suspectId && speaker.kind === "detective" ? ` → ${suspectById.get(item.suspectId)?.name ?? item.suspectId}` : ""}</em>
                  </header>
                  <p>{item.text}</p>
                </div>
              </article>
            );
          }) : (
            <article className="turn-bubble system empty">
              <span className="turn-avatar" aria-hidden="true">※</span>
              <div><header><strong>기록</strong><em>대기</em></header><p>{latestAnswer || "첫 질문을 입력하면 탐정과 용의자의 대화가 말풍선으로 누적됩니다."}</p></div>
            </article>
          )}
        </div>
      </div>

      <form className="natural-input" onSubmit={(event) => { event.preventDefault(); onSubmitQuestion(); }}>
        <label htmlFor="question-input">자연어 질문 입력</label>
        <input
          id="question-input"
          value={draftQuestion}
          onChange={(event) => onDraftQuestionChange(event.target.value)}
          placeholder="직접 질문을 입력하세요. 예: 22시 이후 어디에 있었나요?"
          autoComplete="off"
          disabled={busy || remainingQuestions <= 0 || !selectedSuspect}
        />
        <button type="submit" aria-label="질문 보내기" disabled={busy || !draftQuestion.trim() || remainingQuestions <= 0 || !selectedSuspect}>➤</button>
        <p>{selectedSuspect ? `다음 질문 대상: ${selectedSuspect.name} · 힌트 예시) ${questionHint ? `“${questionHint}”` : "22시 이후에 누군가를 만난 적이 있나요?"}` : "먼저 왼쪽에서 심문할 용의자를 선택하세요. FE는 용의자를 자동 선택하지 않습니다."}</p>
        <button type="button" className="evidence-present" onClick={onPresentEvidence} disabled={busy}>▰ 증거 제시</button>
      </form>
    </section>
  );
}
