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
  const latestRecords = session.records.filter((item) => item.unlocked).slice(0, 3);

  return (
    <aside className="panel evidence-panel" aria-labelledby="evidence-title">
      <EvidenceGrid
        tiles={evidenceTiles}
        unlockedCount={unlockedEvidence.length}
        totalCount={session.evidence.length}
        selectedEvidenceIds={selectedEvidenceIds}
        onToggleEvidence={onToggleEvidence}
      />
      <section className="desk-summary-card" aria-label="사건 자료 요약">
        <header>
          <strong>자료 보드</strong>
          <span>{latestRecords.length} records</span>
        </header>
        <div className="desk-summary-stats">
          <b>{session.notes.length}</b><span>메모</span>
          <b>{session.relations.filter((item) => item.unlocked).length}</b><span>관계</span>
        </div>
        {latestRecords.length > 0 ? (
          latestRecords.map((record) => (
            <article key={record.id}>
              <b>{record.time}</b>
              <p>{record.title}</p>
            </article>
          ))
        ) : (
          <p className="empty-inline">공개 사건 기록이 아직 없습니다.</p>
        )}
      </section>
    </aside>
  );
}
