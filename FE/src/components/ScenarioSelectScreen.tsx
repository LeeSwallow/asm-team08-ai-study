import { useMemo, useState } from "react";
import { caseCoverAsset } from "../constants/presentation";
import type { CaseSummary } from "../types";

type ScenarioSelectScreenProps = {
  cases: CaseSummary[];
  statusMessage: string;
  busy: boolean;
  resumableSessionId: string | null;
  onOpenCase?: (caseId: string) => void;
  onStartCase?: (caseId: string) => void;
  onResumeSession?: () => void;
};

export function ScenarioSelectScreen({ cases, statusMessage, busy, resumableSessionId, onOpenCase, onStartCase, onResumeSession }: ScenarioSelectScreenProps) {
  const hasCases = cases.length > 0;
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const selectedCase = useMemo(
    () => cases.find((caseFile) => caseFile.id === selectedCaseId),
    [cases, selectedCaseId],
  );

  return (
    <main className="scenario-desk" aria-label="사건 선택">
      <section className="scenario-hero" aria-labelledby="scenario-title">
        <div className="scenario-brand">
          <span className="brand-icon" aria-hidden="true">⚖</span>
          <div>
            <p>DETECTIVE DOSSIER</p>
            <h1 id="scenario-title">알리바이 교차검증형 추리 게임</h1>
          </div>
        </div>

        <div className="scenario-copy">
          <span>사건 파일 선택</span>
          <h2>조사할 시나리오를 선택하세요.</h2>
          <p>
            선택한 사건의 공개 브리핑으로 수사를 시작합니다. 용의자·증거·대화 기록은 진행 상황에 따라 갱신됩니다.
          </p>
        </div>
      </section>

      <section className="scenario-panel panel" aria-labelledby="case-list-title">
        <div className="section-title">
          <h2 id="case-list-title">사건 파일</h2>
          <span>{hasCases ? `${cases.length}개 공개` : "대기 중"}</span>
        </div>

        {hasCases ? (
          <div className="scenario-list">
            {cases.map((caseFile, index) => {
              const selected = selectedCase?.id === caseFile.id;
              const coverAsset = caseCoverAsset(caseFile.id, caseFile.sceneId);
              return (
              <article className={`scenario-card ${selected ? "selected" : ""} ${caseFile.enabled === false ? "locked" : ""}`} key={caseFile.id} aria-disabled={caseFile.enabled === false}>
                {caseFile.enabled === false && (
                  <div className="scenario-card-lock" aria-label="준비 중">
                    <span>🔒</span>
                    <strong>준비 중</strong>
                  </div>
                )}
                <div className="case-stamp" aria-hidden="true">
                  {coverAsset ? (
                    <img src={coverAsset} alt="" />
                  ) : (
                    <>CASE {String(index + 1).padStart(2, "0")}</>
                  )}
                </div>
                <div className="case-main">
                  <div>
                    <span>{caseFile.id}</span>
                    <h3>{caseFile.title}</h3>
                  </div>
                  <p>{caseFile.summary}</p>
                </div>
                <dl className="case-meta">
                  <div>
                    <dt>피해자</dt>
                    <dd>{caseFile.victim}</dd>
                  </div>
                  <div>
                    <dt>발생 시각</dt>
                    <dd>{caseFile.incidentTime}</dd>
                  </div>
                  <div>
                    <dt>장소</dt>
                    <dd>{caseFile.location}</dd>
                  </div>
                  <div>
                    <dt>질문 제한</dt>
                    <dd>{caseFile.questionLimit}회</dd>
                  </div>
                </dl>
                <button
                  type="button"
                  disabled={busy || caseFile.enabled === false}
                  aria-pressed={selected}
                  onClick={() => {
                    if (caseFile.enabled === false) return;
                    setSelectedCaseId(caseFile.id);
                    onOpenCase?.(caseFile.id);
                  }}
                >
                  {caseFile.enabled === false ? "업데이트 예정" : onOpenCase ? "사건 상세" : selected ? "선택됨" : "사건 읽어보기"}
                </button>
              </article>
            );
            })}
          </div>
        ) : (
          <div className="scenario-empty" role="status" aria-live="polite">
            <strong>공개 사건 파일을 불러오지 못했습니다.</strong>
            <p>공개 사건 파일이 준비되어야 시작할 수 있습니다.</p>
          </div>
        )}

        {(selectedCase && onStartCase) || (resumableSessionId && onResumeSession) ? (
          <aside className="scenario-start-bar" aria-label="선택한 사건 시작">
            <div>
              <span>{selectedCase ? "선택한 사건" : "저장된 수사"}</span>
              <strong>{selectedCase?.title ?? resumableSessionId}</strong>
            </div>
            {resumableSessionId && onResumeSession ? (
              <button type="button" className="resume-case-button" disabled={busy} onClick={onResumeSession}>
                이전 수사 이어하기
              </button>
            ) : null}
            {selectedCase && onStartCase ? (
              <button type="button" disabled={busy} onClick={() => onStartCase(selectedCase.id)}>
                {busy ? "수사 준비 중" : "선택한 사건 시작"}
              </button>
            ) : null}
          </aside>
        ) : null}

        <footer className="scenario-status" aria-live="polite">
          <span className={busy ? "status-pulse" : ""} aria-hidden="true" />
          {statusMessage}
        </footer>
      </section>
    </main>
  );
}
