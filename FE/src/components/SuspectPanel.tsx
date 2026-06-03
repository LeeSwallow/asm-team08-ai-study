import { suspectAsset, suspectStatusText } from "../constants/presentation";
import type { Suspect } from "../types";

type SuspectPanelProps = {
  suspects: Suspect[];
  selectedSuspectId: string | null;
  onSelectSuspect: (suspectId: string) => void;
  onOpenRelations: () => void;
};

export function SuspectPanel({ suspects, selectedSuspectId, onSelectSuspect, onOpenRelations }: SuspectPanelProps) {
  return (
    <aside className="panel suspect-panel" aria-labelledby="suspect-panel-title">
      <div className="section-title">
        <h2 id="suspect-panel-title">용의자</h2>
      </div>
      {!selectedSuspectId ? <p className="selection-required">심문할 용의자를 선택하세요.</p> : null}
      <div className="suspect-list">
        {suspects.map((suspect) => {
          const isSelected = suspect.id === selectedSuspectId;
          return (
            <button
              key={suspect.id}
              type="button"
              className={`suspect-card ${isSelected ? "active" : ""}`}
              onClick={() => onSelectSuspect(suspect.id)}
              aria-current={isSelected}
              aria-label={`${suspect.name}, ${suspectStatusText(suspect.status, isSelected)}`}
            >
              <span className="portrait"><img src={suspectAsset(suspect.id, suspect.expression)} alt="" /></span>
              <span className="suspect-info">
                <strong>{suspect.name}</strong>
                <span>{suspect.profile}</span>
                <em>{suspectStatusText(suspect.status, isSelected)}</em>
              </span>
              <i className="status-dot" aria-hidden="true" />
            </button>
          );
        })}
      </div>
      <button type="button" className="relation-button" onClick={onOpenRelations}>♙ 인물 관계도</button>
    </aside>
  );
}
