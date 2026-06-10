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

export type CaseDetail = CaseSummary & {
  opening?: Opening;
  publicPremise?: string;
  suspectCount: number;
  visibleEvidenceCount: number;
  visibleRecordCount: number;
  visibleStatementCount: number;
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
  pressureState?: string;
  pressureStage?: string;
  tensionLevel?: VisualState["tensionLevel"];
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

export type CharacterReactionDiagnostic = {
  owner?: string;
  suspectId?: string;
  route?: string;
  reactionRoute?: string;
  label?: string;
  effect?: string;
  confidence?: number;
  playerClaimAssessment?: string;
  characterStance?: string;
  responseIntent?: string;
  playerFacingReason?: string;
  publicOnly?: boolean;
  appliedStateChange?: boolean;
};

export type HelperSuggestion = {
  helperRoute: "nudge_evidence" | "nudge_relation" | "nudge_contradiction" | "nudge_switch_suspect" | "nudge_accusation_ready" | "silent" | string;
  confidence: number;
  tone: "noir_assistant" | string;
  message: string;
  suggestedActions: Array<{ type: string; targetId: string; label: string }>;
  publicRefs: {
    evidenceIds: string[];
    statementIds: string[];
    relationIds: string[];
    suspectIds: string[];
  };
};

export type PressureGates = {
  stages: string[];
  guidance: string;
};

export type DisclosureLadderStage = {
  stage: string;
  state: string;
  dialogueGoal: string;
};

export type DisclosureLadder = {
  suspectId: string;
  suspectName: string;
  currentStage: string;
  stages: DisclosureLadderStage[];
};

export type DialogueRuntimeDiagnostics = {
  source: "api";
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
  characterReaction?: CharacterReactionDiagnostic;
  characterReactionRoute?: string;
  helperSuggestion?: HelperSuggestion;
};

export type GameEventFeedItem = {
  id: string;
  type: string;
  title: string;
  message: string;
  createdAt?: string;
  payload?: Record<string, unknown>;
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
  linkedContradictionIds?: string[];
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
  outcome: "victory" | "defeat";
  title: string;
  message: string;
  usedQuestions: number;
  foundContradictions: string[];
  missedClues: string[];
};

export type AccusationReadiness = {
  eligible: boolean;
  missingRequiredContradictionCount: number;
  missingRequiredEvidenceCount: number;
  missingRequiredStatementCount: number;
  discoveredRequiredContradictionCount: number;
  discoveredRequiredEvidenceCount: number;
  discoveredRequiredStatementCount: number;
  requiredContradictionCount: number;
  requiredEvidenceCount?: number;
  requiredStatementCount?: number;
};

export type PublicContradiction = {
  contradictionId: string;
  title: string;
  suspectId: string;
  suspectName?: string;
  statementIds: string[];
  evidenceIds: string[];
  requiredStatementIds?: string[];
  requiredEvidenceIds?: string[];
  severity?: "core" | "major" | "minor" | string;
  reasonCode?: string;
  displayText: string;
  allRequiredVisible?: boolean;
  status: "discovered" | "candidate" | string;
  submitEligible?: boolean;
};

export type PublicContradictionReadModel = {
  discoveredIds: string[];
  discovered: PublicContradiction[];
  candidates: PublicContradiction[];
};

export type GameSessionView = {
  sessionId: string;
  caseId: string;
  phase: Phase;
  remainingQuestions: number;
  questionLimit: number;
  visibleEvidenceCount: number;
  totalEvidenceCount: number;
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
  contradictions: PublicContradictionReadModel;
  accusationReadiness?: AccusationReadiness;
  opening: Opening;
  storyline: Storyline;
  currentObjective: CurrentObjective;
  currentActId: string;
  visibleTimeline: TimelineEvent[];
  source?: "api";
  visualState?: VisualState;
  latestEvents?: GameEventFeedItem[];
  runtimeDiagnostics?: DialogueRuntimeDiagnostics;
  helperSuggestion?: HelperSuggestion;
  pressureGates?: PressureGates;
  disclosureLadders?: DisclosureLadder[];
  lastVerdict?: {
    verdict: Verdict;
    message: string;
    contradictionId?: string;
  };
  result?: ResultView;
};
