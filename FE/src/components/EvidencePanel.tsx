import { ContradictionPanel } from "./ContradictionPanel";
import { EvidenceGrid } from "./EvidenceGrid";
import type { GameSessionView } from "../types";
import type { ContradictionCandidateView, EvidenceTileView } from "../viewModels/investigationDesk";

type EvidencePanelProps = {
  session: GameSessionView;
  evidenceTiles: EvidenceTileView[];
  contradictionCandidates: ContradictionCandidateView[];
  selectedEvidenceIds: string[];
  onToggleEvidence: (evidenceId: string) => void;
  onSelectContradiction: (statementId: string, evidenceId: string) => void;
};

export function EvidencePanel({
  session,
  evidenceTiles,
  contradictionCandidates,
  selectedEvidenceIds,
  onToggleEvidence,
  onSelectContradiction,
}: EvidencePanelProps) {
  return (
    <aside className="panel evidence-panel" aria-labelledby="evidence-title">
      <EvidenceGrid
        tiles={evidenceTiles}
        unlockedCount={session.evidence.filter((item) => item.unlocked).length}
        totalCount={session.evidence.length}
        selectedEvidenceIds={selectedEvidenceIds}
        onToggleEvidence={onToggleEvidence}
      />
      <ContradictionPanel candidates={contradictionCandidates} onSelect={onSelectContradiction} />
    </aside>
  );
}
