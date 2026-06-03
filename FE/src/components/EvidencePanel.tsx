import { EvidenceGrid } from "./EvidenceGrid";
import { ContradictionPanel } from "./ContradictionPanel";
import type { GameSessionView } from "../types";
import type { ContradictionCandidateView, EvidenceTileView } from "../viewModels/investigationDesk";

type EvidencePanelProps = {
  session: GameSessionView;
  evidenceTiles: EvidenceTileView[];
  selectedEvidenceIds: string[];
  selectedStatementIds: string[];
  contradictionCandidates: ContradictionCandidateView[];
  onToggleEvidence: (evidenceId: string) => void;
  onSelectContradiction: (statementId: string, evidenceId: string) => void;
};

export function EvidencePanel({
  session,
  evidenceTiles,
  selectedEvidenceIds,
  selectedStatementIds,
  contradictionCandidates,
  onToggleEvidence,
  onSelectContradiction,
}: EvidencePanelProps) {
  const unlockedEvidence = session.evidence.filter((item) => item.unlocked);
  const unlockedRecords = session.records.filter((item) => item.unlocked);
  const unlockedRelations = session.relations.filter((item) => item.unlocked);

  return (
    <aside className="panel evidence-panel" aria-labelledby="evidence-title">
      <EvidenceGrid
        tiles={evidenceTiles}
        unlockedCount={unlockedEvidence.length}
        totalCount={session.evidence.length}
        selectedEvidenceIds={selectedEvidenceIds}
        onToggleEvidence={onToggleEvidence}
      />
      <div className="right-investigation-loop">
        <ContradictionPanel
          candidates={contradictionCandidates}
          selectedStatementIds={selectedStatementIds}
          selectedEvidenceIds={selectedEvidenceIds}
          onSelect={onSelectContradiction}
        />
      </div>
      <section className="desk-summary-card compact" aria-label="사건 자료 요약">
        <header>
          <strong>연동 자료</strong>
          <span>BE session</span>
        </header>
        <div className="desk-summary-stats">
          <span><b>{unlockedRecords.length}</b> 기록</span>
          <span><b>{session.notes.length}</b> 메모</span>
          <span><b>{unlockedRelations.length}</b> 관계</span>
        </div>
      </section>
    </aside>
  );
}
