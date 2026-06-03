import { EvidenceGrid } from "./EvidenceGrid";
import type { GameSessionView } from "../types";
import type { EvidenceTileView } from "../viewModels/investigationDesk";

type EvidencePanelProps = {
  session: GameSessionView;
  evidenceTiles: EvidenceTileView[];
  selectedEvidenceIds: string[];
  onToggleEvidence: (evidenceId: string) => void;
};

export function EvidencePanel({
  session,
  evidenceTiles,
  selectedEvidenceIds,
  onToggleEvidence,
}: EvidencePanelProps) {
  const unlockedEvidence = session.evidence.filter((item) => item.unlocked);
  const unlockedRecords = session.records.filter((item) => item.unlocked);
  const unlockedRelations = session.relations.filter((item) => item.unlocked);
  const discoveredContradictions = session.contradictions.discovered;

  return (
    <aside className="panel evidence-panel" aria-labelledby="evidence-title">
      <EvidenceGrid
        tiles={evidenceTiles}
        unlockedCount={unlockedEvidence.length}
        totalCount={session.totalEvidenceCount}
        selectedEvidenceIds={selectedEvidenceIds}
        onToggleEvidence={onToggleEvidence}
      />
      <div className="right-investigation-loop">
        <section className="contradiction-panel be-readmodel-panel" aria-labelledby="be-contradiction-title">
          <header>
            <div>
              <span>수사 기록</span>
              <h3 id="be-contradiction-title">발견된 모순</h3>
            </div>
            <small>자연어 심문에서 확인된 모순만 이곳에 기록됩니다.</small>
          </header>
          {discoveredContradictions.length > 0 ? (
            discoveredContradictions.slice(0, 3).map((item) => (
              <article key={item.contradictionId} className="be-state-row">
                <span>{item.title}</span>
                <strong>{item.displayText}</strong>
                <small>{item.evidenceIds.join(", ") || "관련 증거 없음"}</small>
              </article>
            ))
          ) : (
            <p className="empty-inline">아직 확정된 모순이 없습니다. 증거 이름을 자연어 질문에 넣어 추궁하세요.</p>
          )}
        </section>
      </div>
      <section className="desk-summary-card compact" aria-label="사건 자료 요약">
        <header>
          <strong>수사 자료</strong>
          <span>용의자는 전원 공개 · 단서는 진행 해금</span>
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
