import { AppHeader } from "../components/AppHeader";
import { CaseFilePanel } from "../components/CaseFilePanel";
import { EvidencePanel } from "../components/EvidencePanel";
import { InterrogationStage } from "../components/InterrogationStage";
import { GameEndingOverlay } from "../components/GameEndingOverlay";
import { InvestigationDrawer } from "../components/InvestigationDrawer";
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

      {desk.session.result ? (
        <GameEndingOverlay
          result={desk.session.result}
          session={desk.session}
          onOpenDossier={() => desk.setActiveDrawer("accusation")}
          onReturnToCases={() => onNavigate(caseListPath())}
        />
      ) : null}

    </main>
  );
}
