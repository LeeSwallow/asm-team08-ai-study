import { evidenceAsset, lockedEvidenceAssetPath, statusLabels, suspectAsset } from "../constants/presentation";
import type { GameSessionView, RelationMapEdge, RelationMapNode, Statement, Suspect } from "../types";
import { sanitizePublicIds, sanitizeSourceRefs } from "../utils/publicDiagnostics";

type DrawerMode = "evidence" | "notes" | "relations" | "accusation";

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
  const lockedEvidenceCount = Math.max(0, session.totalEvidenceCount - unlockedEvidence.length);
  const statementsById = new Map(session.statements.map((item) => [item.id, item]));

  return (
    <aside className={`investigation-drawer clean-drawer ${mode === "accusation" ? "accusation-drawer" : ""}`} aria-label="수사 자료 상세 패널">
      <header>
        <div>
          <small>INVESTIGATION DESK</small>
          <strong>{drawerTitle(mode)}</strong>
        </div>
        <button type="button" onClick={onClose} aria-label="수사 자료 패널 닫기">×</button>
      </header>
      <nav aria-label="수사 자료 탭">
        <button className={mode === "evidence" ? "active" : ""} type="button" onClick={() => onOpenMode("evidence")}>증거 목록</button>
        <button className={mode === "notes" ? "active" : ""} type="button" onClick={() => onOpenMode("notes")}>메모</button>
        <button className={mode === "relations" ? "active" : ""} type="button" onClick={() => onOpenMode("relations")}>관계도</button>
        <button className={mode === "accusation" ? "active" : ""} type="button" onClick={() => onOpenMode("accusation")}>최종 고발</button>
      </nav>

      {mode === "evidence" ? (
        <section className="drawer-scroll evidence-detail-layout clean-evidence-layout">
          <div className="drawer-evidence-list">
            <div className="drawer-list-summary"><b>{unlockedEvidence.length}/{session.totalEvidenceCount}</b><span>공개 증거</span><small>잠김 {lockedEvidenceCount}</small></div>
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
                <div><dt>연결 증언</dt><dd>{formatStatementLabels(evidence.relatedStatementIds, statementsById)}</dd></div>
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
          <div className="accusation-hero">
            <span>FINAL DOSSIER</span>
            <h3>최종 고발 검토</h3>
            <p>최종 판정은 지금까지 확보한 공개 단서와 제출 근거를 기준으로 심사됩니다. 고발 대상, 동기, 방법이 모두 입력되어야 제출할 수 있습니다.</p>
          </div>
          <ReadinessDossier readiness={accusationReady} />
          <div className="accusation-layout">
            <fieldset className="accusation-suspect-field">
              <legend>고발 대상</legend>
              <div className="accusation-suspect-grid">
                {session.suspects.map((suspect) => (
                  <label key={suspect.id} className={`accusation-suspect-card ${accusationSuspectId === suspect.id ? "selected" : ""}`}>
                    <input type="radio" name="accused-suspect" value={suspect.id} checked={accusationSuspectId === suspect.id} onChange={() => onAccusationSuspectChange(suspect.id)} />
                    <img src={suspectAsset(suspect.id, suspect.expression)} alt="" />
                    <span>
                      <strong>{suspect.name}</strong>
                      <small>{suspect.role}</small>
                      <em>{statusLabels[suspect.status]} · 긴장 {suspect.tensionLevel ?? "low"} · 압박 {suspect.pressure}%</em>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="accusation-memo-grid">
              <label htmlFor="accusation-motive">동기 메모</label>
              <textarea id="accusation-motive" value={accusationMotive} onChange={(event) => onAccusationMotiveChange(event.target.value)} placeholder="공개 단서로 설명 가능한 동기를 입력하세요." />
              <label htmlFor="accusation-method">방법 메모</label>
              <textarea id="accusation-method" value={accusationMethod} onChange={(event) => onAccusationMethodChange(event.target.value)} placeholder="증거와 증언으로 설명 가능한 방법만 적으세요." />
            </div>
          </div>
          <ProofSummary
            selectedEvidence={selectedEvidence}
            notebookEvidenceIds={notebookProof.evidenceIds}
            selectedStatements={selectedStatements}
            notebookStatementIds={notebookProof.statementIds}
            contradictionIds={session.foundContradictionIds}
          />
          {session.result ? (
            <article className={`verdict-card ${session.result.outcome === "victory" ? "victory" : "defeat"}`}>
              <span>{session.result.outcome === "victory" ? "GAME CLEAR" : "GAME OVER"}</span>
              <b>{session.result.title}</b>
              <p>{session.result.message}</p>
              {session.result.missedClues.length > 0 ? <small>부족한 근거: {session.result.missedClues.join(", ")}</small> : null}
            </article>
          ) : null}
          <p className="accusation-submit-copy">
            {!accusationSuspectId || !accusationMotive.trim() || !accusationMethod.trim()
              ? "필수 입력: 고발 대상, 동기 메모, 방법 메모를 완성하세요."
              : accusationReady && !accusationReady.eligible
                ? "필수 단서가 아직 부족합니다. 제출은 가능하지만 근거 부족으로 기각될 수 있습니다."
                : "최종 제출 준비가 완료되었습니다. 제출 후 판정 결과가 수사 기록에 남습니다."}
          </p>
          <button className="submit-contradiction" type="button" onClick={onSubmitAccusation} disabled={busy || !accusationSuspectId || !accusationMotive.trim() || !accusationMethod.trim()}>
            최종 고발 제출
          </button>
        </section>
      ) : null}
    </aside>
  );
}

function ReadinessDossier({ readiness }: { readiness?: GameSessionView["accusationReadiness"] }) {
  const rows = [
    {
      label: "필수 모순",
      discovered: readiness?.discoveredRequiredContradictionCount ?? 0,
      required: readiness?.requiredContradictionCount ?? ((readiness?.discoveredRequiredContradictionCount ?? 0) + (readiness?.missingRequiredContradictionCount ?? 0)),
      missing: readiness?.missingRequiredContradictionCount ?? 0,
    },
    {
      label: "필수 증거",
      discovered: readiness?.discoveredRequiredEvidenceCount ?? 0,
      required: readiness?.requiredEvidenceCount ?? ((readiness?.discoveredRequiredEvidenceCount ?? 0) + (readiness?.missingRequiredEvidenceCount ?? 0)),
      missing: readiness?.missingRequiredEvidenceCount ?? 0,
    },
    {
      label: "필수 증언",
      discovered: readiness?.discoveredRequiredStatementCount ?? 0,
      required: readiness?.requiredStatementCount ?? ((readiness?.discoveredRequiredStatementCount ?? 0) + (readiness?.missingRequiredStatementCount ?? 0)),
      missing: readiness?.missingRequiredStatementCount ?? 0,
    },
  ];
  const visibleRows = rows.filter((row) => row.required > 0 || row.discovered > 0 || row.missing > 0);
  const missing = visibleRows.filter((row) => row.missing > 0);
  return (
    <section className={`readiness-dossier ${readiness?.eligible ? "eligible" : "ineligible"}`} aria-label="최종 고발 준비 상태">
      <header>
        <strong>{readiness?.eligible ? "필수 단서 충족" : "필수 단서 미충족"}</strong>
        <span>{readiness ? "판정 준비도" : "준비도 확인 중"}</span>
      </header>
      <div className="readiness-grid">
        {visibleRows.map((row) => (
          <div key={row.label}>
            <span>{row.label}</span>
            <b>{row.discovered}/{row.required}</b>
            <small>{row.missing > 0 ? `부족 ${row.missing}` : "충족"}</small>
          </div>
        ))}
      </div>
      <p>{missing.length > 0 ? `누락: ${missing.map((row) => `${row.label} ${row.missing}`).join(" · ")}` : "최종 판단에 필요한 필수 단서 상태가 충족되었습니다."}</p>
    </section>
  );
}

function ProofSummary({
  selectedEvidence,
  notebookEvidenceIds,
  selectedStatements,
  notebookStatementIds,
  contradictionIds,
}: {
  selectedEvidence: GameSessionView["evidence"];
  notebookEvidenceIds: string[];
  selectedStatements: GameSessionView["statements"];
  notebookStatementIds: string[];
  contradictionIds: string[];
}) {
  const hasProof = selectedEvidence.length > 0 || notebookEvidenceIds.length > 0 || selectedStatements.length > 0 || notebookStatementIds.length > 0 || contradictionIds.length > 0;
  return (
    <section className="proof-summary" aria-label="제출 근거 요약">
      <header><h4>제출 근거 요약</h4><span>{hasProof ? "공개 근거만 표시" : "근거 없음"}</span></header>
      {hasProof ? (
        <dl>
          <div><dt>선택 증거</dt><dd>{selectedEvidence.map((item) => item.title).join(", ") || "없음"}</dd></div>
          <div><dt>수첩 증거</dt><dd>{notebookEvidenceIds.join(", ") || "없음"}</dd></div>
          <div><dt>선택 증언</dt><dd>{selectedStatements.map((item) => `${item.speaker}: ${item.text}`).join(" / ") || "없음"}</dd></div>
          <div><dt>수첩 증언</dt><dd>{notebookStatementIds.join(", ") || "없음"}</dd></div>
          <div><dt>발견 모순</dt><dd>{contradictionIds.join(", ") || "없음"}</dd></div>
        </dl>
      ) : (
        <p className="empty-copy">선택된 증거, 수첩 링크, 발견된 모순이 없습니다. 최종 판정에는 지금까지 확보한 공개 단서가 반영됩니다.</p>
      )}
    </section>
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
              <img src={suspectAsset(suspect.id, suspect.expression)} alt="" />
              <strong>{suspect.name}</strong>
              <span>{edge?.unlocked ? edge.label || edge.conflict : "관계 단서 잠김"}</span>
            </article>
          );
        })}
      </div>
      <div className="drawer-section-heading"><h3>공개 관계 단서</h3><span>{edges.filter((edge) => edge.unlocked).length}/{edges.length || session.relations.length}</span></div>
      <div className="relation-detail-grid">
        {edges.length > 0 ? edges.map((edge) => <RelationDetail key={edge.relationshipId} edge={edge} nodes={relationMap?.nodes ?? []} session={session} />) : session.relations.map((relation) => (
          <article key={relation.id} className={`relation-detail ${relation.unlocked ? "unlocked" : "locked"}`}>
            <b>{relation.suspectName}</b>
            <span>{relation.unlocked ? relation.conflict : "잠긴 관계"}</span>
            <p>{relation.unlocked ? relation.description : "대화와 증거 확인을 진행하면 공개됩니다."}</p>
            <small>단서 상태: {relation.unlocked ? "확인됨" : "미확인"}</small>
          </article>
        ))}
      </div>
    </>
  );
}

function RelationDetail({ edge, nodes, session }: { edge: RelationMapEdge; nodes: RelationMapNode[]; session: GameSessionView }) {
  const source = nodes.find((node) => node.characterId === edge.sourceCharacterId)?.name ?? edge.sourceCharacterId;
  const target = nodes.find((node) => node.characterId === edge.targetCharacterId)?.name ?? edge.targetCharacterId;
  return (
    <article className={`relation-detail ${edge.unlocked ? "unlocked" : "locked"}`}>
      <b>{source} ↔ {target}</b>
      <span>{edge.unlocked ? edge.label || edge.conflict : "잠긴 관계"}</span>
      <p>{edge.unlocked ? edge.description : "대화와 증거 확인을 진행하면 공개됩니다."}</p>
      <small>관련 단서: {formatRelationClueLabels(edge, session)}</small>
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
  if (!sanitized) return "공개 참조 없음";
  return Object.entries(sanitized).map(([key, values]) => `${key}:${values.join("|")}`).join(" · ") || "공개 참조 없음";
}

function formatStatementLabels(statementIds: string[], statementsById: Map<string, Statement>) {
  const labels = sanitizePublicIds(statementIds).map((statementId) => {
    const statement = statementsById.get(statementId);
    if (!statement) return statementId;
    return `${statement.speaker}: ${statement.text}`;
  });
  return labels.join(" · ") || "미연결";
}

function formatRelationClueLabels(edge: RelationMapEdge, session: GameSessionView) {
  const evidenceById = new Map(session.evidence.map((item) => [item.id, item]));
  const statementsById = new Map(session.statements.map((item) => [item.id, item]));
  const recordsById = new Map(session.records.map((item) => [item.id, item]));

  const labels = [
    ...sanitizePublicIds(edge.evidenceRefs).map((id) => evidenceById.get(id)?.title ?? id),
    ...sanitizePublicIds(edge.statementRefs).map((id) => {
      const statement = statementsById.get(id);
      return statement ? `${statement.speaker}: ${statement.text}` : id;
    }),
    ...sanitizePublicIds(edge.recordRefs).map((id) => recordsById.get(id)?.title ?? id),
  ];

  return labels.join(" · ") || "아직 없음";
}
