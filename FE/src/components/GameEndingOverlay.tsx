import type { GameSessionView, ResultView } from "../types";

type GameEndingOverlayProps = {
  result: ResultView;
  session: GameSessionView;
  onOpenDossier: () => void;
  onReturnToCases: () => void;
};

export function GameEndingOverlay({ result, session, onOpenDossier, onReturnToCases }: GameEndingOverlayProps) {
  const victory = result.outcome === "victory";
  const suspectName = session.suspects.find((suspect) => suspect.id === session.selectedSuspectId)?.name;
  const missedClues = result.missedClues.filter(Boolean).slice(0, 4);
  const headline = victory ? "사건 해결" : "잘못된 범인";
  const stamp = victory ? "GAME CLEAR" : "GAME FAILED";
  const ariaLabel = victory ? "게임 클리어 결과" : "게임 실패 결과";
  const overlayClassName = victory ? "ending-overlay victory" : "ending-overlay defeat";

  return (
    <section className="ending-overlay-backdrop" aria-live="assertive" aria-label={ariaLabel}>
      <article className={overlayClassName} role="dialog" aria-modal="true" aria-labelledby="ending-title">
        <div className="ending-stamp" aria-hidden="true">{stamp}</div>
        <div className="ending-copy">
          <span>{headline}</span>
          <h2 id="ending-title">{result.title}</h2>
          <p>{result.message}</p>
        </div>
        <dl className="ending-stats" aria-label="최종 수사 기록">
          <div>
            <dt>판정</dt>
            <dd>{victory ? "범인 특정 성공" : "범인 지목 실패"}</dd>
          </div>
          <div>
            <dt>사용 질문</dt>
            <dd>{result.usedQuestions}/{session.questionLimit}</dd>
          </div>
          <div>
            <dt>확정 모순</dt>
            <dd>{result.foundContradictions.length}</dd>
          </div>
          <div>
            <dt>마지막 대상</dt>
            <dd>{suspectName ?? session.selectedSuspectId ?? "미기록"}</dd>
          </div>
        </dl>
        {!victory ? (
          <div className="ending-failure-note">
            <strong>실패 조건</strong>
            <p>최종 고발에서 실제 범인이 아닌 인물을 지목했습니다. 관계도와 해금된 증거를 다시 대조하세요.</p>
            {missedClues.length > 0 ? <small>추가 확인 필요: {missedClues.join(" · ")}</small> : null}
          </div>
        ) : (
          <div className="ending-victory-note">
            <strong>클리어 조건</strong>
            <p>공개 단서와 모순을 통해 범인을 특정했습니다. 최종 기록은 수사 파일에 보존됩니다.</p>
          </div>
        )}
        <div className="ending-actions">
          <button type="button" onClick={onOpenDossier}>최종 고발 기록 보기</button>
          <button type="button" className="secondary" onClick={onReturnToCases}>사건 목록으로</button>
        </div>
      </article>
    </section>
  );
}
