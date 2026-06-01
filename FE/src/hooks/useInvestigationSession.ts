import { useEffect, useMemo, useState } from "react";
import { askQuestion, createNote, createSession, debugSetPressure, debugUnlock, deleteNote, getCases, getSession, submitAccusation, submitContradiction, updateNote } from "../api";
import { QUESTION_LIMIT } from "../constants/presentation";
import { clearStoredSession, loadStoredSession, loadStoredSessionId, saveStoredSession } from "../storage";
import type { CaseSummary, GameEventFeedItem, GameSessionView } from "../types";
import {
  buildContradictionCandidates,
  buildEvidenceTiles,
  latestSuspectAnswer,
  nextQuestionHint,
} from "../viewModels/investigationDesk";
import { createActionTimer, logEvent } from "../utils/observability";
import { useSessionEvents } from "./useSessionEvents";

export function useInvestigationSession() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [session, setSession] = useState<GameSessionView | null>(() => {
    const stored = loadStoredSession();
    return stored?.source === "local" && "opening" in stored && "storyline" in stored ? stored : null;
  });
  const [draftQuestion, setDraftQuestion] = useState("");
  const [selectedStatementIds, setSelectedStatementIds] = useState<string[]>([]);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [autoStarted, setAutoStarted] = useState(false);
  const [statusMessage, setStatusMessage] = useState("사건 파일을 불러오는 중입니다.");
  const [eventFeed, setEventFeed] = useState<GameEventFeedItem[]>([]);
  const [activeDrawer, setActiveDrawer] = useState<"case" | "evidence" | "notes" | "contradiction" | "relations" | "accusation" | "settings" | null>(null);
  const [inspectedEvidenceId, setInspectedEvidenceId] = useState<string | null>(null);
  const [draftNote, setDraftNote] = useState("");
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingNoteText, setEditingNoteText] = useState("");
  const [accusationSuspectId, setAccusationSuspectId] = useState("");
  const [accusationMotive, setAccusationMotive] = useState("");
  const [accusationMethod, setAccusationMethod] = useState("");

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
    const done = createActionTimer({ component: "InvestigationSession", action: "load_cases" });
    getCases()
      .then((items) => {
        setCases(items);
        setStatusMessage("사건 파일 준비 완료");
        done({ level: "info" });
      })
      .catch((error: unknown) => {
        setCases([]);
        setStatusMessage("사건 목록 API 실패: BE 공개 사건 파일 없이는 자동 세션을 시작하지 않습니다.");
        done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
      });
  }, []);

  useEffect(() => {
    const storedSessionId = loadStoredSessionId();
    if (!storedSessionId || storedSessionId.startsWith("mock_")) return;

    const done = createActionTimer({ component: "InvestigationSession", action: "resume_session", sessionId: storedSessionId });
    getSession(storedSessionId, null)
      .then((restored) => {
        setSession(restored);
        setStatusMessage("서버 세션을 복구했습니다.");
        done({ level: "info", caseId: restored.caseId });
      })
      .catch((error: unknown) => {
        setSession(null);
        clearStoredSession();
        setStatusMessage("서버 세션 복구 실패: 저장된 API 세션 화면을 표시하지 않고 재시도를 기다립니다.");
        done({ level: "warn", fallbackUsed: false, reason: error instanceof Error ? error.message : "unknown" });
      });
  }, []);

  useEffect(() => {
    if (session || autoStarted || cases.length === 0) return;
    setAutoStarted(true);
    const caseId = cases[0]?.id ?? "case_001";
    const done = createActionTimer({ component: "InvestigationSession", action: "start_session", caseId });
    createSession(caseId)
      .then((created) => {
        setSession(created);
        setStatusMessage("탐문 대화창을 준비했습니다. 바로 질문을 보낼 수 있습니다.");
        done({ level: "info", sessionId: created.sessionId, fallbackUsed: created.source === "local" });
      })
      .catch((error: unknown) => {
        setStatusMessage("자동 세션 생성에 실패했습니다. 새로고침 후 다시 시도해주세요.");
        done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
      });
  }, [autoStarted, cases, session]);

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
  const contradictionCandidates = useMemo(() => (session ? buildContradictionCandidates(session) : []), [session?.evidence, session?.statements, session?.selectedSuspectId]);
  const questionHint = useMemo(() => (session ? nextQuestionHint(session) : undefined), [session?.questions, session?.selectedSuspectId]);

  async function submitQuestion() {
    if (!session || busy || session.remainingQuestions <= 0) return;
    if (!session.selectedSuspectId) {
      setStatusMessage("먼저 심문할 용의자를 선택하세요. FE가 용의자를 자동 선택하지 않습니다.");
      return;
    }
    const typedQuestion = draftQuestion.trim();
    if (!typedQuestion) return;
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
      setDraftQuestion("");
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
      setStatusMessage(
        `자연어 질문 접수 · source=${diagnostic?.source ?? next.source ?? "unknown"} · intent=${diagnostic?.intent ?? diagnostic?.dialogueMode ?? "AI intent 미분류"} · matched=${matchedRefs.join(", ") || "공개 근거 미연결"} · events=${eventSummary} · fallback=${diagnostic?.fallbackUsed ? "yes" : "no"}`,
      );
      done({
        level: diagnostic?.source === "local" || diagnostic?.fallbackUsed ? "warn" : "info",
        textLength: typedQuestion.length,
        fallbackUsed: next.source === "local" || diagnostic?.fallbackUsed,
        eventType: diagnostic?.intent ?? diagnostic?.dialogueMode,
        eventId: diagnostic?.lastEventId,
      });
    } finally {
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
    setActiveDrawer("contradiction");
    if (session) logEvent({ component: "ContradictionDrawer", action: "select_statement", sessionId: session.sessionId, caseId: session.caseId, eventId: statementId });
  }

  function selectContradiction(statementId: string, evidenceId: string) {
    setSelectedStatementIds([statementId]);
    setSelectedEvidenceIds([evidenceId]);
    if (session) logEvent({ component: "ContradictionPanel", action: "select_candidate", sessionId: session.sessionId, caseId: session.caseId, eventId: evidenceId, eventType: "contradiction_candidate" });
  }

  async function submitSelectedContradiction() {
    if (!session || busy) return;
    if (!session.selectedSuspectId) {
      setStatusMessage("모순 제시는 명시적으로 선택된 용의자가 있어야 합니다.");
      setActiveDrawer("contradiction");
      return;
    }
    if (selectedStatementIds.length === 0 || selectedEvidenceIds.length === 0) {
      setStatusMessage("모순 제시는 증언 1개와 증거 1개 이상을 선택해야 합니다.");
      setActiveDrawer("contradiction");
      return;
    }
    setBusy(true);
    const done = createActionTimer({ component: "ContradictionPanel", action: "submit_contradiction", sessionId: session.sessionId, caseId: session.caseId, suspectId: session.selectedSuspectId });
    try {
      const next = await submitContradiction(session, selectedStatementIds, selectedEvidenceIds);
      setSession(next);
      appendFeedEvents(next.latestEvents ?? []);
      setStatusMessage(next.lastVerdict?.message ?? "모순 사항을 제출했습니다.");
      done({ level: "info", fallbackUsed: next.source === "local", eventType: next.lastVerdict?.verdict });
    } finally {
      setBusy(false);
    }
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
      setStatusMessage(next.result?.message ?? "최종 고발을 BE에 제출했습니다.");
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
      setStatusMessage("메모 저장 실패: BE notes endpoint를 확인해야 합니다.");
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
      setStatusMessage("메모 삭제 실패: BE notes endpoint를 확인해야 합니다.");
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
      setStatusMessage("메모 수정 실패: BE notes endpoint를 확인해야 합니다.");
      done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
    } finally {
      setBusy(false);
    }
  }

  async function adjustDebugPressure(suspectId: string, pressure: number) {
    if (!session || busy) return;
    setBusy(true);
    const done = createActionTimer({ component: "SettingsDrawer", action: "debug_set_pressure", sessionId: session.sessionId, caseId: session.caseId, suspectId });
    try {
      const next = await debugSetPressure(session, suspectId, pressure);
      setSession(next);
      setStatusMessage(`DEBUG: ${suspectId} pressure=${pressure} BE 세션에 반영`);
      done({ level: "warn", fallbackUsed: next.source === "local", eventType: "DEBUG_SESSION_UPDATED" });
    } catch (error) {
      setStatusMessage("DEBUG pressure 변경 실패: BE_DEBUG_TOOLS_ENABLED 또는 debug endpoint를 확인하세요.");
      done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
    } finally {
      setBusy(false);
    }
  }

  async function unlockDebug(target: "evidence" | "relations" | "timeline" | "notes" | "all") {
    if (!session || busy) return;
    setBusy(true);
    const done = createActionTimer({ component: "SettingsDrawer", action: "debug_unlock", sessionId: session.sessionId, caseId: session.caseId, eventType: target });
    try {
      const next = await debugUnlock(session, target);
      setSession(next);
      setStatusMessage(`DEBUG: ${target} unlock을 BE 세션에 반영`);
      done({ level: "warn", fallbackUsed: next.source === "local", eventType: "DEBUG_SESSION_UPDATED" });
    } catch (error) {
      setStatusMessage("DEBUG unlock 실패: BE_DEBUG_TOOLS_ENABLED 또는 debug endpoint를 확인하세요.");
      done({ level: "error", reason: error instanceof Error ? error.message : "unknown" });
    } finally {
      setBusy(false);
    }
  }

  function resetGame() {
    const confirmed = window.confirm("현재 세션을 종료하고 새 세션을 만들까요? 이 동작은 Settings의 명시 Reset/New Session입니다.");
    if (!confirmed) return;
    clearStoredSession();
    setSession(null);
    setAutoStarted(false);
    setStatusMessage("진행 상태를 초기화했습니다. 새 탐문 세션을 준비합니다.");
    logEvent({ component: "AppHeader", action: "reset_session", sessionId: session?.sessionId, caseId: session?.caseId });
  }

  return {
    cases,
    currentCase: cases[0],
    session,
    selectedSuspect,
    latestAnswer,
    evidenceTiles,
    contradictionCandidates,
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
    statusMessage,
    eventFeed,
    remainingQuestions: session?.remainingQuestions ?? QUESTION_LIMIT,
    setDraftQuestion,
    submitQuestion,
    selectSuspect,
    toggleEvidence,
    selectStatement,
    selectContradiction,
    submitSelectedContradiction,
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
    adjustDebugPressure,
    unlockDebug,
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
