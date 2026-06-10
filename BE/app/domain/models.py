from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Phase = Literal["investigation", "accusation", "solved", "failed"]


class Opening(BaseModel):
    hook: str
    objective: str
    rules: List[str] = Field(default_factory=list)
    victoryCondition: str


class StoryAct(BaseModel):
    actId: str
    title: str
    objective: str
    entryCondition: str
    focusSuspectIds: List[str] = Field(default_factory=list)
    recommendedQuestionIds: List[str] = Field(default_factory=list)
    requiredClueIds: List[str] = Field(default_factory=list)
    playerHint: str
    completionCondition: str


class TimelineEvent(BaseModel):
    timelineId: Optional[str] = None
    time: str
    title: str
    description: str
    sourceType: str
    sourceId: str
    hidden: bool = False
    unlockCondition: Optional[str] = None


class CluePathStep(BaseModel):
    order: int
    type: str
    id: str
    prompt: str


class CluePath(BaseModel):
    pathId: str
    title: str
    objective: str
    steps: List[CluePathStep] = Field(default_factory=list)
    resolvesContradictionId: Optional[str] = None
    unlocks: List[str] = Field(default_factory=list)
    secretNote: Optional[str] = None


class ObjectiveRuleCondition(BaseModel):
    missingContradictionId: Optional[str] = None
    discoveredContradictionId: Optional[str] = None
    pressureAtLeast: Optional[Dict[str, Any]] = None


class ObjectiveRule(BaseModel):
    priority: int
    when: ObjectiveRuleCondition = Field(default_factory=ObjectiveRuleCondition)
    objective: str
    actId: str


class Storyline(BaseModel):
    publicPremise: str
    acts: List[StoryAct] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    cluePaths: List[CluePath] = Field(default_factory=list)
    currentObjectiveRules: List[ObjectiveRule] = Field(default_factory=list)


class Character(BaseModel):
    characterId: str
    name: str
    role: str
    publicProfile: str
    secret: Optional[str] = None
    motiveCandidate: bool = False
    isCulprit: bool = False
    speechStyle: Dict[str, Any] = Field(default_factory=dict)
    publicTimeline: List[Dict[str, Any]] = Field(default_factory=list)
    personaVariants: List[Dict[str, Any]] = Field(default_factory=list)


class Evidence(BaseModel):
    evidenceId: str
    name: str
    type: str
    description: str
    foundAt: str
    timeWindow: Optional[str] = None
    reliability: float
    initiallyVisible: bool = False
    unlockCondition: Optional[str] = None


class Record(BaseModel):
    recordId: str
    name: str
    description: str
    timeWindow: Optional[str] = None
    initiallyVisible: bool = False
    unlockCondition: Optional[str] = None


class Relationship(BaseModel):
    relationshipId: str
    characterId: str
    description: str
    conflict: str
    initiallyVisible: bool = False
    unlockCondition: Optional[str] = None


class Statement(BaseModel):
    statementId: str
    characterId: str
    questionText: str
    text: str
    timeWindow: Optional[str] = None
    location: Optional[str] = None
    initiallyVisible: bool = False
    unlockCondition: Optional[str] = None


class Question(BaseModel):
    questionId: str
    characterId: str
    text: str
    answer: str
    playerParaphrases: List[str] = Field(default_factory=list)
    unlocksStatementIds: List[str] = Field(default_factory=list)
    unlocksEvidenceIds: List[str] = Field(default_factory=list)
    unlocksRecordIds: List[str] = Field(default_factory=list)
    unlocksRelationIds: List[str] = Field(default_factory=list)
    initiallyUnlocked: bool = False
    unlockCondition: Optional[str] = None


class Contradiction(BaseModel):
    contradictionId: str
    title: str
    relatedCharacterId: str
    requiredStatementIds: List[str]
    requiredEvidenceIds: List[str]
    severity: Literal["minor", "major", "core"]
    pressureDelta: int
    reasonCode: str
    message: str
    unlockedIds: List[str] = Field(default_factory=list)


class Solution(BaseModel):
    culpritId: str
    motive: str
    method: str
    requiredContradictionIds: List[str]
    requiredEvidenceIds: List[str]
    requiredStatementIds: List[str]
    endings: Dict[str, str]


class Case(BaseModel):
    caseId: str
    sceneId: str
    title: str
    summary: str
    victimId: str
    victimName: str
    incidentTime: str
    incidentLocation: str
    questionLimit: int
    opening: Optional[Opening] = None
    storyline: Optional[Storyline] = None
    suspects: List[Character]
    evidence: List[Evidence]
    records: List[Record] = Field(default_factory=list)
    relations: List[Relationship] = Field(default_factory=list)
    statements: List[Statement]
    questions: List[Question]
    contradictions: List[Contradiction]
    solution: Solution


class DialogueEntry(BaseModel):
    id: str
    suspectId: Optional[str] = None
    questionId: Optional[str] = None
    speaker: str
    text: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)


class NoteEntry(BaseModel):
    id: str
    text: str
    tags: List[str] = Field(default_factory=list)
    linkedContradictionIds: List[str] = Field(default_factory=list)
    linkedStatementIds: List[str] = Field(default_factory=list)
    linkedEvidenceIds: List[str] = Field(default_factory=list)
    linkedRecordIds: List[str] = Field(default_factory=list)
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)


class BookmarkEntry(BaseModel):
    id: str
    targetType: Literal["dialogue", "statement", "evidence", "record", "relation"]
    targetId: str
    note: Optional[str] = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)


class EventEntry(BaseModel):
    id: str
    sessionId: str
    caseId: str
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime = Field(default_factory=datetime.utcnow)


class SessionState(BaseModel):
    sessionId: str
    caseId: str
    phase: Phase = "investigation"
    remainingQuestions: int
    selectedSuspectId: Optional[str] = None
    dialogueLog: List[DialogueEntry] = Field(default_factory=list)
    notes: List[NoteEntry] = Field(default_factory=list)
    bookmarks: List[BookmarkEntry] = Field(default_factory=list)
    unlockedEvidenceIds: List[str] = Field(default_factory=list)
    unlockedRecordIds: List[str] = Field(default_factory=list)
    unlockedRelationIds: List[str] = Field(default_factory=list)
    unlockedStatementIds: List[str] = Field(default_factory=list)
    unlockedQuestionIds: List[str] = Field(default_factory=list)
    askedQuestionCounts: Dict[str, int] = Field(default_factory=dict)
    discoveredContradictionIds: List[str] = Field(default_factory=list)
    partialPressureKeys: List[str] = Field(default_factory=list)
    pressureBySuspect: Dict[str, int] = Field(default_factory=dict)
    newlyUnlockedIds: List[str] = Field(default_factory=list)
    accusation: Optional[Dict[str, Any]] = None
    lastDialogueResult: Optional[Dict[str, Any]] = None
    lastRuntimeDiagnostics: Optional[Dict[str, Any]] = None
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)
