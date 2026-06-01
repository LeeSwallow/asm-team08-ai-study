import { AppHeader } from "./components/AppHeader";
import { EvidencePanel } from "./components/EvidencePanel";
import { InterrogationStage } from "./components/InterrogationStage";
import { InvestigationDrawer } from "./components/InvestigationDrawer";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { SuspectPanel } from "./components/SuspectPanel";
import { SystemFlowStrip } from "./components/SystemFlowStrip";
import { useInvestigationSession } from "./hooks/useInvestigationSession";

export default function App() {
  const desk = useInvestigationSession();

  if (!desk.session) {
    return (
      <main className="loading-desk" aria-live="polite">
        <section className="loading-card">
          <span className="brand-icon">⚖</span>
          <h1>알리바이 교차검증형 추리 게임</h1>
          <p>{desk.currentCase?.summary ?? "폭풍우 치던 밤의 저택 사건 파일을 여는 중입니다."}</p>
          <strong>{desk.statusMessage}</strong>
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
          draftQuestion={desk.draftQuestion}
          questionHint={desk.questionHint}
          busy={desk.busy}
          remainingQuestions={desk.session.remainingQuestions}
          visualState={desk.session.visualState}
          runtimeDiagnostics={desk.session.runtimeDiagnostics}
          onDraftQuestionChange={desk.setDraftQuestion}
          onSubmitQuestion={desk.submitQuestion}
          onPresentEvidence={() => desk.setActiveDrawer("contradiction")}
        />
        <EvidencePanel
          session={desk.session}
          evidenceTiles={desk.evidenceTiles}
          contradictionCandidates={desk.contradictionCandidates}
          selectedEvidenceIds={desk.selectedEvidenceIds}
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
          onSelectStatement={desk.selectStatement}
          onDraftNoteChange={desk.setDraftNote}
          onEditingNoteTextChange={desk.setEditingNoteText}
          onAddNote={desk.addNote}
          onStartEditNote={desk.startEditNote}
          onCancelEditNote={desk.cancelEditNote}
          onSaveEditedNote={desk.saveEditedNote}
          onRemoveNote={desk.removeNote}
          onSubmitContradiction={desk.submitSelectedContradiction}
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
