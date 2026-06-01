export type Phase = "start" | "investigation" | "contradiction" | "accusation" | "result";

export type Verdict = "correct" | "partial" | "insufficient" | "wrong";

export type SuspectStatus = "normal" | "pressed" | "broken";

export type CaseSummary = {
  id: string;
  sceneId?: string;
  title: string;
  summary: string;
  victim: string;
  incidentTime: string;
  location: string;
  questionLimit: number;
};

export type Suspect = {
  id: string;
  name: string;
  role: string;
  profile: string;
  motiveHint: string;
  color: string;
  pressure: number;
  status: SuspectStatus;
  emotion?: string;
  expression?: string;
};

export type VisualState = {
  suspectId?: string;
  backgroundId?: string;
  characterImageState?: string;
  emotionalState?: string;
  expression?: string;
  tensionLevel?: "low" | "medium" | "high" | "critical" | string;
};

export type DialogueRuntimeDiagnostics = {
  source: "api" | "local";
  dialogueMode?: string;
  intent?: string;
  matchedQuestionId?: string | null;
  matchedEvidenceIds?: string[];
  matchedStatementIds?: string[];
  matchedRecordIds?: string[];
  matchedRefs?: string[];
  provider?: string;
  model?: string;
  fallbackUsed?: boolean;
  degraded?: boolean;
  blockedReason?: string | null;
  safety?: string;
  lastEventId?: string;
  proposedEventsCount?: number;
  appliedEventsCount?: number;
  rejectedEventsCount?: number;
  previousRemainingQuestions?: number;
  remainingQuestions?: number;
  remainingQuestionsDelta?: number;
  emotionalState?: string;
  tensionLevel?: string;
};

export type Opening = {
  hook: string;
  objective: string;
  rules: string[];
  victoryCondition: string;
};

export type StoryAct = {
  actId: "intro" | "alibi_collection" | "first_break" | "motive_reveal" | "final_accusation" | string;
  title: string;
  objective: string;
  entryCondition: string;
  focusSuspectIds: string[];
  recommendedQuestionIds: string[];
  requiredClueIds: string[];
  playerHint: string;
  completionCondition: string;
};

export type TimelineEvent = {
  time: string;
  title: string;
  description: string;
  sourceType: "evidence" | "record" | "statement" | "inference" | string;
  sourceId: string;
  unlockCondition?: string;
};

export type CluePathStep = {
  order: number;
  type: "evidence" | "record" | "statement" | "question" | "inference" | string;
  id: string;
  prompt: string;
};

export type CluePath = {
  pathId: string;
  title: string;
  objective: string;
  steps: CluePathStep[];
  resolvesContradictionId?: string;
  unlocks: string[];
};

export type Storyline = {
  publicPremise: string;
  acts: StoryAct[];
  timeline: TimelineEvent[];
  cluePaths: CluePath[];
};

export type CurrentObjective = {
  actId: string;
  title: string;
  objective: string;
  playerHint: string;
};

export type Question = {
  id: string;
  suspectId: string;
  label: string;
  response: string;
  statementId?: string;
  used?: boolean;
  unlockEvidenceIds?: string[];
};

export type EvidenceType = "physical" | "record" | "digital" | "relationship";

export type Evidence = {
  id: string;
  title: string;
  type: EvidenceType;
  description: string;
  source: string;
  time: string;
  reliability: number;
  unlocked: boolean;
  viewed: boolean;
  relatedStatementIds: string[];
  sourceRefs?: Record<string, string[]>;
  relatedContradictionIds?: string[];
  timelineIds?: string[];
};

export type NoteEntry = {
  id: string;
  text: string;
  tags: string[];
  linkedStatementIds: string[];
  linkedEvidenceIds: string[];
  linkedRecordIds: string[];
  createdAt?: string;
  updatedAt?: string;
};

export type CaseRecord = {
  id: string;
  title: string;
  description: string;
  time: string;
  unlocked: boolean;
};

export type Relationship = {
  id: string;
  suspectId: string;
  suspectName: string;
  description: string;
  conflict: string;
  unlocked: boolean;
};

export type RelationMapNode = {
  characterId: string;
  name: string;
  role?: string;
  kind?: string;
};

export type RelationMapEdge = {
  relationshipId: string;
  sourceCharacterId: string;
  targetCharacterId: string;
  label: string;
  description: string;
  conflict: string;
  unlocked: boolean;
  unlockState?: string;
  evidenceRefs: string[];
  statementRefs: string[];
  recordRefs: string[];
};

export type RelationMap = {
  centerCharacterId: string;
  nodes: RelationMapNode[];
  edges: RelationMapEdge[];
};

export type Statement = {
  id: string;
  suspectId: string;
  speaker: string;
  text: string;
  time: string;
  place: string;
  unlocked: boolean;
  bookmarked: boolean;
};

export type DialogueLogItem = {
  id: string;
  speaker: "player" | "system" | string;
  text: string;
  tag: string;
  suspectId?: string;
  questionId?: string;
  statementId?: string;
  important?: boolean;
  createdAt?: string;
};

export type ContradictionRule = {
  id: string;
  title: string;
  suspectId: string;
  requiredStatementIds: string[];
  requiredEvidenceIds: string[];
  severity: "core" | "major" | "minor";
  message: string;
  unlockedStatementIds?: string[];
  unlockedEvidenceIds?: string[];
};

export type AccusationPayload = {
  suspectId: string;
  motive: string;
  method: string;
  evidenceIds: string[];
  statementIds?: string[];
  contradictionIds?: string[];
};

export type ResultView = {
  verdict: Verdict;
  title: string;
  message: string;
  usedQuestions: number;
  foundContradictions: string[];
  missedClues: string[];
};

export type GameSessionView = {
  sessionId: string;
  caseId: string;
  phase: Phase;
  remainingQuestions: number;
  selectedSuspectId: string | null;
  suspects: Suspect[];
  questions: Question[];
  dialogueLog: DialogueLogItem[];
  evidence: Evidence[];
  notes: NoteEntry[];
  records: CaseRecord[];
  relations: Relationship[];
  relationMap?: RelationMap;
  statements: Statement[];
  unlockedQuestionIds: string[];
  newlyUnlockedIds: string[];
  foundContradictionIds: string[];
  opening: Opening;
  storyline: Storyline;
  currentObjective: CurrentObjective;
  currentActId: string;
  visibleTimeline: TimelineEvent[];
  source?: "api" | "local";
  visualState?: VisualState;
  runtimeDiagnostics?: DialogueRuntimeDiagnostics;
  lastVerdict?: {
    verdict: Verdict;
    message: string;
    contradictionId?: string;
  };
  result?: ResultView;
};
