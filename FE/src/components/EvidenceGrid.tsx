import { evidenceAsset, lockedEvidenceAssetPath } from "../constants/presentation";
import type { EvidenceTileView } from "../viewModels/investigationDesk";

type EvidenceGridProps = {
  tiles: EvidenceTileView[];
  unlockedCount: number;
  totalCount: number;
  selectedEvidenceIds: string[];
  onToggleEvidence: (evidenceId: string) => void;
};

export function EvidenceGrid({ tiles, unlockedCount, totalCount, selectedEvidenceIds, onToggleEvidence }: EvidenceGridProps) {
  return (
    <>
      <div className="section-title">
        <h2 id="evidence-title">증거</h2>
        <span>{unlockedCount}/{totalCount}</span>
      </div>
      <div className="evidence-grid">
        {tiles.map((item, index) => {
          if (!item) {
            return (
              <div key={`empty-${index}`} className="evidence-tile locked evidence-photo-card">
                <img src={lockedEvidenceAssetPath} alt="잠긴 증거 슬롯" />
                <strong>추가 증거<br />잠금 해제</strong>
              </div>
            );
          }
          const locked = !item.unlocked;
          const assetPath = locked ? lockedEvidenceAssetPath : evidenceAsset(item.id) ?? lockedEvidenceAssetPath;
          return (
            <button
              key={item.id}
              type="button"
              className={`evidence-tile evidence-photo-card ${locked ? "locked" : ""} ${selectedEvidenceIds.includes(item.id) ? "selected" : ""}`}
              onClick={() => !locked && onToggleEvidence(item.id)}
              disabled={locked}
              aria-pressed={selectedEvidenceIds.includes(item.id)}
            >
              <img src={assetPath} alt={locked ? "잠긴 증거" : `${item.title} 증거 사진`} />
              <strong>{locked ? "추가 증거\n잠금 해제" : item.title}</strong>
            </button>
          );
        })}
      </div>
    </>
  );
}
