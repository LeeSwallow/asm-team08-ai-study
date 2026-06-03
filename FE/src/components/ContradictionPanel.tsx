import type { ContradictionCandidateView } from "../viewModels/investigationDesk";

type ContradictionPanelProps = {
  candidates: ContradictionCandidateView[];
  selectedStatementIds: string[];
  selectedEvidenceIds: string[];
  onSelect: (statementId: string, evidenceId: string) => void;
};

export function ContradictionPanel({
  candidates,
  selectedStatementIds,
  selectedEvidenceIds,
  onSelect,
}: ContradictionPanelProps) {
  const selectedKey = `${selectedStatementIds[0] ?? ""}-${selectedEvidenceIds[0] ?? ""}`;

  return (
    <section className="contradiction-panel" aria-labelledby="contradiction-title">
      <header>
        <div>
          <span>LLM/BE 대화 판정</span>
          <h3 id="contradiction-title">모순 사항</h3>
        </div>
        <small>자연어 심문에서 근거를 언급하면 AI 파이프라인이 판단합니다.</small>
      </header>
      {candidates.length > 0 ? (
        candidates.map((row) => {
          const selected = selectedKey === `${row.statementId}-${row.evidenceId}`;
          return (
            <button
              key={`${row.statementId}-${row.evidenceId}`}
              type="button"
              className={selected ? "selected" : undefined}
              onClick={() => onSelect(row.statementId, row.evidenceId)}
              aria-pressed={selected}
            >
              <span>{row.statement}</span>
              <strong>{row.evidence}</strong>
              <small>최종 고발 근거로 표시</small>
              <i aria-hidden="true">›</i>
            </button>
          );
        })
      ) : (
        <p className="empty-inline">아직 AI가 연결한 공개 증언·증거 후보가 없습니다. 용의자에게 자연어로 증거를 언급해 추궁하세요.</p>
      )}
    </section>
  );
}
