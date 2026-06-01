import { evidenceAsset, lockedEvidenceAssetPath } from "../constants/presentation";
import type { GameSessionView } from "../types";
import { sanitizePublicIds, sanitizeSourceRefs } from "../utils/publicDiagnostics";

type DrawerMode = "case" | "evidence" | "notes" | "contradiction" | "relations" | "accusation";

type InvestigationDrawerProps = {
  mode: DrawerMode;
  session: GameSessionView;
  inspectedEvidenceId: string | null;
  selectedEvidenceIds: string[];
  selectedStatementIds: string[];
  draftNote: string;
  editingNoteId: string | null;
  editingNoteText: string;
  busy: boolean;
  accusationSuspectId: string;
  accusationMotive: string;
  accusationMethod: string;
  onClose: () => void;
  onOpenMode: (mode: DrawerMode) => void;
  onInspectEvidence: (evidenceId: string) => void;
  onToggleEvidence: (evidenceId: string) => void;
  onSelectStatement: (statementId: string) => void;
  onDraftNoteChange: (value: string) => void;
  onEditingNoteTextChange: (value: string) => void;
  onAddNote: () => void;
  onStartEditNote: (noteId: string) => void;
  onCancelEditNote: () => void;
  onSaveEditedNote: () => void;
  onRemoveNote: (noteId: string) => void;
  onSubmitContradiction: () => void;
  onAccusationSuspectChange: (suspectId: string) => void;
  onAccusationMotiveChange: (value: string) => void;
  onAccusationMethodChange: (value: string) => void;
  onSubmitAccusation: () => void;
};

export function InvestigationDrawer({
  mode,
  session,
  inspectedEvidenceId,
  selectedEvidenceIds,
  selectedStatementIds,
  draftNote,
  editingNoteId,
  editingNoteText,
  busy,
  accusationSuspectId,
  accusationMotive,
  accusationMethod,
  onClose,
  onOpenMode,
  onInspectEvidence,
  onToggleEvidence,
  onSelectStatement,
  onDraftNoteChange,
  onEditingNoteTextChange,
  onAddNote,
  onStartEditNote,
  onCancelEditNote,
  onSaveEditedNote,
  onRemoveNote,
  onSubmitContradiction,
  onAccusationSuspectChange,
  onAccusationMotiveChange,
  onAccusationMethodChange,
  onSubmitAccusation,
}: InvestigationDrawerProps) {
  const evidence = session.evidence.find((item) => item.id === inspectedEvidenceId) ?? session.evidence.find((item) => item.unlocked) ?? session.evidence[0];
  const selectedStatement = session.statements.find((item) => selectedStatementIds.includes(item.id));
  const selectedEvidence = session.evidence.filter((item) => selectedEvidenceIds.includes(item.id));
  const activeStatements = session.selectedSuspectId
    ? session.statements.filter((item) => item.unlocked && item.suspectId === session.selectedSuspectId)
    : [];

  return (
    <aside className="investigation-drawer" aria-label="수사 자료 상세 패널">
      <header>
        <strong>{drawerTitle(mode)}</strong>
        <button type="button" onClick={onClose} aria-label="수사 자료 패널 닫기">×</button>
      </header>
      <nav aria-label="수사 자료 탭">
        <button className={mode === "case" ? "active" : ""} type="button" onClick={() => onOpenMode("case")}>사건 파일</button>
        <button className={mode === "evidence" ? "active" : ""} type="button" onClick={() => onOpenMode("evidence")}>증거 목록</button>
        <button className={mode === "notes" ? "active" : ""} type="button" onClick={() => onOpenMode("notes")}>메모</button>
        <button className={mode === "contradiction" ? "active" : ""} type="button" onClick={() => onOpenMode("contradiction")}>모순 제시</button>
        <button className={mode === "relations" ? "active" : ""} type="button" onClick={() => onOpenMode("relations")}>관계도</button>
        <button className={mode === "accusation" ? "active" : ""} type="button" onClick={() => onOpenMode("accusation")}>최종 고발</button>
      </nav>

      {mode === "case" ? (
        <section className="drawer-scroll case-file-sheet">
          <h3>{session.opening.hook}</h3>
          <p>{session.storyline.publicPremise}</p>
          <dl>
            <div><dt>현재 목표</dt><dd>{session.currentObjective.objective}</dd></div>
            <div><dt>플레이 힌트</dt><dd>{session.currentObjective.playerHint}</dd></div>
            <div><dt>승리 조건</dt><dd>{session.opening.victoryCondition}</dd></div>
          </dl>
          <h4>공개 타임라인</h4>
          {session.visibleTimeline.map((item) => (
            <article key={`${item.time}-${item.sourceId}`} className="timeline-row">
              <b>{item.time}</b>
              <span>{item.title}</span>
              <p>{item.description}</p>
            </article>
          ))}
          <h4>사건 기록</h4>
          {session.records.filter((item) => item.unlocked).map((item) => (
            <article key={item.id} className="record-row"><b>{item.time}</b><span>{item.title}</span><p>{item.description}</p></article>
          ))}
        </section>
      ) : null}

      {mode === "evidence" ? (
        <section className="drawer-scroll evidence-detail-layout">
          <div className="drawer-evidence-list">
            {session.evidence.map((item) => (
              <button
                type="button"
                key={item.id}
                className={`${item.id === evidence?.id ? "active" : ""} ${!item.unlocked ? "locked" : ""}`}
                disabled={!item.unlocked}
                onClick={() => onInspectEvidence(item.id)}
              >
                <img src={item.unlocked ? evidenceAsset(item.id) ?? lockedEvidenceAssetPath : lockedEvidenceAssetPath} alt="" />
                <span>{item.unlocked ? item.title : "잠긴 증거"}</span>
              </button>
            ))}
          </div>
          {evidence ? (
            <article className="evidence-detail-card">
              <img src={evidence.unlocked ? evidenceAsset(evidence.id) ?? lockedEvidenceAssetPath : lockedEvidenceAssetPath} alt={`${evidence.title} 상세 이미지`} />
              <h3>{evidence.title}</h3>
              <p>{evidence.unlocked ? evidence.description : "아직 공개되지 않은 증거입니다."}</p>
              <dl>
                <div><dt>발견 위치/source</dt><dd>{evidence.source}</dd></div>
                <div><dt>시간대</dt><dd>{evidence.time}</dd></div>
                <div><dt>신뢰도</dt><dd>{Math.round(evidence.reliability * 100)}%</dd></div>
                <div><dt>source refs</dt><dd>{formatRefs(evidence.sourceRefs)}</dd></div>
                <div><dt>연결 증언</dt><dd>{evidence.relatedStatementIds.join(", ") || "미연결"}</dd></div>
              </dl>
              <button type="button" onClick={() => onToggleEvidence(evidence.id)} disabled={!evidence.unlocked}>
                {selectedEvidenceIds.includes(evidence.id) ? "증거 선택 해제" : "모순 제시용 증거 선택"}
              </button>
            </article>
          ) : null}
        </section>
      ) : null}

      {mode === "notes" ? (
        <section className="drawer-scroll notes-sheet">
          <form onSubmit={(event) => { event.preventDefault(); onAddNote(); }}>
            <label htmlFor="note-input">새 메모</label>
            <textarea id="note-input" value={draftNote} onChange={(event) => onDraftNoteChange(event.target.value)} placeholder="탐문 중 발견한 단서나 의심점을 기록하세요." />
            <button type="submit" disabled={busy || !draftNote.trim()}>메모 저장</button>
          </form>
          {session.notes.length > 0 ? session.notes.map((note) => (
            <article key={note.id} className="note-card">
              {editingNoteId === note.id ? (
                <form className="note-edit-form" onSubmit={(event) => { event.preventDefault(); onSaveEditedNote(); }}>
                  <label htmlFor={`note-edit-${note.id}`}>메모 수정</label>
                  <textarea id={`note-edit-${note.id}`} value={editingNoteText} onChange={(event) => onEditingNoteTextChange(event.target.value)} />
                  <div>
                    <button type="submit" disabled={busy || !editingNoteText.trim()}>수정 저장</button>
                    <button type="button" onClick={onCancelEditNote}>취소</button>
                  </div>
                </form>
              ) : (
                <p>{note.text}</p>
              )}
              <small>tags: {note.tags.join(", ") || "none"}</small>
              <small>links: {[...note.linkedStatementIds, ...note.linkedEvidenceIds, ...note.linkedRecordIds].join(", ") || "none"}</small>
              {editingNoteId !== note.id ? (
                <div className="note-actions">
                  <button type="button" onClick={() => onStartEditNote(note.id)} disabled={busy}>수정</button>
                  <button type="button" onClick={() => onRemoveNote(note.id)} disabled={busy}>삭제</button>
                </div>
              ) : null}
            </article>
          )) : <p className="empty-copy">서버 노트가 아직 없습니다. 위 입력창에서 직접 메모를 저장해 갱신을 확인하세요.</p>}
        </section>
      ) : null}

      {mode === "contradiction" ? (
        <section className="drawer-scroll contradiction-builder">
          <div className="selection-summary">
            <b>선택된 증언</b><span>{selectedStatement ? `${selectedStatement.speaker}: ${selectedStatement.text}` : "증언을 선택하세요"}</span>
            <b>선택된 증거</b><span>{selectedEvidence.map((item) => item.title).join(", ") || "증거를 선택하세요"}</span>
          </div>
          <h3>용의자 증언 선택</h3>
          {!session.selectedSuspectId ? <p className="empty-copy">먼저 용의자를 명시적으로 선택해야 해당 용의자의 BE 공개 증언을 고를 수 있습니다.</p> : null}
          {activeStatements.map((statement) => (
            <button key={statement.id} type="button" className={selectedStatementIds.includes(statement.id) ? "selected" : ""} onClick={() => onSelectStatement(statement.id)}>
              <strong>{statement.speaker}</strong><span>{statement.text}</span><small>{statement.time} · {statement.place}</small>
            </button>
          ))}
          <h3>증거 선택</h3>
          {session.evidence.filter((item) => item.unlocked).map((item) => (
            <button key={item.id} type="button" className={selectedEvidenceIds.includes(item.id) ? "selected" : ""} onClick={() => onToggleEvidence(item.id)}>
              <strong>{item.title}</strong><span>{item.description}</span><small>{item.time} · reliability {Math.round(item.reliability * 100)}%</small>
            </button>
          ))}
          <button className="submit-contradiction" type="button" onClick={onSubmitContradiction} disabled={busy || selectedStatementIds.length === 0 || selectedEvidenceIds.length === 0}>
            선택한 증언+증거로 모순 제시
          </button>
        </section>
      ) : null}

      {mode === "accusation" ? (
        <section className="drawer-scroll final-accusation-sheet">
          <h3>최종 고발</h3>
          <p className="empty-copy">최종 판정은 BE accusation endpoint 응답만 반영됩니다. 실패 시 로컬 판정은 생성하지 않습니다.</p>
          <fieldset>
            <legend>고발 대상</legend>
            {session.suspects.map((suspect) => (
              <label key={suspect.id}>
                <input
                  type="radio"
                  name="accused-suspect"
                  value={suspect.id}
                  checked={accusationSuspectId === suspect.id}
                  onChange={() => onAccusationSuspectChange(suspect.id)}
                />
                <span>{suspect.name} ({suspect.role})</span>
              </label>
            ))}
          </fieldset>
          <label htmlFor="accusation-motive">동기 메모</label>
          <textarea id="accusation-motive" value={accusationMotive} onChange={(event) => onAccusationMotiveChange(event.target.value)} placeholder="BE에 함께 보낼 공개 추론 메모를 입력하세요." />
          <label htmlFor="accusation-method">방법 메모</label>
          <textarea id="accusation-method" value={accusationMethod} onChange={(event) => onAccusationMethodChange(event.target.value)} placeholder="증거와 증언으로 설명 가능한 방법만 적으세요." />
          <dl className="accusation-context">
            <div><dt>선택 증거</dt><dd>{selectedEvidence.map((item) => item.title).join(", ") || "없음"}</dd></div>
            <div><dt>선택 증언</dt><dd>{selectedStatement ? selectedStatement.id : "없음"}</dd></div>
            <div><dt>발견 모순</dt><dd>{session.foundContradictionIds.join(", ") || "없음"}</dd></div>
          </dl>
          {session.result ? (
            <article className="verdict-card">
              <b>{session.result.title}</b>
              <p>{session.result.message}</p>
            </article>
          ) : null}
          <button
            className="submit-contradiction"
            type="button"
            onClick={onSubmitAccusation}
            disabled={busy || !accusationSuspectId || !accusationMotive.trim() || !accusationMethod.trim()}
          >
            BE로 최종 고발 제출
          </button>
        </section>
      ) : null}

      {mode === "relations" ? (
        <section className="drawer-scroll relation-map-sheet">
          <div className="relation-map-stage" aria-label="인물 관계도">
            {session.relationMap ? (
              <>
                <div className="victim-node">{session.relationMap.nodes.find((node) => node.kind === "victim" || node.characterId.includes("victim"))?.name ?? "강도준"}<br /><small>피해자</small></div>
                {session.relationMap.edges.map((edge, index) => {
                  const node = session.relationMap?.nodes.find((item) => item.characterId === edge.sourceCharacterId || item.characterId === edge.targetCharacterId);
                  const suspect = session.suspects.find((item) => item.id === node?.characterId) ?? session.suspects[index % Math.max(1, session.suspects.length)];
                  return (
                    <article key={edge.relationshipId} className={`relation-node relation-pos-${(index % 4) + 1} ${edge.unlocked ? "unlocked" : "locked"}`}>
                      <img src={`/assets/char_${suspect.id.replace("char_", "")}_neutral.png`} alt="" />
                      <strong>{node?.name ?? suspect.name}</strong>
                      <span>{edge.unlocked ? edge.label || edge.conflict : "관계 단서 잠김"}</span>
                    </article>
                  );
                })}
              </>
            ) : session.suspects.map((suspect, index) => {
              const relation = session.relations.find((item) => item.suspectId === suspect.id);
              return (
                <article key={suspect.id} className={`relation-node relation-pos-${index + 1} ${relation?.unlocked ? "unlocked" : "locked"}`}>
                  <img src={`/assets/char_${suspect.id.replace("char_", "")}_neutral.png`} alt="" />
                  <strong>{suspect.name}</strong>
                  <span>{relation?.unlocked ? relation.conflict : "관계 단서 잠김"}</span>
                </article>
              );
            })}
          </div>
          <h3>공개 관계 단서</h3>
          {session.relationMap?.edges.map((edge) => (
            <article key={edge.relationshipId} className={`relation-detail ${edge.unlocked ? "unlocked" : "locked"}`}>
              <b>{edge.label || edge.relationshipId}</b>
              <span>{edge.unlocked ? edge.conflict : "잠긴 관계"}</span>
              <p>{edge.unlocked ? edge.description : "대화/증거 진행 후 BE 세션에서 공개됩니다."}</p>
              <small>refs: {sanitizePublicIds([...edge.evidenceRefs, ...edge.statementRefs, ...edge.recordRefs]).join(", ") || "none"}</small>
            </article>
          )) ?? session.relations.map((relation) => (
            <article key={relation.id} className={`relation-detail ${relation.unlocked ? "unlocked" : "locked"}`}>
              <b>{relation.suspectName}</b>
              <span>{relation.unlocked ? relation.conflict : "잠긴 관계"}</span>
              <p>{relation.unlocked ? relation.description : "대화/증거 진행 후 BE 세션에서 공개됩니다."}</p>
              <small>relationId: {relation.id}</small>
            </article>
          ))}
        </section>
      ) : null}
    </aside>
  );
}

function drawerTitle(mode: DrawerMode) {
  if (mode === "case") return "사건 파일";
  if (mode === "evidence") return "증거 목록 / 상세";
  if (mode === "notes") return "수사 메모";
  if (mode === "relations") return "인물 관계도";
  if (mode === "accusation") return "최종 고발";
  return "모순 제시";
}

function formatRefs(refs?: Record<string, string[]>) {
  const sanitized = sanitizeSourceRefs(refs);
  if (!sanitized) return "미수신";
  return Object.entries(sanitized).map(([key, values]) => `${key}:${values.join("|")}`).join(" · ") || "미수신";
}
