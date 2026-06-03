import { AppHeader } from "../components/AppHeader";
import { EvidencePanel } from "../components/EvidencePanel";
import { InterrogationStage } from "../components/InterrogationStage";
import { InvestigationDrawer } from "../components/InvestigationDrawer";
import { SettingsDrawer } from "../components/SettingsDrawer";
import { SuspectPanel } from "../components/SuspectPanel";
import { SystemFlowStrip } from "../components/SystemFlowStrip";
import { useInvestigationSession } from "../hooks/useInvestigationSession";
import { caseListPath } from "../routing";

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

  if (!desk.session) {
    return (
      <main className="loading-desk" aria-label="세션 로딩">
        <section className="loading-card" role="status" aria-live="polite">
          <span className="brand-icon" aria-hidden="true">⚖</span>
          <h1>수사 세션 복구</h1>
          <p>{desk.statusMessage}</p>
          <button type="button" onClick={() => onNavigate(caseListPath())}>사건 목록으로</button>
        </section>
      </main>
    );
  }

  return (
    <main className="noir-desk">
      <AppHeader
        onOpenCaseFile={() => desk.setActiveDrawer("case")}
        onOpenEvidence={() => desk.setActiveDrawer("evidence")}
        onOpenNotes={() => desk.setActiveDrawer("notes")}
        onOpenRelations={() => desk.setActiveDrawer("relations")}
        onOpenAccusation={() => desk.setActiveDrawer("accusation")}
        onOpenSettings={() => desk.setActiveDrawer("settings")}
      />

      <section className="desk-grid" aria-label="수사 데스크">
        <SuspectPanel
          suspects={desk.session.suspects}
          selectedSuspectId={desk.session.selectedSuspectId}
          onSelectSuspect={desk.selectSuspect}
          onOpenRelations={() => desk.setActiveDrawer("relations")}
        />
        <InterrogationStage
          selectedSuspect={desk.selectedSuspect}
          suspects={desk.session.suspects}
          latestAnswer={desk.latestAnswer}
          dialogueLog={desk.session.dialogueLog}
          eventFeed={desk.eventFeed}
          draftQuestion={desk.draftQuestion}
          questionHint={desk.questionHint}
          busy={desk.busy}
          remainingQuestions={desk.session.remainingQuestions}
          visualState={desk.session.visualState}
          runtimeDiagnostics={desk.session.runtimeDiagnostics}
          onDraftQuestionChange={desk.setDraftQuestion}
          onSubmitQuestion={desk.submitQuestion}
          onPresentEvidence={() => desk.setActiveDrawer("evidence")}
        />
        <EvidencePanel
          session={desk.session}
          evidenceTiles={desk.evidenceTiles}
          selectedEvidenceIds={desk.selectedEvidenceIds}
          selectedStatementIds={desk.selectedStatementIds}
          contradictionCandidates={desk.contradictionCandidates}
          onToggleEvidence={desk.toggleEvidence}
          onSelectContradiction={desk.selectContradiction}
        />
      </section>

      {desk.activeDrawer && desk.activeDrawer !== "settings" ? (
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
          onToggleEvidence={desk.toggleEvidence}
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

      {desk.activeDrawer === "settings" ? (
        <SettingsDrawer
          session={desk.session}
          busy={desk.busy}
          onClose={() => desk.setActiveDrawer(null)}
          onAdjustPressure={desk.adjustDebugPressure}
          onUnlock={desk.unlockDebug}
          onReset={desk.resetGame}
        />
      ) : null}

      <SystemFlowStrip statusMessage={desk.statusMessage} remainingQuestions={desk.session.remainingQuestions} />
    </main>
  );
}
