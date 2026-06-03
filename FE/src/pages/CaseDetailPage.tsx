import { useEffect, useState } from "react";
import { createSession, getCaseDetail } from "../api";
import { caseCoverAsset } from "../constants/presentation";
import { caseListPath, sessionPath } from "../routing";
import { clearStoredSession, saveStoredSession } from "../storage";
import type { CaseDetail } from "../types";
import { createActionTimer } from "../utils/observability";

type CaseDetailPageProps = {
  caseId: string;
  onNavigate: (path: string) => void;
};

export function CaseDetailPage({ caseId, onNavigate }: CaseDetailPageProps) {
  const [caseFile, setCaseFile] = useState<CaseDetail | null>(null);
  const [busy, setBusy] = useState(true);
  const [starting, setStarting] = useState(false);
  const [statusMessage, setStatusMessage] = useState("사건 브리핑을 불러오는 중입니다.");

  useEffect(() => {
    setBusy(true);
    const done = createActionTimer({ component: "CaseDetailPage", action: "load_case_detail", caseId });
    getCaseDetail(caseId)
      .then((item) => {
        setCaseFile(item);
        setStatusMessage("공개 브리핑 준비 완료");
        done({ level: "info" });
      })
      .catch((error: unknown) => {
        setCaseFile(null);
        setStatusMessage("사건 상세 API를 불러오지 못했습니다.");
        done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
      })
      .finally(() => setBusy(false));
  }, [caseId]);

  async function startInvestigation() {
    if (!caseFile || starting) return;
    setStarting(true);
    clearStoredSession();
    setStatusMessage("서버 세션을 생성하는 중입니다.");
    const done = createActionTimer({ component: "CaseDetailPage", action: "start_session", caseId: caseFile.id });
    try {
      const created = await createSession(caseFile.id);
      saveStoredSession(created);
      done({ level: created.source === "local" ? "warn" : "info", sessionId: created.sessionId, fallbackUsed: created.source === "local" });
      onNavigate(sessionPath(created.sessionId));
    } catch (error) {
      setStatusMessage("세션 생성 실패: BE /api/v1/sessions 계약과 caseId를 확인해야 합니다.");
      done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
    } finally {
      setStarting(false);
    }
  }

  const coverAsset = caseFile ? caseCoverAsset(caseFile.id, caseFile.sceneId) : undefined;

  return (
    <main className="case-detail-desk" aria-label="사건 브리핑">
      <section className="case-detail-hero" aria-labelledby="case-detail-title">
        <button type="button" className="back-link" onClick={() => onNavigate(caseListPath())}>
          ← 사건 목록
        </button>
        <div>
          <span>Public Case Briefing</span>
          <h1 id="case-detail-title">{caseFile?.title ?? caseId}</h1>
          <p>{caseFile?.summary ?? "백엔드 공개 사건 정보를 기다리는 중입니다."}</p>
        </div>
      </section>

      <section className="case-briefing-panel panel">
        <div className="case-briefing-media">
          {coverAsset ? <img src={coverAsset} alt="" /> : <strong>{caseId}</strong>}
        </div>

        {caseFile ? (
          <div className="case-briefing-copy">
            <dl className="case-meta case-detail-meta">
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

            <article className="briefing-block">
              <span>목표</span>
              <h2>{caseFile.opening?.objective ?? "공개 목표 미수신"}</h2>
              <p>{caseFile.publicPremise ?? caseFile.opening?.hook ?? "공개 premise 미수신"}</p>
            </article>

            <div className="briefing-counters" aria-label="공개 조사 자료">
              <span>용의자 {caseFile.suspectCount}</span>
              <span>증거 {caseFile.visibleEvidenceCount}</span>
              <span>기록 {caseFile.visibleRecordCount}</span>
              <span>진술 {caseFile.visibleStatementCount}</span>
            </div>

            <button type="button" className="start-investigation-button" disabled={starting} onClick={startInvestigation}>
              {starting ? "세션 생성 중" : "수사 시작"}
            </button>
          </div>
        ) : (
          <div className="scenario-empty" role="status" aria-live="polite">
            <strong>{busy ? "브리핑 로딩 중" : "사건 브리핑을 표시할 수 없습니다."}</strong>
            <p>{statusMessage}</p>
          </div>
        )}

        <footer className="scenario-status" aria-live="polite">
          <span className={busy || starting ? "status-pulse" : ""} aria-hidden="true" />
          {statusMessage}
        </footer>
      </section>
    </main>
  );
}
