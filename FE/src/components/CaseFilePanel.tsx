import type { GameSessionView } from "../types";

type CaseFilePanelProps = {
  session: GameSessionView;
};

export function CaseFilePanel({ session }: CaseFilePanelProps) {
  const unlockedRecords = session.records.filter((item) => item.unlocked);

  return (
    <aside className="panel case-file-panel" aria-labelledby="case-file-panel-title">
      <div className="section-title">
        <h2 id="case-file-panel-title">사건 파일</h2>
        <span>CASE FILE</span>
      </div>

      <div className="case-file-scroll">
        <div className="case-file-hero">
          <h3>{session.opening.hook}</h3>
          <p>{session.storyline.publicPremise}</p>
        </div>

        <dl className="case-file-facts">
          <div><dt>현재 목표</dt><dd>{session.currentObjective.objective}</dd></div>
          <div><dt>승리 조건</dt><dd>{session.opening.victoryCondition}</dd></div>
          <div><dt>남은 질문</dt><dd>{session.remainingQuestions}회</dd></div>
          <div><dt>진행 상태</dt><dd>{session.phase}</dd></div>
        </dl>

        <div className="case-file-section-heading">
          <h4>공개 타임라인</h4>
          <span>{session.visibleTimeline.length}</span>
        </div>
        <div className="case-file-timeline">
          {session.visibleTimeline.length > 0 ? session.visibleTimeline.map((item) => (
            <article key={`${item.time}-${item.sourceId}`} className="case-file-timeline-row">
              <b>{item.time}</b>
              <div><span>{item.title}</span><p>{item.description}</p></div>
            </article>
          )) : <p className="empty-inline">공개된 타임라인이 없습니다.</p>}
        </div>

        <div className="case-file-section-heading">
          <h4>사건 기록</h4>
          <span>{unlockedRecords.length}</span>
        </div>
        <div className="case-file-records">
          {unlockedRecords.length > 0 ? unlockedRecords.map((item) => (
            <article key={item.id} className="case-file-record-row">
              <b>{item.time}</b>
              <span>{item.title}</span>
              <p>{item.description}</p>
            </article>
          )) : <p className="empty-inline">아직 공개된 사건 기록이 없습니다.</p>}
        </div>
      </div>
    </aside>
  );
}
