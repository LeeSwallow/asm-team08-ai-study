import { useState, useEffect, useRef } from "react";
import { AppHeader } from "../components/AppHeader";
import { CaseFilePanel } from "../components/CaseFilePanel";
import { EvidencePanel } from "../components/EvidencePanel";
import { InterrogationStage } from "../components/InterrogationStage";
import { GameEndingOverlay } from "../components/GameEndingOverlay";
import { InvestigationDrawer } from "../components/InvestigationDrawer";
import { useInvestigationSession } from "../hooks/useInvestigationSession";
import { caseListPath } from "../routing";
import type { HelperSuggestion } from "../types";

type SessionDeskPageProps = {
  sessionId: string;
  onNavigate: (path: string) => void;
};

export function SessionDeskPage({ sessionId, onNavigate }: SessionDeskPageProps) {
  const desk = useInvestigationSession({
    sessionId,
    onSessionCreated: (createdSessionId) => onNavigate(`/sessions/${encodeURIComponent(createdSessionId)}`),
    onSessionCleared: () => onNavigate(caseListPath()),
  });

  const [toastHelper, setToastHelper] = useState<HelperSuggestion | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const helperSuggestion = desk.session?.runtimeDiagnostics?.helperSuggestion;

  useEffect(() => {
    if (!helperSuggestion || helperSuggestion.helperRoute === "silent" || !helperSuggestion.message) return;
    setToastHelper(helperSuggestion);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToastHelper(null), 5000);
    return () => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [helperSuggestion?.message]);

  if (!desk.session) {
    return (
      <main className="loading-desk" aria-label="수사 기록 로딩">
        <section className="loading-card" role="status" aria-live="polite">
          <span className="brand-icon" aria-hidden="true">⚖</span>
          <h1>수사 기록 복구</h1>
          <p>{desk.statusMessage}</p>
          <button type="button" onClick={() => onNavigate(caseListPath())}>사건 목록으로</button>
        </section>
      </main>
    );
  }

  return (
    <main className="noir-desk">
      <AppHeader
        onOpenEvidence={() => desk.setActiveDrawer("evidence")}
        onOpenNotes={() => desk.setActiveDrawer("notes")}
        onOpenRelations={() => desk.setActiveDrawer("relations")}
        onOpenAccusation={() => desk.setActiveDrawer("accusation")}
        onExitSession={() => onNavigate(caseListPath())}
      />

      <section className="desk-grid" aria-label="수사 데스크">
        <CaseFilePanel session={desk.session} />
        <InterrogationStage
          selectedSuspect={desk.selectedSuspect}
          suspects={desk.session.suspects}
          selectedSuspectId={desk.session.selectedSuspectId}
          latestAnswer={desk.latestAnswer}
          dialogueLog={desk.session.dialogueLog}
          pendingUserMessage={desk.pendingUserMessage}
          eventFeed={desk.eventFeed}
          draftQuestion={desk.draftQuestion}
          questionHint={desk.questionHint}
          busy={desk.busy}
          remainingQuestions={desk.session.remainingQuestions}
          questionLimit={desk.session.questionLimit}
          visualState={desk.session.visualState}
          runtimeDiagnostics={desk.session.runtimeDiagnostics}
          onDraftQuestionChange={desk.setDraftQuestion}
          onSubmitQuestion={desk.submitQuestion}
          onPresentEvidence={() => desk.setActiveDrawer("evidence")}
          onOpenRelations={() => desk.setActiveDrawer("relations")}
          onOpenAccusation={() => desk.setActiveDrawer("accusation")}
          onSelectSuspect={desk.selectSuspect}
        />
        <EvidencePanel
          session={desk.session}
          evidenceTiles={desk.evidenceTiles}
          selectedEvidenceIds={desk.selectedEvidenceIds}
          onToggleEvidence={desk.toggleEvidence}
        />
      </section>

      {desk.activeDrawer ? (
        <InvestigationDrawer
          mode={desk.activeDrawer}
          session={desk.session}
          inspectedEvidenceId={desk.inspectedEvidenceId}
          selectedEvidenceIds={desk.selectedEvidenceIds}
          selectedStatementIds={desk.selectedStatementIds}
          draftNote={desk.draftNote}
          editingNoteId={desk.editingNoteId}
          editingNoteText={desk.editingNoteText}
          busy={desk.busy}
          onClose={() => desk.setActiveDrawer(null)}
          onOpenMode={(mode) => desk.setActiveDrawer(mode)}
          onInspectEvidence={desk.setInspectedEvidenceId}
          onDraftNoteChange={desk.setDraftNote}
          onEditingNoteTextChange={desk.setEditingNoteText}
          onAddNote={desk.addNote}
          onStartEditNote={desk.startEditNote}
          onCancelEditNote={desk.cancelEditNote}
          onSaveEditedNote={desk.saveEditedNote}
          onRemoveNote={desk.removeNote}
          accusationSuspectId={desk.accusationSuspectId}
          accusationMotive={desk.accusationMotive}
          accusationMethod={desk.accusationMethod}
          onAccusationSuspectChange={desk.setAccusationSuspectId}
          onAccusationMotiveChange={desk.setAccusationMotive}
          onAccusationMethodChange={desk.setAccusationMethod}
          onSubmitAccusation={desk.submitFinalAccusation}
        />
      ) : null}

      {desk.session.result ? (
        <GameEndingOverlay
          result={desk.session.result}
          session={desk.session}
          onOpenDossier={() => desk.setActiveDrawer("accusation")}
          onReturnToCases={() => onNavigate(caseListPath())}
        />
      ) : null}

      {toastHelper ? (
        <aside className="helper-toast" aria-live="polite" aria-label="조수의 조언">
          <div className="helper-toast-body">
            <span className="helper-toast-label">조수의 조언</span>
            <p>{toastHelper.message}</p>
          </div>
          <button
            type="button"
            className="helper-toast-close"
            aria-label="닫기"
            onClick={() => { if (toastTimerRef.current) clearTimeout(toastTimerRef.current); setToastHelper(null); }}
          >✕</button>
        </aside>
      ) : null}

    </main>
  );
}
