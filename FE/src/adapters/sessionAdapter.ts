import type {
  CaseRecord,
  CharacterReactionDiagnostic,
  CaseSummary,
  CluePath,
  CurrentObjective,
  DialogueLogItem,
  DialogueRuntimeDiagnostics,
  Evidence,
  GameEventFeedItem,
  HelperSuggestion,
  GameSessionView,
  NoteEntry,
  Opening,
  Phase,
  Question,
  RelationMap,
  Relationship,
  Statement,
  StoryAct,
  Storyline,
  Suspect,
  SuspectStatus,
  TimelineEvent,
  Verdict,
  VisualState,
  PublicContradictionReadModel,
} from "../types";
import { defaultBackgroundIdForCase, normalizeExpression } from "../constants/presentation";
import { sanitizePublicDiagnosticValue, sanitizePublicIds, sanitizeSourceRefs } from "../utils/publicDiagnostics";

const emptyOpening: Opening = {
  hook: "사건 파일 확인 중",
  objective: "서버 공개 사건 파일을 불러와야 합니다.",
  rules: [],
  victoryCondition: "공개 사건 정보 확인 중",
};

const emptyStoryline: Storyline = {
  publicPremise: "사건 흐름 확인 중",
  acts: [],
  timeline: [],
  cluePaths: [],
};

export type BackendCase = {
  caseId: string;
  sceneId?: string;
  title: string;
  summary: string;
  victimName: string;
  incidentTime: string;
  incidentLocation: string;
  questionLimit: number;
};

export type BackendSession = {
  sessionId: string;
  caseId: string;
  phase?: "investigation" | "accusation" | "solved" | "failed" | Phase;
  remainingQuestions: number;
  questionLimit?: number;
  visibleEvidenceCount?: number;
  totalEvidenceCount?: number;
  selectedSuspectId?: string | null;
  suspects?: Array<{
    characterId: string;
    name: string;
    role: string;
    publicProfile: string;
    motiveCandidate?: boolean;
    pressure?: number;
    pressureState?: string;
    pressureStage?: string;
    tensionLevel?: string;
    emotionalState?: string;
    emotion?: string;
    expression?: string;
  }>;
  dialogueLog?: Array<{
    id: string;
    speaker: string;
    text: string;
    suspectId?: string;
    questionId?: string;
    createdAt?: string;
  }>;
  evidence?: Array<{
    evidenceId: string;
    name: string;
    type: string;
    description: string;
    foundAt: string;
    timeWindow?: string | null;
    reliability: number;
    sourceRefs?: Record<string, string[]>;
    relatedStatementIds?: string[];
    relatedContradictionIds?: string[];
    timelineIds?: string[];
  }>;
  notes?: Array<{
    id: string;
    text: string;
    tags?: string[];
    linkedContradictionIds?: string[];
    linkedStatementIds?: string[];
    linkedEvidenceIds?: string[];
    linkedRecordIds?: string[];
    createdAt?: string;
    updatedAt?: string;
  }>;
  records?: Array<{
    recordId: string;
    name: string;
    description: string;
    timeWindow?: string | null;
  }>;
  relations?: Array<{
    relationshipId: string;
    characterId: string;
    description: string;
    conflict: string;
  }>;
  relationMap?: RelationMap;
  statements?: Array<{
    statementId: string;
    characterId: string;
    text: string;
    timeWindow?: string | null;
    location?: string | null;
  }>;
  questions?: Array<{
    questionId: string;
    characterId: string;
    text: string;
    answer: string;
    unlocksEvidenceIds?: string[];
    unlocksStatementIds?: string[];
  }>;
  unlockedQuestionIds?: string[];
  newlyUnlockedIds?: string[];
  discoveredContradictionIds?: string[];
  foundContradictionIds?: string[];
  accusationReadiness?: GameSessionView["accusationReadiness"];
  pressureBySuspect?: Record<string, number>;
  emotionBySuspect?: Record<string, string>;
  expressionBySuspect?: Record<string, string>;
  visualState?: VisualState;
  dialogueResult?: {
    dialogueMode?: string;
    intent?: string;
    matchedQuestionId?: string | null;
    matchedEvidenceIds?: string[];
    matchedStatementIds?: string[];
    matchedRecordIds?: string[];
    matchedRefs?: string[];
    sourceRefs?: string[];
    fallbackUsed?: boolean;
    degraded?: boolean;
    provider?: string;
    model?: string;
    blockedReason?: string | null;
    safety?: string | { status?: string; decision?: string; blocked?: boolean; repaired?: boolean };
    proposedEvents?: unknown[];
    appliedEvents?: unknown[];
    proposedEventsCount?: number;
    appliedEventsCount?: number;
    previousRemainingQuestions?: number;
    remainingQuestions?: number;
    remainingQuestionsDelta?: number;
    emotionalState?: string;
    tensionLevel?: string;
    lastEventId?: string;
    characterReaction?: CharacterReactionDiagnostic;
    characterReactionRoute?: string;
    helperSuggestion?: HelperSuggestion;
  };
  helperSuggestion?: HelperSuggestion;
  pressureGates?: GameSessionView["pressureGates"];
  disclosureLadders?: GameSessionView["disclosureLadders"];
  lastEventId?: string;
  opening?: Opening;
  storyline?: Partial<Storyline> & {
    acts?: StoryAct[];
    timeline?: TimelineEvent[];
    cluePaths?: CluePath[];
  };
  currentObjective?: string | Partial<CurrentObjective>;
  currentActId?: string;
  visibleTimeline?: TimelineEvent[];
  contradictionResult?: {
    verdict: Verdict;
    contradictionId?: string | null;
    message: string;
  };
  accusationResult?: {
    verdict: Verdict;
    message: string;
    missingEvidenceIds?: string[];
    missingContradictionIds?: string[];
    missingStatementIds?: string[];
  };
  accusation?: {
    verdict?: Verdict;
    correct?: boolean;
    message?: string;
    missingEvidenceIds?: string[];
    missingContradictionIds?: string[];
    missingStatementIds?: string[];
  };
  contradictions?: PublicContradictionReadModel;
};

function eventFeedItem(value: unknown): GameEventFeedItem | null {
  if (!value || typeof value !== "object") return null;
  const event = value as { id?: string; type?: string; eventType?: string; createdAt?: string; payload?: Record<string, unknown> };
  const type = sanitizePublicDiagnosticValue(event.type ?? event.eventType) ?? "EVENT";
  const payload = event.payload && typeof event.payload === "object" ? event.payload : {};
  const text = typeof payload.text === "string" ? payload.text : undefined;
  const contradictionId = typeof payload.contradictionId === "string" ? payload.contradictionId : undefined;
  const evidenceId = typeof payload.evidenceId === "string" ? payload.evidenceId : undefined;
  const sourceId = typeof payload.sourceId === "string" ? payload.sourceId : undefined;
  const titleByType: Record<string, string> = {
    NOTE_FACT_ADDED: "단서 기록",
    NOTE_CONTRADICTION_CANDIDATE_ADDED: "모순 후보",
    EVIDENCE_UNLOCKED: "증거 해금",
    TIMELINE_EVENT_REVEALED: "타임라인 갱신",
    VISUAL_STATE_CHANGED: "심문 반응",
    BOOKMARK_SUGGESTED: "북마크 제안",
  };
  return {
    id: sanitizePublicDiagnosticValue(event.id) ?? `${type}_${Date.now()}`,
    type,
    title: titleByType[type] ?? type,
    message: sanitizePublicDiagnosticValue(text ?? contradictionId ?? evidenceId ?? sourceId ?? type) ?? type,
    createdAt: event.createdAt,
    payload,
  };
}

export function normalizeCase(item: BackendCase | CaseSummary): CaseSummary {
  if ("caseId" in item) {
    return {
      id: item.caseId,
      sceneId: item.sceneId,
      title: item.title,
      summary: item.summary,
      victim: item.victimName,
      incidentTime: item.incidentTime,
      location: item.incidentLocation,
      questionLimit: item.questionLimit,
    };
  }
  return item;
}

function normalizePhase(phase: BackendSession["phase"]): Phase {
  if (phase === "solved" || phase === "failed") return "result";
  if (phase === "accusation") return "accusation";
  return "investigation";
}

function formatSafety(value?: string | { status?: string; decision?: string; blocked?: boolean; repaired?: boolean }): string | undefined {
  if (!value) return undefined;
  if (typeof value === "string") return sanitizePublicDiagnosticValue(value);
  const flags = [value.status, value.decision, value.blocked ? "blocked" : undefined, value.repaired ? "repaired" : undefined].filter(Boolean);
  return sanitizePublicDiagnosticValue(flags.join("/"));
}

function countEvents(value?: unknown[], explicit?: number): number | undefined {
  if (typeof explicit === "number") return explicit;
  return value?.length;
}

const reactionLabels: Record<string, string> = {
  answer_relevant: "관련 질문",
  deflect_irrelevant: "관련 없는 발화",
  reject_false_premise: "근거 없는 단정",
  challenge_player_contradiction: "플레이어 발화 모순",
  react_to_valid_pressure: "유효한 압박",
  ask_clarification: "모호한 질문",
  refuse_meta_or_private: "메타/비공개 요청",
};

const reactionEffects: Record<string, string> = {
  answer_relevant: "공개 사실 답변",
  deflect_irrelevant: "캐릭터식 회피",
  reject_false_premise: "전제 반박",
  challenge_player_contradiction: "공개 정보 기준 지적",
  react_to_valid_pressure: "긴장 반응",
  ask_clarification: "구체화 요청",
  refuse_meta_or_private: "세계관 안에서 거절",
};

function normalizeCharacterReaction(value?: CharacterReactionDiagnostic): CharacterReactionDiagnostic | undefined {
  if (!value || typeof value !== "object") return undefined;
  const route = sanitizePublicDiagnosticValue(value.reactionRoute ?? value.route);
  if (!route) return undefined;
  return {
    owner: sanitizePublicDiagnosticValue(value.owner),
    suspectId: sanitizePublicDiagnosticValue(value.suspectId),
    route,
    reactionRoute: route,
    label: sanitizePublicDiagnosticValue(value.label) ?? reactionLabels[route],
    effect: sanitizePublicDiagnosticValue(value.effect) ?? reactionEffects[route],
    confidence: typeof value.confidence === "number" ? value.confidence : undefined,
    playerClaimAssessment: sanitizePublicDiagnosticValue(value.playerClaimAssessment),
    characterStance: sanitizePublicDiagnosticValue(value.characterStance),
    responseIntent: sanitizePublicDiagnosticValue(value.responseIntent),
    playerFacingReason: sanitizePublicDiagnosticValue(value.playerFacingReason),
    publicOnly: value.publicOnly !== false,
    appliedStateChange: value.appliedStateChange === true,
  };
}

function normalizeHelperSuggestion(value?: HelperSuggestion): HelperSuggestion | undefined {
  if (!value || typeof value !== "object") return undefined;
  const helperRoute = sanitizePublicDiagnosticValue(value.helperRoute) ?? "silent";
  return {
    helperRoute,
    confidence: typeof value.confidence === "number" ? value.confidence : 0,
    tone: sanitizePublicDiagnosticValue(value.tone) ?? "noir_assistant",
    message: sanitizePublicDiagnosticValue(value.message) ?? "",
    suggestedActions: Array.isArray(value.suggestedActions)
      ? value.suggestedActions.map((action) => ({
          type: sanitizePublicDiagnosticValue(action.type) ?? "open_evidence",
          targetId: sanitizePublicDiagnosticValue(action.targetId) ?? "",
          label: sanitizePublicDiagnosticValue(action.label) ?? "확인",
        })).filter((action) => action.targetId || action.label)
      : [],
    publicRefs: {
      evidenceIds: sanitizePublicIds(value.publicRefs?.evidenceIds),
      statementIds: sanitizePublicIds(value.publicRefs?.statementIds),
      relationIds: sanitizePublicIds(value.publicRefs?.relationIds),
      suspectIds: sanitizePublicIds(value.publicRefs?.suspectIds),
    },
  };
}

function cleanDialogueText(text: string, speaker: string): string {
  if (speaker === "player") return text;
  let cleaned = text.trim();
  const pairs: Array<[string, string]> = [["\"", "\""], ["'", "'"], ["“", "”"], ["‘", "’"], ["「", "」"], ["『", "』"]];
  let changed = true;
  while (changed && cleaned.length >= 2) {
    changed = false;
    for (const [left, right] of pairs) {
      if (cleaned.startsWith(left) && cleaned.endsWith(right)) {
        cleaned = cleaned.slice(left.length, -right.length).trim();
        changed = true;
        break;
      }
    }
  }
  return cleaned
    .replaceAll("것이오", "겁니다")
    .replaceAll("하오", "해요")
    .replaceAll("하소", "하세요")
    .replaceAll("했소", "했습니다")
    .replaceAll("계셨지", "계셨습니다")
    .replaceAll("그대", "형사님");
}

function runtimeDiagnostics(session: BackendSession, source: "api"): DialogueRuntimeDiagnostics {
  const result = session.dialogueResult;
  const characterReaction = normalizeCharacterReaction(result?.characterReaction);
  const helperSuggestion = normalizeHelperSuggestion(result?.helperSuggestion ?? session.helperSuggestion);
  return {
    source,
    dialogueMode: sanitizePublicDiagnosticValue(result?.dialogueMode),
    intent: sanitizePublicDiagnosticValue(result?.intent ?? result?.dialogueMode),
    matchedQuestionId: sanitizePublicDiagnosticValue(result?.matchedQuestionId) ?? null,
    matchedEvidenceIds: sanitizePublicIds(result?.matchedEvidenceIds),
    matchedStatementIds: sanitizePublicIds(result?.matchedStatementIds),
    matchedRecordIds: sanitizePublicIds(result?.matchedRecordIds),
    matchedRefs: sanitizePublicIds([...(result?.matchedRefs ?? []), ...(result?.sourceRefs ?? [])]),
    provider: sanitizePublicDiagnosticValue(result?.provider),
    model: sanitizePublicDiagnosticValue(result?.model),
    fallbackUsed: result?.fallbackUsed,
    degraded: result?.degraded,
    blockedReason: sanitizePublicDiagnosticValue(result?.blockedReason),
    safety: formatSafety(result?.safety),
    lastEventId: sanitizePublicDiagnosticValue(result?.lastEventId ?? session.lastEventId),
    proposedEventsCount: countEvents(result?.proposedEvents, result?.proposedEventsCount),
    appliedEventsCount: countEvents(result?.appliedEvents, result?.appliedEventsCount),
    previousRemainingQuestions: result?.previousRemainingQuestions,
    remainingQuestions: result?.remainingQuestions ?? session.remainingQuestions,
    remainingQuestionsDelta: result?.remainingQuestionsDelta,
    emotionalState: sanitizePublicDiagnosticValue(result?.emotionalState),
    tensionLevel: sanitizePublicDiagnosticValue(result?.tensionLevel),
    characterReaction,
    characterReactionRoute: sanitizePublicDiagnosticValue(result?.characterReactionRoute ?? characterReaction?.reactionRoute ?? characterReaction?.route),
    helperSuggestion,
  };
}

function normalizeRelationMap(value?: RelationMap): RelationMap | undefined {
  if (!value) return undefined;
  return {
    centerCharacterId: sanitizePublicDiagnosticValue(value.centerCharacterId) ?? value.centerCharacterId,
    nodes: value.nodes.map((node) => ({
      ...node,
      characterId: sanitizePublicDiagnosticValue(node.characterId) ?? node.characterId,
    })),
    edges: value.edges.map((edge) => ({
      ...edge,
      relationshipId: sanitizePublicDiagnosticValue(edge.relationshipId) ?? edge.relationshipId,
      sourceCharacterId: sanitizePublicDiagnosticValue(edge.sourceCharacterId) ?? edge.sourceCharacterId,
      targetCharacterId: sanitizePublicDiagnosticValue(edge.targetCharacterId) ?? edge.targetCharacterId,
      evidenceRefs: sanitizePublicIds(edge.evidenceRefs),
      statementRefs: sanitizePublicIds(edge.statementRefs),
      recordRefs: sanitizePublicIds(edge.recordRefs),
    })),
  };
}

function statusFromPressure(pressure: number): SuspectStatus {
  if (pressure >= 70) return "broken";
  if (pressure > 0) return "pressed";
  return "normal";
}

function statusFromPublicState(pressure: number, pressureState?: string, tensionLevel?: string): SuspectStatus {
  const state = `${pressureState ?? ""} ${tensionLevel ?? ""}`.toLowerCase();
  if (state.includes("break") || state.includes("critical")) return "broken";
  if (state.includes("high") || state.includes("press") || state.includes("medium") || pressure > 0) return "pressed";
  return statusFromPressure(pressure);
}

function deriveExpression(pressure: number, tensionLevel?: string, emotionalState?: string, explicitExpression?: string): string {
  if (explicitExpression) return normalizeExpression(explicitExpression);
  const state = `${emotionalState ?? ""} ${tensionLevel ?? ""}`.toLowerCase();
  if (state.includes("break")) return "breakdown";
  if (state.includes("shock")) return "shocked";
  if (state.includes("angry") || state.includes("rage")) return "angry";
  if (state.includes("anx") || state.includes("critical")) return "anxious";
  if (state.includes("defensive") || state.includes("high")) return "defensive";
  if (state.includes("confident") || state.includes("lying")) return "confident_lying";
  if (state.includes("sad")) return "sad";
  if (state.includes("focus")) return "focused";
  if (state.includes("wary") || state.includes("guard") || state.includes("medium")) return "wary";
  if (pressure >= 85) return "breakdown";
  if (pressure >= 70) return "anxious";
  if (pressure >= 45) return "defensive";
  if (pressure >= 15) return "wary";
  return "neutral";
}

function tensionFromPressure(pressure: number, explicit?: string): VisualState["tensionLevel"] {
  if (explicit) return explicit;
  if (pressure >= 80) return "critical";
  if (pressure >= 55) return "high";
  if (pressure >= 20) return "medium";
  return "low";
}

function normalizeCurrentObjective(value: BackendSession["currentObjective"], actId: string, storyline: Storyline): CurrentObjective {
  const act = storyline.acts.find((item) => item.actId === actId) ?? storyline.acts[0];
  if (typeof value === "string") {
    return {
      actId: act?.actId ?? actId,
      title: act?.title ?? "현재 목표",
      objective: value,
      playerHint: act?.playerHint ?? "공개 목표 확인 중",
    };
  }
  if (value?.objective) {
    return {
      actId: value.actId ?? act?.actId ?? actId,
      title: value.title ?? act?.title ?? "현재 목표",
      objective: value.objective,
      playerHint: value.playerHint ?? act?.playerHint ?? "공개 목표 확인 중",
    };
  }
  return {
    actId: act?.actId ?? actId,
    title: act?.title ?? "목표 확인 중",
    objective: act?.objective ?? "현재 목표 확인 중",
    playerHint: act?.playerHint ?? "공개 사건 정보를 확인하세요.",
  };
}

function normalizeStoryline(value: BackendSession["storyline"]): Storyline {
  return {
    publicPremise: value?.publicPremise ?? emptyStoryline.publicPremise,
    acts: value?.acts ?? [],
    timeline: value?.timeline ?? [],
    cluePaths: (value?.cluePaths ?? []).map((path) => ({
      pathId: path.pathId,
      title: path.title,
      objective: path.objective,
      steps: path.steps.map((step) => ({
        order: step.order,
        type: step.type,
        id: step.id,
        prompt: step.prompt,
      })),
      resolvesContradictionId: path.resolvesContradictionId,
      unlocks: path.unlocks,
    })),
  };
}

function visibleTimelineFallback(storyline: Storyline, evidence: Evidence[], records: CaseRecord[], statements: Statement[]): TimelineEvent[] {
  const visibleIds = new Set([
    ...evidence.filter((item) => item.unlocked).map((item) => item.id),
    ...records.filter((item) => item.unlocked).map((item) => item.id),
    ...statements.filter((item) => item.unlocked).map((item) => item.id),
  ]);
  return storyline.timeline.filter((item) => visibleIds.has(item.sourceId) || !item.unlockCondition);
}

function emptyContradictions(): PublicContradictionReadModel {
  return { discoveredIds: [], discovered: [], candidates: [] };
}

function enrichSessionView(session: GameSessionView): GameSessionView {
  const storyline = session.storyline ?? emptyStoryline;
  const currentActId = session.currentActId ?? storyline.acts[0]?.actId ?? "intro";
  return {
    ...session,
    suspects: session.suspects.map((suspect) => ({
      id: suspect.id,
      name: suspect.name,
      role: suspect.role,
      profile: suspect.profile,
      motiveHint: suspect.motiveHint,
      color: suspect.color,
      pressure: suspect.pressure,
      status: suspect.status,
      pressureState: suspect.pressureState,
      pressureStage: suspect.pressureStage,
      tensionLevel: suspect.tensionLevel,
      emotion: suspect.emotion,
      expression: suspect.expression,
    })),
    visibleEvidenceCount: session.visibleEvidenceCount ?? session.evidence.filter((item) => item.unlocked).length,
    totalEvidenceCount: session.totalEvidenceCount ?? session.evidence.length,
    opening: session.opening ?? emptyOpening,
    storyline,
    currentActId,
    currentObjective: session.currentObjective ?? normalizeCurrentObjective(undefined, currentActId, storyline),
    visibleTimeline:
      session.visibleTimeline ?? visibleTimelineFallback(storyline, session.evidence, session.records, session.statements),
    source: "api",
    contradictions: session.contradictions ?? emptyContradictions(),
  };
}

export function normalizeSession(payload: BackendSession | GameSessionView): GameSessionView {
  if ("source" in payload || ("suspects" in payload && payload.suspects?.some((item) => "id" in item))) {
    return enrichSessionView(payload as GameSessionView);
  }

  const session = payload as BackendSession;
  const pressureBySuspect = session.pressureBySuspect ?? {};
  const emotionBySuspect = session.emotionBySuspect ?? {};
  const expressionBySuspect = session.expressionBySuspect ?? {};
  const suspects: Suspect[] = (session.suspects ?? []).map((item, index) => {
    const pressure = item.pressure ?? pressureBySuspect[item.characterId] ?? 0;
    const emotionalState = item.emotionalState ?? item.emotion ?? emotionBySuspect[item.characterId] ?? "guarded";
    const tensionLevel = tensionFromPressure(pressure, item.tensionLevel);
    const expression = deriveExpression(pressure, tensionLevel, emotionalState, item.expression ?? expressionBySuspect[item.characterId]);
    return {
      id: item.characterId,
      name: item.name,
      role: item.role,
      profile: item.publicProfile,
      motiveHint: item.motiveCandidate ? "동기 후보" : "알리바이 검증 필요",
      color: ["#8f2f2a", "#566170", "#4d6672", "#78613e"][index] ?? "#6f5a3a",
      pressure,
      status: statusFromPublicState(pressure, item.pressureState, tensionLevel),
      pressureState: item.pressureState,
      pressureStage: sanitizePublicDiagnosticValue(item.pressureStage),
      tensionLevel,
      emotion: emotionalState,
      expression,
    };
  });
  const suspectName = (id: string) => suspects.find((item) => item.id === id)?.name ?? id;
  const questionSuspectById = new Map((session.questions ?? []).map((item) => [item.questionId, item.characterId]));

  const evidence: Evidence[] = [
    ...(session.evidence ?? []).map((item) => ({
      id: item.evidenceId,
      title: item.name,
      type: item.type as Evidence["type"],
      description: item.description,
      source: item.foundAt,
      time: item.timeWindow ?? "불명",
      reliability: item.reliability,
      unlocked: true,
      viewed: false,
      relatedStatementIds: item.relatedStatementIds ?? [],
      sourceRefs: sanitizeSourceRefs(item.sourceRefs),
      relatedContradictionIds: item.relatedContradictionIds,
      timelineIds: item.timelineIds,
    })),
  ];
  const notes: NoteEntry[] = (session.notes ?? []).map((item) => ({
    id: item.id,
    text: item.text,
    tags: item.tags ?? [],
    linkedContradictionIds: item.linkedContradictionIds ?? [],
    linkedStatementIds: item.linkedStatementIds ?? [],
    linkedEvidenceIds: item.linkedEvidenceIds ?? [],
    linkedRecordIds: item.linkedRecordIds ?? [],
    createdAt: item.createdAt,
    updatedAt: item.updatedAt,
  }));
  const records: CaseRecord[] = [
    ...(session.records ?? []).map((item) => ({
      id: item.recordId,
      title: item.name,
      description: item.description,
      time: item.timeWindow ?? "불명",
      unlocked: true,
    })),
  ];
  const relations: Relationship[] = [
    ...(session.relations ?? []).map((item) => ({
      id: item.relationshipId,
      suspectId: item.characterId,
      suspectName: suspectName(item.characterId),
      description: item.description,
      conflict: item.conflict,
      unlocked: true,
    })),
  ];
  const statements: Statement[] = [
    ...(session.statements ?? []).map((item) => ({
      id: item.statementId,
      suspectId: item.characterId,
      speaker: suspectName(item.characterId),
      text: item.text,
      time: item.timeWindow ?? "불명",
      place: item.location ?? "불명",
      unlocked: true,
      bookmarked: false,
    })),
  ];
  const questions: Question[] = [
    ...(session.questions ?? []).map((item) => ({
      id: item.questionId,
      suspectId: item.characterId,
      label: item.text,
      response: item.answer,
      statementId: item.unlocksStatementIds?.[0],
      unlockEvidenceIds: item.unlocksEvidenceIds,
      used: session.dialogueLog?.some((log) => log.questionId === item.questionId && log.speaker === "player") ?? false,
    })),
  ];
  const dialogueLog: DialogueLogItem[] = (session.dialogueLog ?? []).map((item) => ({
    id: item.id,
    speaker: item.speaker,
    text: cleanDialogueText(item.text, item.speaker),
    suspectId: item.suspectId ?? (item.questionId ? questionSuspectById.get(item.questionId) : undefined),
    questionId: item.questionId,
    tag: item.speaker === "player" ? "질문" : item.speaker === "rule_engine" ? "룰 판정" : "답변",
    createdAt: item.createdAt,
    important: item.speaker !== "player",
  }));
  const contradictionResult = session.contradictionResult;
  const accusationResult = session.accusationResult ?? (
    session.accusation?.verdict || typeof session.accusation?.correct === "boolean" || session.accusation?.message
      ? {
          verdict: session.accusation.verdict ?? (session.accusation.correct ? "correct" : "wrong"),
          message: session.accusation.message ?? (session.accusation.correct ? "사건이 해결되었습니다." : "잘못된 범인을 지목했습니다."),
          missingEvidenceIds: session.accusation.missingEvidenceIds,
          missingContradictionIds: session.accusation.missingContradictionIds,
          missingStatementIds: session.accusation.missingStatementIds,
        }
      : undefined
  );
  const foundContradictionIds = session.discoveredContradictionIds ?? session.foundContradictionIds ?? [];
  const storyline = normalizeStoryline(session.storyline);
  const currentActId = session.currentActId ?? storyline.acts[0]?.actId ?? "intro";
  const selectedSuspectId = session.selectedSuspectId ?? null;
  const selectedSuspect = selectedSuspectId ? suspects.find((item) => item.id === selectedSuspectId) : undefined;
  const visualState: VisualState = {
    ...(session.visualState ?? {}),
    suspectId: session.visualState?.suspectId ?? selectedSuspectId ?? undefined,
    backgroundId: session.visualState?.backgroundId ?? defaultBackgroundIdForCase(session.caseId),
    expression: session.visualState?.expression ?? selectedSuspect?.expression ?? "neutral",
    emotionalState: session.visualState?.emotionalState ?? session.dialogueResult?.emotionalState ?? selectedSuspect?.emotion,
    tensionLevel: session.visualState?.tensionLevel ?? session.dialogueResult?.tensionLevel,
  };
  const visibleTimeline = session.visibleTimeline?.length
    ? session.visibleTimeline
    : visibleTimelineFallback(storyline, evidence, records, statements);

  return {
    sessionId: session.sessionId,
    caseId: session.caseId,
    phase: accusationResult ? "result" : normalizePhase(session.phase),
    remainingQuestions: session.remainingQuestions,
    questionLimit: session.questionLimit ?? 12,
    visibleEvidenceCount: session.visibleEvidenceCount ?? evidence.filter((item) => item.unlocked).length,
    totalEvidenceCount: session.totalEvidenceCount ?? evidence.length,
    selectedSuspectId,
    suspects,
    questions,
    dialogueLog,
    evidence,
    notes,
    records,
    relations,
    relationMap: normalizeRelationMap(session.relationMap),
    statements,
    unlockedQuestionIds: session.unlockedQuestionIds ?? questions.map((item) => item.id),
    newlyUnlockedIds: session.newlyUnlockedIds ?? [],
    foundContradictionIds,
    contradictions: session.contradictions ?? emptyContradictions(),
    accusationReadiness: session.accusationReadiness,
    opening: session.opening ?? emptyOpening,
    storyline,
    currentObjective: normalizeCurrentObjective(session.currentObjective, currentActId, storyline),
    currentActId,
    visibleTimeline,
    source: "api",
    visualState,
    latestEvents: (session.dialogueResult?.appliedEvents ?? []).map(eventFeedItem).filter((item): item is GameEventFeedItem => Boolean(item)),
    runtimeDiagnostics: runtimeDiagnostics(session, "api"),
    helperSuggestion: normalizeHelperSuggestion(session.helperSuggestion ?? session.dialogueResult?.helperSuggestion),
    pressureGates: session.pressureGates,
    disclosureLadders: session.disclosureLadders,
    lastVerdict: contradictionResult
      ? {
          verdict: contradictionResult.verdict,
          message: contradictionResult.message,
          contradictionId: contradictionResult.contradictionId ?? undefined,
        }
      : undefined,
    result: accusationResult
      ? {
          verdict: accusationResult.verdict,
          outcome: accusationResult.verdict === "correct" ? "victory" : "defeat",
          title:
            accusationResult.verdict === "correct"
              ? "승리: 사건이 해결되었습니다"
              : accusationResult.verdict === "partial"
                ? "패배: 범인은 맞았지만 근거가 부족합니다"
                : accusationResult.verdict === "insufficient"
                  ? "패배: 제출 근거가 부족합니다"
                  : "패배: 결정적 모순을 놓쳤습니다",
          message: accusationResult.message,
          usedQuestions: Math.max(0, (session.dialogueLog ?? []).filter((item) => item.speaker === "player").length),
          foundContradictions: foundContradictionIds,
          missedClues: [
            ...(accusationResult.missingEvidenceIds ?? []),
            ...(accusationResult.missingContradictionIds ?? []),
            ...(accusationResult.missingStatementIds ?? []),
          ],
        }
      : undefined,
  };
}
