type AppHeaderProps = {
  onOpenCaseFile: () => void;
  onOpenEvidence: () => void;
  onOpenNotes: () => void;
  onOpenRelations: () => void;
  onOpenAccusation: () => void;
  onOpenSettings: () => void;
};

export function AppHeader({ onOpenCaseFile, onOpenEvidence, onOpenNotes, onOpenRelations, onOpenAccusation, onOpenSettings }: AppHeaderProps) {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand-icon" aria-hidden="true">⚖</span>
        <h1>알리바이 교차검증형 추리 게임</h1>
      </div>
      <nav aria-label="수사 메뉴" className="header-actions">
        <button type="button" onClick={onOpenCaseFile}>▣ 사건 파일</button>
        <button type="button" onClick={onOpenEvidence}>▤ 증거 목록</button>
        <button type="button" onClick={onOpenNotes}>▥ 메모</button>
        <button type="button" onClick={onOpenRelations}>◎ 관계도</button>
        <button type="button" onClick={onOpenAccusation}>⚑ 최종 고발</button>
        <button type="button" aria-label="설정" onClick={onOpenSettings}>⚙</button>
      </nav>
    </header>
  );
}
