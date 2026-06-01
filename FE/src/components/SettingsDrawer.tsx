import type { GameSessionView } from "../types";

type DebugUnlockTarget = "evidence" | "relations" | "timeline" | "notes" | "all";

type SettingsDrawerProps = {
  session: GameSessionView;
  busy: boolean;
  onClose: () => void;
  onAdjustPressure: (suspectId: string, pressure: number) => void;
  onUnlock: (target: DebugUnlockTarget) => void;
  onReset: () => void;
};

export function SettingsDrawer({
  session,
  busy,
  onClose,
  onAdjustPressure,
  onUnlock,
  onReset,
}: SettingsDrawerProps) {
  return (
    <aside className="investigation-drawer settings-drawer" aria-label="설정 및 디버그 패널">
      <header>
        <strong>설정 / Debug</strong>
        <button type="button" onClick={onClose} aria-label="설정 패널 닫기">×</button>
      </header>

      <section className="drawer-scroll settings-sheet">
        <div className="debug-banner">
          <b>DEBUG ONLY</b>
          <span>아래 조작은 BE dev endpoint를 호출하며 현재 세션을 유지한 채 서버 상태를 변경합니다.</span>
        </div>

        <dl className="session-debug-meta">
          <div><dt>session</dt><dd>{session.sessionId}</dd></div>
          <div><dt>case</dt><dd>{session.caseId}</dd></div>
          <div><dt>selected</dt><dd>{session.selectedSuspectId}</dd></div>
          <div><dt>source</dt><dd>{session.source ?? "api"}</dd></div>
        </dl>

        <section className="debug-section" aria-label="캐릭터 압박 수치 조정">
          <h3>Pressure / Tension</h3>
          {session.suspects.map((suspect) => (
            <label key={suspect.id} className="pressure-row">
              <span>
                <b>{suspect.name}</b>
                <small>{suspect.id} · {suspect.status}</small>
              </span>
              <output>{suspect.pressure}</output>
              <input
                type="range"
                min="0"
                max="100"
                step="5"
                value={suspect.pressure}
                disabled={busy}
                onChange={(event) => onAdjustPressure(suspect.id, Number(event.target.value))}
              />
            </label>
          ))}
        </section>

        <section className="debug-section" aria-label="공개 단서 해금">
          <h3>BE-backed Unlocks</h3>
          <div className="debug-action-grid">
            <button type="button" disabled={busy} onClick={() => onUnlock("evidence")}>Unlock Evidence</button>
            <button type="button" disabled={busy} onClick={() => onUnlock("relations")}>Unlock Relations</button>
            <button type="button" disabled={busy} onClick={() => onUnlock("timeline")}>Unlock Timeline</button>
            <button type="button" disabled={busy} onClick={() => onUnlock("notes")}>Sync Debug Note</button>
            <button type="button" disabled={busy} onClick={() => onUnlock("all")}>Unlock All Public</button>
          </div>
        </section>

        <section className="debug-section reset-section" aria-label="명시적 세션 초기화">
          <h3>Session</h3>
          <button type="button" disabled={busy} onClick={onReset}>Reset / New Session</button>
        </section>
      </section>
    </aside>
  );
}
