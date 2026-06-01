import { evidenceAsset, lockedEvidenceAssetPath } from "../constants/presentation";
import type { GameSessionView, RelationMapEdge, RelationMapNode, Suspect } from "../types";
import { sanitizePublicIds, sanitizeSourceRefs } from "../utils/publicDiagnostics";

type DrawerMode = "case" | "evidence" | "notes" | "relations" | "accusation";

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
  onDraftNoteChange: (value: string) => void;
  onEditingNoteTextChange: (value: string) => void;
  onAddNote: () => void;
  onStartEditNote: (noteId: string) => void;
  onCancelEditNote: () => void;
  onSaveEditedNote: () => void;
  onRemoveNote: (noteId: string) => void;
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
  onDraftNoteChange,
  onEditingNoteTextChange,
  onAddNote,
  onStartEditNote,
  onCancelEditNote,
  onSaveEditedNote,
  onRemoveNote,
  onAccusationSuspectChange,
  onAccusationMotiveChange,
  onAccusationMethodChange,
  onSubmitAccusation,
}: InvestigationDrawerProps) {
  const evidence = session.evidence.find((item) => item.id === inspectedEvidenceId) ?? session.evidence.find((item) => item.unlocked) ?? session.evidence[0];
  const selectedEvidence = session.evidence.filter((item) => selectedEvidenceIds.includes(item.id));
  const selectedStatements = session.statements.filter((item) => selectedStatementIds.includes(item.id));
  const notebookProof = proofFromNotebook(session);
  const accusationReady = session.accusationReadiness;
  const unlockedEvidence = session.evidence.filter((item) => item.unlocked);
  const lockedEvidenceCount = session.evidence.length - unlockedEvidence.length;
  const unlockedRecords = session.records.filter((item) => item.unlocked);

  return (
    <aside className="investigation-drawer clean-drawer" aria-label="수사 자료 상세 패널">
      <header>
        <div>
          <small>INVESTIGATION DESK</small>
          <strong>{drawerTitle(mode)}</strong>
        </div>
        <button type="button" onClick={onClose} aria-label="수사 자료 패널 닫기">×</button>
      </header>
      <nav aria-label="수사 자료 탭">
        <button className={mode === "case" ? "active" : ""} type="button" onClick={() => onOpenMode("case")}>사건 파일</button>
        <button className={mode === "evidence" ? "active" : ""} type="button" onClick={() => onOpenMode("evidence")}>증거 목록</button>
        <button className={mode === "notes" ? "active" : ""} type="button" onClick={() => onOpenMode("notes")}>메모</button>
        <button className={mode === "relations" ? "active" : ""} type="button" onClick={() => onOpenMode("relations")}>관계도</button>
        <button className={mode === "accusation" ? "active" : ""} type="button" onClick={() => onOpenMode("accusation")}>최종 고발</button>
      </nav>

      {mode === "case" ? (
        <section className="drawer-scroll case-file-sheet clean-case-file">
          <div className="drawer-hero-card">
            <span>CASE FILE</span>
            <h3>{session.opening.hook}</h3>
            <p>{session.storyline.publicPremise}</p>
          </div>
          <dl className="case-facts-grid">
            <div><dt>현재 목표</dt><dd>{session.currentObjective.objective}</dd></div>
            <div><dt>승리 조건</dt><dd>{session.opening.victoryCondition}</dd></div>
            <div><dt>남은 질문</dt><dd>{session.remainingQuestions}회</dd></div>
            <div><dt>진행 상태</dt><dd>{session.phase}</dd></div>
          </dl>
          <div className="drawer-section-heading"><h4>공개 타임라인</h4><span>{session.visibleTimeline.length}</span></div>
          <div className="clean-timeline-list">
            {session.visibleTimeline.map((item) => (
              <article key={`${item.time}-${item.sourceId}`} className="timeline-row">
                <b>{item.time}</b>
                <div><span>{item.title}</span><p>{item.description}</p></div>
              </article>
            ))}
          </div>
          <div className="drawer-section-heading"><h4>사건 기록</h4><span>{unlockedRecords.length}</span></div>
          <div className="clean-record-grid">
            {unlockedRecords.map((item) => (
              <article key={item.id} className="record-row"><b>{item.time}</b><span>{item.title}</span><p>{item.description}</p></article>
            ))}
            {unlockedRecords.length === 0 ? <p className="empty-copy">아직 공개된 사건 기록이 없습니다.</p> : null}
          </div>
        </section>
      ) : null}

      {mode === "evidence" ? (
        <section className="drawer-scroll evidence-detail-layout clean-evidence-layout">
          <div className="drawer-evidence-list">
            <div className="drawer-list-summary"><b>{unlockedEvidence.length}</b><span>공개 증거</span><small>잠김 {lockedEvidenceCount}</small></div>
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
                <small>{item.unlocked ? `${item.type} · ${item.time}` : "진행 후 공개"}</small>
              </button>
            ))}
          </div>
          {evidence ? (
            <article className="evidence-detail-card clean-evidence-card">
              <img src={evidence.unlocked ? evidenceAsset(evidence.id) ?? lockedEvidenceAssetPath : lockedEvidenceAssetPath} alt={`${evidence.title} 상세 이미지`} />
              <div className="evidence-card-title">
                <span>{evidence.type}</span>
                <h3>{evidence.unlocked ? evidence.title : "잠긴 증거"}</h3>
              </div>
              <p>{evidence.unlocked ? evidence.description : "아직 공개되지 않은 증거입니다."}</p>
              <dl>
                <div><dt>발견 위치</dt><dd>{evidence.source}</dd></div>
                <div><dt>시간대</dt><dd>{evidence.time}</dd></div>
                <div><dt>신뢰도</dt><dd>{Math.round(evidence.reliability * 100)}%</dd></div>
                <div><dt>연결 증언</dt><dd>{evidence.relatedStatementIds.join(", ") || "미연결"}</dd></div>
                <div><dt>공개 참조</dt><dd>{formatRefs(evidence.sourceRefs)}</dd></div>
              </dl>
              <button type="button" onClick={() => onToggleEvidence(evidence.id)} disabled={!evidence.unlocked}>
                {selectedEvidenceIds.includes(evidence.id) ? "선택 해제" : "증거 선택"}
              </button>
            </article>
          ) : null}
        </section>
      ) : null}

      {mode === "notes" ? (
        <section className="drawer-scroll notes-sheet clean-notes-sheet">
          <form onSubmit={(event) => { event.preventDefault(); onAddNote(); }}>
            <label htmlFor="note-input">새 메모</label>
            <textarea id="note-input" value={draftNote} onChange={(event) => onDraftNoteChange(event.target.value)} placeholder="탐문 중 발견한 단서, 의심점, 연결해야 할 증거를 기록하세요." />
            <button type="submit" disabled={busy || !draftNote.trim()}>메모 저장</button>
          </form>
          <div className="note-list">
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
                <div className="note-meta-row">
                  <small>{note.tags.length ? note.tags.join(", ") : "태그 없음"}</small>
                  <small>{[...note.linkedStatementIds, ...note.linkedEvidenceIds, ...note.linkedRecordIds].length} links</small>
                </div>
                {editingNoteId !== note.id ? (
                  <div className="note-actions">
                    <button type="button" onClick={() => onStartEditNote(note.id)} disabled={busy}>수정</button>
                    <button type="button" onClick={() => onRemoveNote(note.id)} disabled={busy}>삭제</button>
                  </div>
                ) : null}
              </article>
            )) : <p className="empty-copy">아직 저장된 메모가 없습니다. 위 입력창에서 직접 메모를 남기세요.</p>}
          </div>
        </section>
      ) : null}

      {mode === "relations" ? (
        <section className="drawer-scroll relation-map-sheet clean-relation-sheet">
          <RelationMapView session={session} />
        </section>
      ) : null}

      {mode === "accusation" ? (
        <section className="drawer-scroll final-accusation-sheet clean-accusation-sheet">
          <h3>최종 고발</h3>
          <p className={accusationReady?.eligible ? "ready-copy" : "empty-copy"}>
            {accusationReady?.eligible
              ? "수첩의 공개 증언·증거 링크와 함께 최종 고발을 제출할 수 있습니다."
              : `필수 단서 진행: 증거 ${accusationReady?.discoveredRequiredEvidenceCount ?? 0}/${(accusationReady?.discoveredRequiredEvidenceCount ?? 0) + (accusationReady?.missingRequiredEvidenceCount ?? 0)} · 증언 ${accusationReady?.discoveredRequiredStatementCount ?? 0}/${(accusationReady?.discoveredRequiredStatementCount ?? 0) + (accusationReady?.missingRequiredStatementCount ?? 0)}`}
          </p>
          <fieldset>
            <legend>고발 대상</legend>
            {session.suspects.map((suspect) => (
              <label key={suspect.id}>
                <input type="radio" name="accused-suspect" value={suspect.id} checked={accusationSuspectId === suspect.id} onChange={() => onAccusationSuspectChange(suspect.id)} />
                <span>{suspect.name} ({suspect.role})</span>
              </label>
            ))}
          </fieldset>
          <label htmlFor="accusation-motive">동기 메모</label>
          <textarea id="accusation-motive" value={accusationMotive} onChange={(event) => onAccusationMotiveChange(event.target.value)} placeholder="공개 단서로 설명 가능한 동기를 입력하세요." />
          <label htmlFor="accusation-method">방법 메모</label>
          <textarea id="accusation-method" value={accusationMethod} onChange={(event) => onAccusationMethodChange(event.target.value)} placeholder="증거와 증언으로 설명 가능한 방법만 적으세요." />
          <dl className="accusation-context">
            <div><dt>선택 증거</dt><dd>{selectedEvidence.map((item) => item.title).join(", ") || "없음"}</dd></div>
            <div><dt>수첩 증거</dt><dd>{notebookProof.evidenceIds.join(", ") || "없음"}</dd></div>
            <div><dt>선택 증언</dt><dd>{selectedStatements.map((item) => item.id).join(", ") || "없음"}</dd></div>
            <div><dt>수첩 증언</dt><dd>{notebookProof.statementIds.join(", ") || "없음"}</dd></div>
          </dl>
          {session.result ? <article className="verdict-card"><b>{session.result.title}</b><p>{session.result.message}</p></article> : null}
          <button className="submit-contradiction" type="button" onClick={onSubmitAccusation} disabled={busy || !accusationSuspectId || !accusationMotive.trim() || !accusationMethod.trim()}>
            BE로 최종 고발 제출
          </button>
        </section>
      ) : null}
    </aside>
  );
}

function RelationMapView({ session }: { session: GameSessionView }) {
  const relationMap = session.relationMap;
  const victim = relationMap?.nodes.find((node) => node.kind === "victim" || node.characterId.includes("victim"));
  const suspects = session.suspects;
  const positions = buildRelationPositions(suspects);
  const edges = relationMap?.edges ?? [];

  return (
    <>
      <div className="relation-map-stage clean-relation-map" aria-label="인물 관계도">
        <svg className="relation-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          {suspects.map((suspect) => {
            const pos = positions[suspect.id];
            const edge = edgeForSuspect(edges, suspect.id);
            return <line key={suspect.id} x1="50" y1="50" x2={pos.x} y2={pos.y} className={edge?.unlocked ? "unlocked" : "locked"} />;
          })}
        </svg>
        <div className="victim-node clean-node" style={{ left: "50%", top: "50%" }}>
          <strong>{victim?.name ?? "강도준"}</strong><small>피해자</small>
        </div>
        {suspects.map((suspect) => {
          const pos = positions[suspect.id];
          const edge = edgeForSuspect(edges, suspect.id);
          return (
            <article key={suspect.id} className={`relation-node clean-node ${edge?.unlocked ? "unlocked" : "locked"}`} style={{ left: `${pos.x}%`, top: `${pos.y}%` }}>
              <img src={`/assets/char_${suspect.id.replace("char_", "")}_neutral.png`} alt="" />
              <strong>{suspect.name}</strong>
              <span>{edge?.unlocked ? edge.label || edge.conflict : "관계 단서 잠김"}</span>
            </article>
          );
        })}
      </div>
      <div className="drawer-section-heading"><h3>공개 관계 단서</h3><span>{edges.filter((edge) => edge.unlocked).length}/{edges.length || session.relations.length}</span></div>
      <div className="relation-detail-grid">
        {edges.length > 0 ? edges.map((edge) => <RelationDetail key={edge.relationshipId} edge={edge} nodes={relationMap?.nodes ?? []} />) : session.relations.map((relation) => (
          <article key={relation.id} className={`relation-detail ${relation.unlocked ? "unlocked" : "locked"}`}>
            <b>{relation.suspectName}</b>
            <span>{relation.unlocked ? relation.conflict : "잠긴 관계"}</span>
            <p>{relation.unlocked ? relation.description : "대화/증거 진행 후 BE 세션에서 공개됩니다."}</p>
            <small>relationId: {relation.id}</small>
          </article>
        ))}
      </div>
    </>
  );
}

function RelationDetail({ edge, nodes }: { edge: RelationMapEdge; nodes: RelationMapNode[] }) {
  const source = nodes.find((node) => node.characterId === edge.sourceCharacterId)?.name ?? edge.sourceCharacterId;
  const target = nodes.find((node) => node.characterId === edge.targetCharacterId)?.name ?? edge.targetCharacterId;
  return (
    <article className={`relation-detail ${edge.unlocked ? "unlocked" : "locked"}`}>
      <b>{source} ↔ {target}</b>
      <span>{edge.unlocked ? edge.label || edge.conflict : "잠긴 관계"}</span>
      <p>{edge.unlocked ? edge.description : "대화/증거 진행 후 BE 세션에서 공개됩니다."}</p>
      <small>refs: {sanitizePublicIds([...edge.evidenceRefs, ...edge.statementRefs, ...edge.recordRefs]).join(", ") || "none"}</small>
    </article>
  );
}

function buildRelationPositions(suspects: Suspect[]) {
  const anchors = [
    { x: 20, y: 22 },
    { x: 80, y: 22 },
    { x: 22, y: 78 },
    { x: 78, y: 78 },
    { x: 50, y: 12 },
    { x: 50, y: 88 },
  ];
  return Object.fromEntries(suspects.map((suspect, index) => [suspect.id, anchors[index % anchors.length]]));
}

function edgeForSuspect(edges: RelationMapEdge[], suspectId: string) {
  return edges.find((edge) => edge.sourceCharacterId === suspectId || edge.targetCharacterId === suspectId);
}

function drawerTitle(mode: DrawerMode) {
  if (mode === "case") return "사건 파일";
  if (mode === "evidence") return "증거 목록";
  if (mode === "notes") return "수사 메모";
  if (mode === "relations") return "인물 관계도";
  return "최종 고발";
}

function proofFromNotebook(session: GameSessionView) {
  const evidenceNotes = session.notes.filter((note) => note.linkedStatementIds.length > 0 || note.linkedEvidenceIds.length > 0 || note.linkedRecordIds.length > 0);
  return {
    statementIds: Array.from(new Set(evidenceNotes.flatMap((note) => note.linkedStatementIds))),
    evidenceIds: Array.from(new Set(evidenceNotes.flatMap((note) => note.linkedEvidenceIds))),
  };
}

function formatRefs(refs?: Record<string, string[]>) {
  const sanitized = sanitizeSourceRefs(refs);
  if (!sanitized) return "미수신";
  return Object.entries(sanitized).map(([key, values]) => `${key}:${values.join("|")}`).join(" · ") || "미수신";
}
