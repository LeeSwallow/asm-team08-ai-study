import { useEffect, useRef } from "react";
import { backgroundAsset, defaultBackgroundIdForCase, suspectAsset, suspectStatusText } from "../constants/presentation";
import type { DialogueLogItem, DialogueRuntimeDiagnostics, GameEventFeedItem, Suspect, VisualState } from "../types";

const TONE_KO: Record<string, string> = {
  sharp_defensive: "날카롭게 방어",
  calm_defensive: "침착하게 방어",
  restrained_formal: "격식체",
  evidence_shock: "충격 반응",
  broken: "멘탈 붕괴",
  formal: "정중하게",
  tense: "긴장감",
  neutral: "평온",
  evasive: "회피",
  aggressive: "공격적",
  collapsed: "붕괴",
  cooperative: "협조적",
};

function formatVoiceTone(tone: string): string {
  return TONE_KO[tone] ?? tone.replace(/_/g, " ");
}

type InterrogationStageProps = {
  selectedSuspect?: Suspect;
  suspects: Suspect[];
  selectedSuspectId: string | null;
  latestAnswer: string;
  dialogueLog: DialogueLogItem[];
  pendingUserMessage?: { text: string; suspectId: string } | null;
  eventFeed: GameEventFeedItem[];
  draftQuestion: string;
  questionHint?: string;
  busy: boolean;
  remainingQuestions: number;
  questionLimit: number;
  visualState?: VisualState;
  runtimeDiagnostics?: DialogueRuntimeDiagnostics;
  onDraftQuestionChange: (value: string) => void;
  onSubmitQuestion: () => void;
  onPresentEvidence: () => void;
  onOpenRelations: () => void;
  onOpenAccusation: () => void;
  onSelectSuspect: (suspectId: string) => void;
};

export function InterrogationStage({
  selectedSuspect,
  suspects,
  selectedSuspectId,
  latestAnswer,
  dialogueLog,
  pendingUserMessage,
  eventFeed,
  draftQuestion,
  questionHint,
  busy,
  remainingQuestions,
  questionLimit,
  visualState,
  runtimeDiagnostics,
  onDraftQuestionChange,
  onSubmitQuestion,
  onPresentEvidence,
  onOpenRelations,
  onOpenAccusation,
  onSelectSuspect,
}: InterrogationStageProps) {
  const visualAppliesToSelected = Boolean(
    selectedSuspect && (!visualState?.suspectId || visualState.suspectId === selectedSuspect.id),
  );
  const pressure = selectedSuspect?.pressure ?? 0;
  const fallbackTensionLevel = selectedSuspect?.tensionLevel ?? (pressure >= 80 ? "critical" : pressure >= 55 ? "high" : pressure >= 20 ? "medium" : "low");
  const tensionLevel = visualAppliesToSelected ? (visualState?.tensionLevel ?? fallbackTensionLevel) : fallbackTensionLevel;
  const expression = visualAppliesToSelected
    ? (visualState?.characterImageState ?? visualState?.expression ?? selectedSuspect?.expression ?? "neutral")
    : (selectedSuspect?.expression ?? "neutral");
  const emotion = visualAppliesToSelected ? (visualState?.emotionalState ?? selectedSuspect?.emotion ?? "guarded") : (selectedSuspect?.emotion ?? "guarded");
  const stageBackground = backgroundAsset(visualAppliesToSelected ? visualState?.backgroundId : defaultBackgroundIdForCase());
  const stageAsset = suspectAsset(selectedSuspect?.id, expression);
  const stageMood = `${emotion}-${expression}-${tensionLevel}`;
  const diagnosticTone = runtimeDiagnostics?.fallbackUsed || runtimeDiagnostics?.degraded ? "fallback" : "api";
  const reaction = runtimeDiagnostics?.characterReaction;
  const helperSuggestion = runtimeDiagnostics?.helperSuggestion;
  const showHelperSuggestion = Boolean(helperSuggestion && helperSuggestion.helperRoute !== "silent" && helperSuggestion.message);
  const handleHelperAction = (actionType: string, targetId: string) => {
    if (actionType === "ask_suspect" && targetId) {
      onSelectSuspect(targetId);
      return;
    }
    if (actionType === "open_relation" || actionType === "open_relations" || actionType === "nudge_relation") {
      onOpenRelations();
      return;
    }
    if (actionType === "open_accusation" || actionType === "prepare_accusation") {
      onOpenAccusation();
      return;
    }
    if (actionType === "try_contradiction" || actionType === "open_evidence") {
      onPresentEvidence();
      return;
    }
    onPresentEvidence();
  };
  const reactionRoute = runtimeDiagnostics?.characterReactionRoute ?? reaction?.reactionRoute ?? reaction?.route;
  const reactionLabel = reaction?.label ?? reactionRoute;
  const reactionSummary = reactionLabel ? `${reactionLabel}${reaction?.effect ? ` → ${reaction.effect}` : ""}` : undefined;
  const visibleProgressCount = runtimeDiagnostics?.appliedEventsCount ?? 0;
  const suspectById = new Map(suspects.map((suspect) => [suspect.id, suspect]));
  const suspectByName = new Map(suspects.map((suspect) => [suspect.name, suspect]));
  const isActiveSuspectTurn = (item: DialogueLogItem) => {
    if (!selectedSuspect) return true;
    if (item.suspectId) return item.suspectId === selectedSuspect.id;
    if (item.speaker === "player" || item.speaker === "system" || item.speaker === "rule_engine") return false;
    return item.speaker === selectedSuspect.name;
  };
  const visibleDialogue = dialogueLog.filter(isActiveSuspectTurn).slice(-6);
  const dialogueLogRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const node = dialogueLogRef.current;
    if (!node) return;
    node.scrollTo({ top: node.scrollHeight, behavior: "smooth" });
  }, [visibleDialogue.length, selectedSuspect?.id, latestAnswer]);
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
      <div className="suspect-bar" aria-label="용의자 선택">
        {suspects.map((suspect) => {
          const isSelected = suspect.id === selectedSuspectId;
          return (
            <button
              key={suspect.id}
              type="button"
              className={`suspect-bar-chip ${isSelected ? "active" : ""}`}
              onClick={() => onSelectSuspect(suspect.id)}
              aria-current={isSelected}
            >
              <i className={`suspect-bar-dot ${isSelected ? "active" : ""}`} aria-hidden="true" />
              <span>{suspect.name}</span>
              <small>{suspectStatusText(suspect.status, isSelected)}</small>
            </button>
          );
        })}
      </div>
      <h2 id="stage-title">
        심문 대상: <span>{selectedSuspect?.name ?? "용의자 선택 필요"}</span>
      </h2>
      <details className="interrogation-meta" aria-label="수사 상태">
        <summary>
          <span className={`runtime-badge ${diagnosticTone}`}>수사 기록</span>
          {reactionSummary ? <span className="reaction-route-badge">AI 판단: {reactionSummary}</span> : null}
          <span>{runtimeDiagnostics?.fallbackUsed || runtimeDiagnostics?.degraded ? "기록 확인 중" : "진행 정상"}</span>
          <span>남은 질문 {remainingQuestions}/{questionLimit}</span>
        </summary>
        <div className="diagnostic-detail-row">
          <span>최근 진행: {visibleProgressCount > 0 ? `${visibleProgressCount}건 기록됨` : "새 기록 없음"}</span>
          <span>질문 사용: {runtimeDiagnostics?.previousRemainingQuestions ?? remainingQuestions}→{runtimeDiagnostics?.remainingQuestions ?? remainingQuestions}/{questionLimit}</span>
          <span>분위기: {emotion}/{tensionLevel}</span>
          {reactionRoute ? <span>분기: {reactionRoute}{typeof reaction?.confidence === "number" ? ` · ${Math.round(reaction.confidence * 100)}%` : ""}</span> : null}
          {reaction?.playerFacingReason ? <span>판단 근거: {reaction.playerFacingReason}</span> : null}
          {runtimeDiagnostics?.blockedReason ? <span className="diagnostic-alert">응답 보류: 공개 가능한 답변으로 조정 중</span> : null}
        </div>
      </details>

      <div
        className={`cinematic-stage reactive-stage tension-${tensionLevel} expression-${expression} ${visibleDialogue.length > 0 ? "has-dialogue" : "is-awaiting-first-turn"}`}
        data-mood={stageMood}
        style={stageBackground ? { backgroundImage: `linear-gradient(90deg, rgba(0,0,0,.82), rgba(0,0,0,.12) 48%, rgba(0,0,0,.22)), linear-gradient(180deg, rgba(0,0,0,.04), rgba(0,0,0,.76)), url(${stageBackground})` } : undefined}
      >
        {stageAsset ? (
          <img key={`${selectedSuspect?.id}-${expression}`} className="stage-character" src={stageAsset} alt={`${selectedSuspect?.name ?? "용의자"} ${expression} 표정 만화 일러스트`} />
        ) : null}
        <div className="tension-meter" aria-label={`긴장도 ${pressure}% ${tensionLevel}`}>
          <span>긴장도</span>
          <div><i style={{ width: `${Math.min(100, Math.max(0, pressure))}%` }} /></div>
          <b>{tensionLevel}</b>
          <em>{emotion} / {expression}</em>
        </div>
        <div className="interrogation-target-card" aria-label="현재 심문 대상">
          <span>질문 대상</span>
          <strong>{selectedSuspect ? selectedSuspect.name : "미선택"}</strong>
          <em>{selectedSuspect ? selectedSuspect.role : "왼쪽 용의자를 선택해야 질문할 수 있습니다."}</em>
        </div>
        <aside className="gm-event-feed" aria-label="수사 진행 기록" aria-live="polite">
          {eventFeed.slice(-2).map((item) => (
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
            const vTag = item.voiceTag ? formatVoiceTone(item.voiceTag) : null;
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
                  {vTag ? <span className="voice-tag" aria-label={`발화 상태: ${vTag}`}>{vTag}</span> : null}
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
          {pendingUserMessage ? (
            <article className="turn-bubble detective pending" aria-label="전송 중인 질문">
              <span className="turn-avatar" aria-hidden="true">探</span>
              <div>
                <header>
                  <strong>탐정</strong>
                  <em>질문{pendingUserMessage.suspectId ? ` → ${suspectById.get(pendingUserMessage.suspectId)?.name ?? ""}` : ""}</em>
                </header>
                <p>{pendingUserMessage.text}</p>
              </div>
            </article>
          ) : null}
          {busy && selectedSuspect ? (
            <article className="turn-bubble suspect typing-bubble" aria-label={`${selectedSuspect.name} 응답 중`} aria-live="polite">
              <img src={suspectAsset(selectedSuspect.id, expression)} alt={`${selectedSuspect.name} 만화 초상`} />
              <div>
                <header>
                  <strong>{selectedSuspect.name}</strong>
                  <em>생각 중…</em>
                </header>
                <span className="typing-dots" aria-hidden="true">
                  <i /><i /><i />
                </span>
              </div>
            </article>
          ) : null}
        </div>
      </div>

      <form className="natural-input" onSubmit={(event) => { event.preventDefault(); onSubmitQuestion(); }}>
        <label htmlFor="question-input">자연어 질문 입력</label>
        <input
          id="question-input"
          value={draftQuestion}
          onChange={(event) => onDraftQuestionChange(event.target.value)}
          placeholder="직접 질문을 입력하세요."
          autoComplete="off"
          disabled={busy || remainingQuestions <= 0 || !selectedSuspect}
        />
        <button type="submit" aria-label="질문 보내기" disabled={busy || !draftQuestion.trim() || remainingQuestions <= 0 || !selectedSuspect}>➤</button>
        <p>{selectedSuspect ? "자연어로 직접 추궁하세요. 구체적인 질문 예시는 힌트 안에만 숨겨 둡니다." : "왼쪽 용의자를 선택하면 자연어 질문을 보낼 수 있습니다."}</p>
        {selectedSuspect && questionHint ? (
          <details className="question-hint">
            <summary>막혔을 때만 보기</summary>
            <span>{questionHint}</span>
          </details>
        ) : null}
        <button type="button" className="evidence-present" onClick={onPresentEvidence} disabled={busy}>▰ 증거 목록</button>
      </form>
    </section>
  );
}
