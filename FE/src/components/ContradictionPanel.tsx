import type { ContradictionCandidateView } from "../viewModels/investigationDesk";

type ContradictionPanelProps = {
  candidates: ContradictionCandidateView[];
  onSelect: (statementId: string, evidenceId: string) => void;
};

export function ContradictionPanel({ candidates, onSelect }: ContradictionPanelProps) {
  return (
    <section className="contradiction-panel" aria-labelledby="contradiction-title">
      <h3 id="contradiction-title">모순 사항</h3>
      {candidates.map((row) => (
        <button key={`${row.statementId}-${row.evidenceId}`} type="button" onClick={() => onSelect(row.statementId, row.evidenceId)}>
          <span>{row.statement}</span>
          <strong>{row.evidence}</strong>
          <i aria-hidden="true">›</i>
        </button>
      ))}
    </section>
  );
}
