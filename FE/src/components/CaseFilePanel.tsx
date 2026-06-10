import type { GameSessionView } from "../types";

type CaseFilePanelProps = {
  session: GameSessionView;
};

const HERO_LIMIT = 86;
const ROW_LIMIT = 58;
const TIMELINE_PREVIEW_LIMIT = 5;
const RECORD_PREVIEW_LIMIT = 4;

function compactText(value: string, limit: number) {
  const firstSentence = value.split(/(?<=[.!?。！？])\s+|(?<=다\.)\s*/)[0]?.trim() || value.trim();
  return firstSentence.length > limit ? `${firstSentence.slice(0, limit).trim()}…` : firstSentence;
}

export function CaseFilePanel({ session }: CaseFilePanelProps) {
  const unlockedRecords = session.records.filter((item) => item.unlocked);
  const timelinePreview = session.visibleTimeline.slice(0, TIMELINE_PREVIEW_LIMIT);
  const recordPreview = unlockedRecords.slice(0, RECORD_PREVIEW_LIMIT);
  const hiddenTimelineCount = Math.max(0, session.visibleTimeline.length - timelinePreview.length);
  const hiddenRecordCount = Math.max(0, unlockedRecords.length - recordPreview.length);

  return (
    <aside className="panel case-file-panel" aria-labelledby="case-file-panel-title">
      <div className="section-title">
        <h2 id="case-file-panel-title">사건 파일</h2>
        <span>CASE FILE</span>
      </div>

      <div className="case-file-scroll">
        <div className="case-file-hero">
          <h3>{session.opening.hook}</h3>
          <p>{compactText(session.storyline.publicPremise, HERO_LIMIT)}</p>
        </div>

        <dl className="case-file-facts">
          <div><dt>수사 단계</dt><dd>{session.currentObjective.title}</dd></div>
          <div><dt>남은 질문</dt><dd>{session.remainingQuestions}회</dd></div>
          <div><dt>진행 상태</dt><dd>{session.phase}</dd></div>
        </dl>

        <div className="case-file-section-heading">
          <h4>공개 타임라인</h4>
          <span>{session.visibleTimeline.length}</span>
        </div>
        <div className="case-file-timeline">
          {timelinePreview.length > 0 ? timelinePreview.map((item) => (
            <article key={`${item.time}-${item.sourceId}`} className="case-file-timeline-row">
              <b>{item.time}</b>
              <div><span>{item.title}</span><p>{compactText(item.description, ROW_LIMIT)}</p></div>
            </article>
          )) : <p className="empty-inline">공개된 타임라인이 없습니다.</p>}
          {hiddenTimelineCount > 0 ? <p className="case-file-more">+{hiddenTimelineCount}건은 상세 파일에서 확인</p> : null}
        </div>

        <div className="case-file-section-heading">
          <h4>사건 기록</h4>
          <span>{unlockedRecords.length}</span>
        </div>
        <div className="case-file-records">
          {recordPreview.length > 0 ? recordPreview.map((item) => (
            <article key={item.id} className="case-file-record-row">
              <b>{item.time}</b>
              <span>{item.title}</span>
              <p>{compactText(item.description, ROW_LIMIT)}</p>
            </article>
          )) : <p className="empty-inline">아직 공개된 사건 기록이 없습니다.</p>}
          {hiddenRecordCount > 0 ? <p className="case-file-more">+{hiddenRecordCount}건은 증거 목록에서 확인</p> : null}
        </div>
      </div>
    </aside>
  );
}
