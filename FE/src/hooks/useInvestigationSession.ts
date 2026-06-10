import { useEffect, useMemo, useRef, useState } from "react";
import { askQuestion, createNote, createSession, deleteNote, getCases, getSession, submitAccusation, updateNote } from "../api";
import { QUESTION_LIMIT } from "../constants/presentation";
import { clearStoredSession, loadStoredSessionId, saveStoredSession } from "../storage";
import type { CaseSummary, GameEventFeedItem, GameSessionView } from "../types";
import { buildEvidenceTiles, latestSuspectAnswer, nextQuestionHint } from "../viewModels/investigationDesk";
import { createActionTimer, logEvent } from "../utils/observability";
import { useSessionEvents } from "./useSessionEvents";

type InvestigationSessionOptions = {
  sessionId?: string;
  onSessionCreated?: (sessionId: string) => void;
  onSessionCleared?: () => void;
};

export function useInvestigationSession(options: InvestigationSessionOptions = {}) {
  const requestedSessionIdRef = useRef<string | null>(null);
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [session, setSession] = useState<GameSessionView | null>(null);
  const [draftQuestion, setDraftQuestion] = useState("");
  const [selectedStatementIds, setSelectedStatementIds] = useState<string[]>([]);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [pendingUserMessage, setPendingUserMessage] = useState<{ text: string; suspectId: string } | null>(null);
  const [statusMessage, setStatusMessage] = useState("사건 파일을 불러오는 중입니다.");
  const [eventFeed, setEventFeed] = useState<GameEventFeedItem[]>([]);
  const [activeDrawer, setActiveDrawer] = useState<"evidence" | "notes" | "relations" | "accusation" | null>(null);
  const [inspectedEvidenceId, setInspectedEvidenceId] = useState<string | null>(null);
  const [draftNote, setDraftNote] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingNoteText, setEditingNoteText] = useState("");
  const [accusationSuspectId, setAccusationSuspectId] = useState("");
  const [accusationMotive, setAccusationMotive] = useState("");
  const [accusationMethod, setAccusationMethod] = useState("");
  const [resumableSessionId, setResumableSessionId] = useState<string | null>(() => {
    const storedSessionId = loadStoredSessionId();
    return storedSessionId;
  });

  function appendFeedEvents(items: GameEventFeedItem[]) {
    if (items.length === 0) return;
    setEventFeed((current) => {
      const byId = new Map(current.map((item) => [item.id, item]));
      items.forEach((item) => byId.set(item.id, item));
      return Array.from(byId.values()).slice(-5);
    });
  }

  useEffect(() => {
    if (eventFeed.length === 0) return;
    const timeout = window.setTimeout(() => {
      setEventFeed((current) => current.slice(1));
    }, 5200);
    return () => window.clearTimeout(timeout);
  }, [eventFeed]);

  useSessionEvents(session, setSession, (event) => appendFeedEvents([event]));

  useEffect(() => {
    if (!options.sessionId || session?.sessionId === options.sessionId || requestedSessionIdRef.current === options.sessionId) return;
    requestedSessionIdRef.current = options.sessionId;
    setBusy(true);
    setStatusMessage("이전 수사 기록을 불러오는 중입니다.");
    const done = createActionTimer({ component: "SessionDeskPage", action: "load_session", sessionId: options.sessionId });
    getSession(options.sessionId, null)
      .then((restored) => {
        setSession(restored);
        setResumableSessionId(restored.sessionId);
        setSelectedEvidenceIds([]);
        setSelectedStatementIds([]);
        setInspectedEvidenceId(null);
        setActiveDrawer(null);
        setEventFeed([]);
        setDraftQuestion("");
        setStatusMessage("이전 수사 기록을 불러왔습니다.");
        done({ level: "info", caseId: restored.caseId });
      })
      .catch((error: unknown) => {
        setSession(null);
        setResumableSessionId(null);
        clearStoredSession();
        setStatusMessage("이전 수사 기록을 불러오지 못했습니다. 사건 목록에서 새 수사를 시작하세요.");
        done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
      })
      .finally(() => setBusy(false));
  }, [options.sessionId, session?.sessionId]);

  useEffect(() => {
    const done = createActionTimer({ component: "InvestigationSession", action: "load_cases" });
    getCases()
      .then((items) => {
        setCases(items);
        setStatusMessage("사건 파일 준비 완료");
        done({ level: "info" });
      })
      .catch((error: unknown) => {
        setCases([]);
        setStatusMessage("사건 목록을 불러오지 못했습니다. 공개 사건 파일이 준비되어야 시작할 수 있습니다.");
        done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
      });
  }, []);

  useEffect(() => {
    if (session) saveStoredSession(session);
  }, [session]);

  useEffect(() => {
    if (!session) return;
    setDraftQuestion("");
  }, [session?.selectedSuspectId]);

  const selectedSuspect = session?.suspects.find((suspect) => suspect.id === session.selectedSuspectId);
  const latestAnswer = useMemo(
    () => (session ? latestSuspectAnswer(session, session.selectedSuspectId) : ""),
    [session?.dialogueLog, session?.selectedSuspectId],
  );
  const evidenceTiles = useMemo(() => (session ? buildEvidenceTiles(session) : []), [session?.evidence]);
  const questionHint = useMemo(() => (session ? nextQuestionHint(session) : undefined), [session?.questions, session?.selectedSuspectId]);

  async function startCase(caseId: string) {
    if (busy) return;
    const caseFile = cases.find((item) => item.id === caseId);
    setBusy(true);
    setStatusMessage(`${caseFile?.title ?? caseId} 수사를 준비하는 중입니다.`);
    clearStoredSession();
    const done = createActionTimer({ component: "ScenarioSelect", action: "start_session", caseId });
    try {
      const created = await createSession(caseId);
      setSession(created);
      setResumableSessionId(created.sessionId);
      options.onSessionCreated?.(created.sessionId);
      setSelectedEvidenceIds([]);
      setSelectedStatementIds([]);
      setInspectedEvidenceId(null);
      setActiveDrawer(null);
      setEventFeed([]);
      setDraftQuestion("");
      setDraftNote("");
      setEditingNoteId(null);
      setEditingNoteText("");
      setAccusationSuspectId("");
      setAccusationMotive("");
      setAccusationMethod("");
      setStatusMessage("탐문 대화창을 준비했습니다. 바로 질문을 보낼 수 있습니다.");
      done({ level: "info", sessionId: created.sessionId, fallbackUsed: false });
    } catch (error) {
      setStatusMessage("수사를 시작하지 못했습니다. 사건 파일 상태를 확인해 주세요.");
      done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
    } finally {
      setBusy(false);
    }
  }

  async function resumeStoredSession() {
    if (busy || !resumableSessionId) return;
    setBusy(true);
    setStatusMessage("이전 수사 기록을 불러오는 중입니다.");
    const done = createActionTimer({ component: "ScenarioSelect", action: "resume_session", sessionId: resumableSessionId });
    try {
      const restored = await getSession(resumableSessionId, null);
      setSession(restored);
      setStatusMessage("이전 수사 기록을 불러왔습니다.");
      done({ level: "info", caseId: restored.caseId });
    } catch (error) {
      setSession(null);
      setResumableSessionId(null);
      clearStoredSession();
      setStatusMessage("이전 수사 기록을 불러오지 못했습니다. 사건 파일을 선택해 새 수사를 시작하세요.");
      done({ level: "warn", fallbackUsed: false, reason: error instanceof Error ? error.message : "unknown" });
    } finally {
      setBusy(false);
    }
  }

  async function submitQuestion() {
    if (!session || busy || session.remainingQuestions <= 0) return;
    if (!session.selectedSuspectId) {
      setStatusMessage("먼저 심문할 용의자를 선택하세요. FE가 용의자를 자동 선택하지 않습니다.");
      return;
    }
    const typedQuestion = draftQuestion.trim();
    if (!typedQuestion) return;
    setPendingUserMessage({ text: typedQuestion, suspectId: session.selectedSuspectId });
    setDraftQuestion("");
    setBusy(true);
    const done = createActionTimer({
      component: "InterrogationStage",
      action: "submit_dialogue",
      sessionId: session.sessionId,
      caseId: session.caseId,
      suspectId: session.selectedSuspectId,
    });
    try {
      const next = await askQuestion(session, session.selectedSuspectId, typedQuestion);
      setSession(next);
      appendFeedEvents(next.latestEvents ?? []);
      setPendingUserMessage(null);
      const diagnostic = next.runtimeDiagnostics;
      const matchedRefs = [
        diagnostic?.matchedQuestionId,
        ...(diagnostic?.matchedEvidenceIds ?? []),
        ...(diagnostic?.matchedStatementIds ?? []),
        ...(diagnostic?.matchedRecordIds ?? []),
        ...(diagnostic?.matchedRefs ?? []),
      ].filter(Boolean);
      const eventSummary =
        diagnostic?.proposedEventsCount === 0 && diagnostic?.appliedEventsCount === 0
          ? "이 턴에서 진행 이벤트 없음"
          : `${diagnostic?.proposedEventsCount ?? "?"}/${diagnostic?.appliedEventsCount ?? "?"}`;
      const routeSummary = diagnostic?.characterReaction?.label ?? diagnostic?.characterReactionRoute;
      setStatusMessage(
        diagnostic?.fallbackUsed || diagnostic?.degraded
          ? `자연어 질문은 처리됐지만 진단 확인이 필요합니다 · route=${routeSummary ?? "unknown"} · events=${eventSummary}`
          : `자연어 질문 접수 · route=${routeSummary ?? "none"} · events=${eventSummary} · matched=${matchedRefs.length}`,
      );
      done({
        level: diagnostic?.fallbackUsed || diagnostic?.degraded ? "warn" : "info",
        textLength: typedQuestion.length,
        fallbackUsed: diagnostic?.fallbackUsed,
        eventType: diagnostic?.intent ?? diagnostic?.dialogueMode,
        eventId: diagnostic?.lastEventId,
      });
    } finally {
      setPendingUserMessage(null);
      setBusy(false);
    }
  }

  function selectSuspect(suspectId: string) {
    if (!session) return;
    setSession({ ...session, selectedSuspectId: suspectId });
    logEvent({ component: "SuspectPanel", action: "select_suspect", sessionId: session.sessionId, caseId: session.caseId, suspectId });
  }

  function toggleEvidence(evidenceId: string) {
    setSelectedEvidenceIds((current) => (current.includes(evidenceId) ? current.filter((item) => item !== evidenceId) : [...current, evidenceId]));
    setInspectedEvidenceId(evidenceId);
    setActiveDrawer("evidence");
    if (session) logEvent({ component: "EvidenceGrid", action: "toggle_evidence", sessionId: session.sessionId, caseId: session.caseId, eventId: evidenceId });
  }

  function selectStatement(statementId: string) {
    setSelectedStatementIds((current) => (current.includes(statementId) ? current.filter((item) => item !== statementId) : [statementId]));
    setActiveDrawer("notes");
    if (session) logEvent({ component: "NotesDrawer", action: "select_statement", sessionId: session.sessionId, caseId: session.caseId, eventId: statementId });
  }


  async function submitFinalAccusation() {
    if (!session || busy) return;
    if (!accusationSuspectId) {
      setStatusMessage("최종 고발 대상 용의자를 선택하세요.");
      setActiveDrawer("accusation");
      return;
    }
    const motive = accusationMotive.trim();
    const method = accusationMethod.trim();
    if (!motive || !method) {
      setStatusMessage("최종 고발에는 동기와 방법 메모가 필요합니다.");
      setActiveDrawer("accusation");
      return;
    }
    setBusy(true);
    const done = createActionTimer({ component: "AccusationDrawer", action: "submit_accusation", sessionId: session.sessionId, caseId: session.caseId, suspectId: accusationSuspectId });
    const inferredProof = accusationProofFromNotebook(session, selectedStatementIds, selectedEvidenceIds);
    try {
      const next = await submitAccusation(session, {
        suspectId: accusationSuspectId,
        motive,
        method,
        evidenceIds: inferredProof.evidenceIds,
        statementIds: inferredProof.statementIds,
        contradictionIds: inferredProof.contradictionIds,
      });
      setSession(next);
      setActiveDrawer("accusation");
      setStatusMessage(next.result?.message ?? "최종 고발을 제출했습니다.");
      done({ level: next.runtimeDiagnostics?.degraded ? "warn" : "info", fallbackUsed: next.runtimeDiagnostics?.fallbackUsed, eventType: next.result?.verdict });
    } finally {
      setBusy(false);
    }
  }

  async function addNote() {
    if (!session || busy) return;
    const text = draftNote.trim();
    if (!text) return;
    setBusy(true);
    const done = createActionTimer({ component: "NotesDrawer", action: "create_note", sessionId: session.sessionId, caseId: session.caseId });
    try {
      const next = await createNote(session, text, selectedStatementIds, selectedEvidenceIds);
      setSession(next);
      setDraftNote("");
      setActiveDrawer("notes");
      setStatusMessage("메모를 서버 노트북에 저장했습니다.");
      done({ level: "info", textLength: text.length });
    } catch (error) {
      setStatusMessage("메모를 저장하지 못했습니다.");
      done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
    } finally {
      setBusy(false);
    }
  }

  async function removeNote(noteId: string) {
    if (!session || busy) return;
    setBusy(true);
    const done = createActionTimer({ component: "NotesDrawer", action: "delete_note", sessionId: session.sessionId, caseId: session.caseId, eventId: noteId });
    try {
      const next = await deleteNote(session, noteId);
      setSession(next);
      setActiveDrawer("notes");
      setStatusMessage("메모를 서버 노트북에서 삭제했습니다.");
      done({ level: "info" });
    } catch (error) {
      setStatusMessage("메모를 삭제하지 못했습니다.");
      done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
    } finally {
      setBusy(false);
    }
  }

  function startEditNote(noteId: string) {
    const note = session?.notes.find((item) => item.id === noteId);
    if (!note) return;
    setEditingNoteId(noteId);
    setEditingNoteText(note.text);
    setActiveDrawer("notes");
  }

  function cancelEditNote() {
    setEditingNoteId(null);
    setEditingNoteText("");
  }

  async function saveEditedNote() {
    if (!session || busy || !editingNoteId) return;
    const text = editingNoteText.trim();
    if (!text) return;
    const note = session.notes.find((item) => item.id === editingNoteId);
    setBusy(true);
    const done = createActionTimer({ component: "NotesDrawer", action: "update_note", sessionId: session.sessionId, caseId: session.caseId, eventId: editingNoteId });
    try {
      const next = await updateNote(
        session,
        editingNoteId,
        text,
        note?.linkedStatementIds ?? selectedStatementIds,
        note?.linkedEvidenceIds ?? selectedEvidenceIds,
        note?.linkedRecordIds ?? [],
      );
      setSession(next);
      setEditingNoteId(null);
      setEditingNoteText("");
      setActiveDrawer("notes");
      setStatusMessage("메모를 서버 노트북에서 수정했습니다.");
      done({ level: "info", textLength: text.length });
    } catch (error) {
      setStatusMessage("메모를 수정하지 못했습니다.");
      done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
    } finally {
      setBusy(false);
    }
  }


  function resetGame() {
    const confirmed = window.confirm("현재 수사를 종료하고 새 수사를 시작할까요?");
    if (!confirmed) return;
    clearStoredSession();
    setSession(null);
    setResumableSessionId(null);
    options.onSessionCleared?.();
    setStatusMessage("진행 상태를 초기화했습니다. 시작할 사건 파일을 선택하세요.");
    logEvent({ component: "AppHeader", action: "reset_session", sessionId: session?.sessionId, caseId: session?.caseId });
  }

  const currentCase = session ? cases.find((item) => item.id === session.caseId) : cases[0];

  return {
    cases,
    currentCase,
    session,
    selectedSuspect,
    latestAnswer,
    evidenceTiles,
    questionHint,
    draftQuestion,
    selectedEvidenceIds,
    selectedStatementIds,
    activeDrawer,
    inspectedEvidenceId,
    draftNote,
    editingNoteId,
    editingNoteText,
    accusationSuspectId,
    accusationMotive,
    accusationMethod,
    busy,
    pendingUserMessage,
    resumableSessionId,
    statusMessage,
    eventFeed,
    remainingQuestions: session?.remainingQuestions ?? QUESTION_LIMIT,
    startCase,
    resumeStoredSession,
    setDraftQuestion,
    submitQuestion,
    selectSuspect,
    toggleEvidence,
    selectStatement,
    setActiveDrawer,
    setDraftNote,
    setEditingNoteText,
    setInspectedEvidenceId,
    setAccusationSuspectId,
    setAccusationMotive,
    setAccusationMethod,
    addNote,
    removeNote,
    startEditNote,
    cancelEditNote,
    saveEditedNote,
    submitFinalAccusation,
    resetGame,
  };
}

function accusationProofFromNotebook(
  session: GameSessionView,
  selectedStatementIds: string[],
  selectedEvidenceIds: string[],
) {
  const contradictionNotes = session.notes.filter((note) =>
    note.tags.includes("note_contradiction_candidate_added")
    || (note.linkedStatementIds.length > 0 && note.linkedEvidenceIds.length > 0),
  );
  return {
    statementIds: dedupe([
      ...selectedStatementIds,
      ...contradictionNotes.flatMap((note) => note.linkedStatementIds),
    ]),
    evidenceIds: dedupe([
      ...selectedEvidenceIds,
      ...contradictionNotes.flatMap((note) => note.linkedEvidenceIds),
    ]),
    contradictionIds: dedupe([
      ...session.foundContradictionIds,
      ...contradictionNotes.flatMap((note) => note.linkedContradictionIds ?? []),
    ]),
  };
}

function dedupe(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}
