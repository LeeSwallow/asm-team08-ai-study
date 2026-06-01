import type {
  AccusationPayload,
  CaseSummary,
  ContradictionRule,
  CaseRecord,
  CurrentObjective,
  DialogueLogItem,
  Evidence,
  GameSessionView,
  Opening,
  Question,
  Relationship,
  ResultView,
  Storyline,
  Statement,
  Suspect,
  TimelineEvent,
  Verdict,
} from "./types";

export const mockCase: CaseSummary = {
  id: "case_001",
  title: "진실은, 서로의 말 속에 있다",
  summary: "폭풍우 치던 밤, 저택 2층 서재에서 강도준이 쓰러진 채 발견됐다. 외부 침입 흔적은 없다.",
  victim: "강도준",
  incidentTime: "22:00~22:10",
  location: "저택 2층 서재",
  questionLimit: 12,
};

export const initialSuspects: Suspect[] = [
  {
    id: "char_hanseoyeon",
    name: "한서연",
    role: "조카",
    profile: "상속 문제로 피해자와 갈등이 있었다.",
    motiveHint: "상속 비율 변경",
    color: "#973a2b",
    pressure: 18,
    status: "normal",
  },
  {
    id: "char_yoonjaeho",
    name: "윤재호",
    role: "집사",
    profile: "사건 최초 발견자. 저택 내부 사정을 잘 안다.",
    motiveHint: "유언장 변경 은폐",
    color: "#33404c",
    pressure: 8,
    status: "normal",
  },
  {
    id: "char_parkmingyu",
    name: "박민규",
    role: "주치의",
    profile: "피해자의 건강을 관리했고 처방 문제로 다툰 적이 있다.",
    motiveHint: "처방 책임",
    color: "#5d7892",
    pressure: 10,
    status: "normal",
  },
  {
    id: "char_choiyuna",
    name: "최윤아",
    role: "비서",
    profile: "피해자의 일정과 업무를 관리했다.",
    motiveHint: "비밀 일정",
    color: "#8b643e",
    pressure: 12,
    status: "normal",
  },
];

export const mockOpening: Opening = {
  hook: "폭풍우 치던 밤, 폐쇄된 저택의 서재에서 강도준이 쓰러진 채 발견됐다.",
  objective: "용의자들의 알리바이를 수집하고 같은 시간대의 증거와 충돌하는 진술을 찾으세요.",
  rules: [
    "질문은 제한된 횟수 안에서만 사용할 수 있습니다.",
    "모순 제기는 진술과 증거, 또는 진술과 진술을 연결해 제출합니다.",
    "공개된 단서만으로 현재 목표를 좁혀야 합니다.",
  ],
  victoryCondition: "범인, 동기, 수단, 핵심 모순 근거를 함께 제출합니다.",
};

export const mockStoryline: Storyline = {
  publicPremise: "외부 침입 흔적은 없고, 네 명의 내부 인물이 서로 다른 시간대의 알리바이를 주장한다.",
  acts: [
    {
      actId: "intro",
      title: "도입",
      objective: "사건의 시간, 장소, 초기 단서를 파악합니다.",
      entryCondition: "start",
      focusSuspectIds: ["char_hanseoyeon", "char_yoonjaeho", "char_parkmingyu", "char_choiyuna"],
      recommendedQuestionIds: ["q_hanseoyeon_where", "q_yoonjaeho_found"],
      requiredClueIds: ["ev_study_entry_log", "ev_servant_log"],
      playerHint: "사망 추정 시간과 출입 기록처럼 시간 축을 잡아 주는 단서부터 확인하세요.",
      completionCondition: "초기 증거와 첫 알리바이를 확인한다.",
    },
    {
      actId: "alibi_collection",
      title: "알리바이 수집",
      objective: "각 용의자의 22시 전후 위치 진술을 확보합니다.",
      entryCondition: "질문 시작",
      focusSuspectIds: ["char_hanseoyeon", "char_yoonjaeho", "char_parkmingyu", "char_choiyuna"],
      recommendedQuestionIds: ["q_hanseoyeon_where", "q_yoonjaeho_found", "q_parkmingyu_where", "q_choiyuna_call"],
      requiredClueIds: ["st_hanseoyeon_room_2200", "st_yoonjaeho_found_2210", "st_parkmingyu_guestroom_2200", "st_choiyuna_call_2155"],
      playerHint: "누가 언제 어디에 있었다고 말하는지 진술 카드로 모아 보세요.",
      completionCondition: "주요 용의자의 알리바이 진술을 확보한다.",
    },
    {
      actId: "first_break",
      title: "첫 모순",
      objective: "방에 있었다는 진술과 같은 시간대의 출입 기록을 대조합니다.",
      entryCondition: "알리바이 진술 확보",
      focusSuspectIds: ["char_hanseoyeon"],
      recommendedQuestionIds: ["q_hanseoyeon_where", "q_hanseoyeon_inheritance"],
      requiredClueIds: ["st_hanseoyeon_room_2200", "ev_study_entry_log"],
      playerHint: "같은 시간대에 서로 다른 장소를 가리키는 진술과 기록을 찾아 연결하세요.",
      completionCondition: "첫 핵심 모순을 제기한다.",
    },
    {
      actId: "motive_reveal",
      title: "동기 확정",
      objective: "압박으로 해금된 단서를 통해 갈등의 이유를 좁힙니다.",
      entryCondition: "con_room_claim_vs_entry_log",
      focusSuspectIds: ["char_hanseoyeon", "char_choiyuna"],
      recommendedQuestionIds: ["q_hanseoyeon_inheritance", "q_choiyuna_schedule", "q_yoonjaeho_will"],
      requiredClueIds: ["st_hanseoyeon_no_reason", "ev_torn_will"],
      playerHint: "행동의 모순을 확인했다면, 이제 왜 숨기려 했는지 공개 단서끼리 맞춰 보세요.",
      completionCondition: "동기와 관련된 공개 단서를 연결한다.",
    },
    {
      actId: "final_accusation",
      title: "최종 지목",
      objective: "범인, 동기, 수단, 알리바이 모순 근거를 정리해 제출합니다.",
      entryCondition: "핵심 모순과 동기 단서 확보",
      focusSuspectIds: ["char_hanseoyeon"],
      recommendedQuestionIds: ["q_hanseoyeon_inheritance", "q_yoonjaeho_will"],
      requiredClueIds: ["con_room_claim_vs_entry_log", "con_inheritance_motive"],
      playerHint: "최종 지목은 이름만으로 충분하지 않습니다. 진술과 증거 조합을 함께 제출하세요.",
      completionCondition: "최종 범인 지목을 제출한다.",
    },
  ],
  timeline: [
    {
      time: "21:40",
      title: "회중시계 정지",
      description: "서재 바닥의 회중시계가 21:40에 멈춰 있다.",
      sourceType: "evidence",
      sourceId: "ev_broken_watch",
    },
    {
      time: "21:55",
      title: "마지막 통화",
      description: "피해자가 비서에게 전화를 걸었다는 기록이 있다.",
      sourceType: "evidence",
      sourceId: "ev_phone_call",
      unlockCondition: "q_choiyuna_call",
    },
    {
      time: "22:00",
      title: "주요 알리바이 시간",
      description: "여러 용의자가 22시 전후 자신의 위치를 주장한다.",
      sourceType: "statement",
      sourceId: "st_hanseoyeon_room_2200",
    },
    {
      time: "22:02",
      title: "서재 출입 기록",
      description: "보안 시스템에 특정 인물의 서재 출입 시간이 남아 있다.",
      sourceType: "evidence",
      sourceId: "ev_study_entry_log",
    },
    {
      time: "22:05~22:07",
      title: "저택 일부 정전",
      description: "관리실 기록에 짧은 정전 구간이 남아 있다.",
      sourceType: "evidence",
      sourceId: "ev_storm_blackout",
      unlockCondition: "q_yoonjaeho_found",
    },
    {
      time: "22:10",
      title: "피해자 발견",
      description: "서재 문이 열린 상태로 피해자가 발견됐다.",
      sourceType: "record",
      sourceId: "rec_hallway_patrol",
    },
  ],
  cluePaths: [
    {
      pathId: "path_time_location",
      title: "시간과 장소 대조",
      objective: "알리바이 진술의 시간과 출입 기록의 시간을 비교합니다.",
      steps: [
        { order: 1, type: "statement", id: "st_hanseoyeon_room_2200", prompt: "22시에 어디에 있었다고 말했는지 확인하세요." },
        { order: 2, type: "evidence", id: "ev_study_entry_log", prompt: "같은 시간대의 출입 기록이 어느 장소를 가리키는지 보세요." },
      ],
      resolvesContradictionId: "con_room_claim_vs_entry_log",
      unlocks: ["st_hanseoyeon_pressure", "ev_torn_will"],
    },
    {
      pathId: "path_motive_documents",
      title: "갈등 단서 정리",
      objective: "갈등 진술과 문서형 단서가 같은 방향을 가리키는지 확인합니다.",
      steps: [
        { order: 1, type: "statement", id: "st_hanseoyeon_no_reason", prompt: "갈등은 인정하지만 이유를 부정하는 진술을 찾으세요." },
        { order: 2, type: "evidence", id: "ev_torn_will", prompt: "동기와 관련된 문서 단서가 해금되면 함께 대조하세요." },
      ],
      resolvesContradictionId: "con_inheritance_motive",
      unlocks: [],
    },
  ],
};

function actObjective(actId: string): CurrentObjective {
  const act = mockStoryline.acts.find((item) => item.actId === actId) ?? mockStoryline.acts[0];
  return {
    actId: act.actId,
    title: act.title,
    objective: act.objective,
    playerHint: act.playerHint,
  };
}

function visibleTimelineForSession(session: Pick<GameSessionView, "evidence" | "records" | "statements">): TimelineEvent[] {
  const visibleIds = new Set([
    ...session.evidence.filter((item) => item.unlocked).map((item) => item.id),
    ...session.records.filter((item) => item.unlocked).map((item) => item.id),
    ...session.statements.filter((item) => item.unlocked).map((item) => item.id),
  ]);
  return mockStoryline.timeline.filter((item) => visibleIds.has(item.sourceId) || !item.unlockCondition);
}

export const initialStatements: Statement[] = [
  {
    id: "st_hanseoyeon_room_2200",
    suspectId: "char_hanseoyeon",
    speaker: "한서연",
    text: "저는 22:00에 제 방에 있었어요.",
    time: "22:00",
    place: "자기 방",
    unlocked: true,
    bookmarked: false,
  },
  {
    id: "st_hanseoyeon_no_reason",
    suspectId: "char_hanseoyeon",
    speaker: "한서연",
    text: "상속 문제로 다툰 적은 있지만 죽일 이유는 없었어요.",
    time: "불명",
    place: "불명",
    unlocked: true,
    bookmarked: false,
  },
  {
    id: "st_yoonjaeho_found_2210",
    suspectId: "char_yoonjaeho",
    speaker: "윤재호",
    text: "22:10쯤 서재 문이 열려 있는 걸 봤습니다.",
    time: "22:10",
    place: "서재 앞",
    unlocked: true,
    bookmarked: false,
  },
  {
    id: "st_parkmingyu_guestroom_2200",
    suspectId: "char_parkmingyu",
    speaker: "박민규",
    text: "손님방에서 의료 기록을 정리하고 있었습니다.",
    time: "22:00",
    place: "손님방",
    unlocked: true,
    bookmarked: false,
  },
  {
    id: "st_choiyuna_call_2155",
    suspectId: "char_choiyuna",
    speaker: "최윤아",
    text: "21:55에 전화를 받았지만 직접 만나진 않았습니다.",
    time: "21:55",
    place: "응접실",
    unlocked: true,
    bookmarked: false,
  },
  {
    id: "st_hanseoyeon_pressure",
    suspectId: "char_hanseoyeon",
    speaker: "한서연",
    text: "잠깐 들어갔을 뿐이에요. 그때 이미 상황이 이상했습니다.",
    time: "22:02",
    place: "서재",
    unlocked: false,
    bookmarked: false,
  },
];

export const initialEvidence: Evidence[] = [
  {
    id: "ev_broken_watch",
    title: "깨진 회중시계",
    type: "physical",
    description: "21:40에 멈춰 있다. 유리 파편이 부자연스럽다.",
    source: "서재 바닥",
    time: "21:40",
    reliability: 0.65,
    unlocked: true,
    viewed: false,
    relatedStatementIds: ["st_hanseoyeon_pressure"],
  },
  {
    id: "ev_wine_glass",
    title: "와인잔",
    type: "physical",
    description: "서재 책상에서 발견. 립스틱 흔적이 남아 있다.",
    source: "서재 책상",
    time: "22:00 전후",
    reliability: 0.8,
    unlocked: true,
    viewed: false,
    relatedStatementIds: [],
  },
  {
    id: "ev_study_entry_log",
    title: "서재 출입 기록",
    type: "record",
    description: "22:02에 한서연의 출입 기록이 남아 있다.",
    source: "저택 보안 시스템",
    time: "22:02",
    reliability: 0.95,
    unlocked: true,
    viewed: false,
    relatedStatementIds: ["st_hanseoyeon_room_2200"],
  },
  {
    id: "ev_servant_log",
    title: "부검 전 기록",
    type: "record",
    description: "사망 추정 시각은 22:00~22:10이다.",
    source: "현장 기록",
    time: "22:00~22:10",
    reliability: 0.9,
    unlocked: true,
    viewed: false,
    relatedStatementIds: ["st_yoonjaeho_found_2210"],
  },
  {
    id: "ev_torn_will",
    title: "찢어진 유언장",
    type: "physical",
    description: "상속 비율이 변경된 흔적이 있다.",
    source: "서재 금고 옆",
    time: "불명",
    reliability: 0.85,
    unlocked: false,
    viewed: false,
    relatedStatementIds: ["st_hanseoyeon_no_reason"],
  },
  {
    id: "ev_phone_call",
    title: "통화 기록",
    type: "digital",
    description: "21:55에 피해자가 비서에게 전화를 걸었다.",
    source: "피해자 휴대폰",
    time: "21:55",
    reliability: 0.9,
    unlocked: false,
    viewed: false,
    relatedStatementIds: ["st_choiyuna_call_2155"],
  },
  {
    id: "ev_medicine_box",
    title: "약 상자",
    type: "physical",
    description: "복용 시간이 21:30으로 표시되어 있다.",
    source: "침실",
    time: "21:30",
    reliability: 0.75,
    unlocked: false,
    viewed: false,
    relatedStatementIds: ["st_parkmingyu_guestroom_2200"],
  },
  {
    id: "ev_storm_blackout",
    title: "정전 기록",
    type: "record",
    description: "22:05~22:07 사이 저택 일부가 정전됐다.",
    source: "관리실 로그",
    time: "22:05~22:07",
    reliability: 0.88,
    unlocked: false,
    viewed: false,
    relatedStatementIds: ["st_hanseoyeon_pressure"],
  },
];

export const initialRecords: CaseRecord[] = [
  {
    id: "rec_opening_report",
    title: "초동 수사 보고",
    description: "외부 침입 흔적은 없고 서재 내부에서 충돌 흔적이 발견됐다.",
    time: "22:10",
    unlocked: true,
  },
  {
    id: "rec_hallway_patrol",
    title: "2층 복도 순찰 기록",
    description: "윤재호는 22:10에 서재 앞 복도에 있었다.",
    time: "22:10",
    unlocked: true,
  },
  {
    id: "rec_will_revision_notice",
    title: "유언장 변경 예약 기록",
    description: "피해자는 사건 다음 날 변호사를 만나 유언장 변경을 확정할 예정이었다.",
    time: "사건 다음 날",
    unlocked: false,
  },
];

export const initialRelations: Relationship[] = [
  {
    id: "rel_hanseoyeon_inheritance",
    suspectId: "char_hanseoyeon",
    suspectName: "한서연",
    description: "조카이자 상속 후보",
    conflict: "상속 비율 변경으로 강한 갈등이 있었다.",
    unlocked: true,
  },
  {
    id: "rel_yoonjaeho_loyalty",
    suspectId: "char_yoonjaeho",
    suspectName: "윤재호",
    description: "오래된 집사",
    conflict: "유언장 변경 사실을 숨겼다.",
    unlocked: false,
  },
  {
    id: "rel_parkmingyu_medical",
    suspectId: "char_parkmingyu",
    suspectName: "박민규",
    description: "주치의",
    conflict: "처방 문제로 책임 추궁 가능성이 있었다.",
    unlocked: true,
  },
  {
    id: "rel_choiyuna_schedule",
    suspectId: "char_choiyuna",
    suspectName: "최윤아",
    description: "비서",
    conflict: "피해자의 비밀 일정을 관리했다.",
    unlocked: false,
  },
];

export const initialQuestions: Question[] = [
  {
    id: "q_hanseoyeon_where",
    suspectId: "char_hanseoyeon",
    label: "22시 전후 어디에 있었나요?",
    response: "저는 22:00에 제 방에 있었어요. 폭풍 소리 때문에 아무것도 듣지 못했습니다.",
    statementId: "st_hanseoyeon_room_2200",
  },
  {
    id: "q_hanseoyeon_inheritance",
    suspectId: "char_hanseoyeon",
    label: "상속 문제로 다툰 적 있나요?",
    response: "상속 문제로 다툰 건 사실이지만, 삼촌을 해칠 이유는 없었어요.",
    statementId: "st_hanseoyeon_no_reason",
  },
  {
    id: "q_yoonjaeho_found",
    suspectId: "char_yoonjaeho",
    label: "피해자를 언제 발견했나요?",
    response: "22:10쯤 순찰 중 서재 문이 열려 있는 걸 보고 발견했습니다.",
    statementId: "st_yoonjaeho_found_2210",
    unlockEvidenceIds: ["ev_storm_blackout"],
  },
  {
    id: "q_yoonjaeho_will",
    suspectId: "char_yoonjaeho",
    label: "유언장 변경 사실을 알고 있었나요?",
    response: "회장님이 유언장을 손보려 하셨다는 말은 들었습니다. 자세한 내용은 모릅니다.",
  },
  {
    id: "q_parkmingyu_where",
    suspectId: "char_parkmingyu",
    label: "22시에 어디 있었나요?",
    response: "손님방에서 의료 기록을 정리하고 있었습니다. 약 상자는 침실에 두었습니다.",
    statementId: "st_parkmingyu_guestroom_2200",
    unlockEvidenceIds: ["ev_medicine_box"],
  },
  {
    id: "q_parkmingyu_medicine",
    suspectId: "char_parkmingyu",
    label: "피해자의 약 복용 상태는?",
    response: "복용 시간은 21:30으로 맞춰져 있었습니다. 사망 시각과는 조금 거리가 있습니다.",
  },
  {
    id: "q_choiyuna_call",
    suspectId: "char_choiyuna",
    label: "마지막으로 연락한 때는 언제인가요?",
    response: "21:55에 전화를 받았지만 직접 만나진 않았습니다. 통화 내용은 일정 확인 정도였습니다.",
    statementId: "st_choiyuna_call_2155",
    unlockEvidenceIds: ["ev_phone_call"],
  },
  {
    id: "q_choiyuna_schedule",
    suspectId: "char_choiyuna",
    label: "피해자의 마지막 일정은 무엇이었나요?",
    response: "그날 밤 서재 일정은 비어 있었습니다. 다만 회장님이 누군가를 기다리는 듯했습니다.",
  },
];

export const contradictionRules: ContradictionRule[] = [
  {
    id: "con_room_claim_vs_entry_log",
    title: "방에 있었다는 진술과 서재 출입 기록의 충돌",
    suspectId: "char_hanseoyeon",
    requiredStatementIds: ["st_hanseoyeon_room_2200"],
    requiredEvidenceIds: ["ev_study_entry_log"],
    severity: "core",
    message: "한서연의 22:00 방 진술은 22:02 서재 출입 기록과 충돌합니다.",
    unlockedStatementIds: ["st_hanseoyeon_pressure"],
    unlockedEvidenceIds: ["ev_torn_will"],
  },
  {
    id: "con_watch_time_manipulated",
    title: "회중시계 시각 조작 의혹",
    suspectId: "char_hanseoyeon",
    requiredStatementIds: ["st_hanseoyeon_pressure"],
    requiredEvidenceIds: ["ev_broken_watch", "ev_storm_blackout"],
    severity: "major",
    message: "정전 시간과 부자연스러운 회중시계 파손은 현장 조작 가능성을 높입니다.",
  },
  {
    id: "con_inheritance_motive",
    title: "상속 갈등과 찢어진 유언장",
    suspectId: "char_hanseoyeon",
    requiredStatementIds: ["st_hanseoyeon_no_reason"],
    requiredEvidenceIds: ["ev_torn_will"],
    severity: "core",
    message: "죽일 이유가 없다는 진술은 변경된 유언장과 맞물려 약해집니다.",
  },
  {
    id: "con_call_record",
    title: "피해자의 마지막 통화와 비서의 은폐",
    suspectId: "char_choiyuna",
    requiredStatementIds: ["st_choiyuna_call_2155"],
    requiredEvidenceIds: ["ev_phone_call"],
    severity: "minor",
    message: "최윤아는 마지막 통화를 축소했지만, 이는 범행보다 유언장 변경 정황에 가깝습니다.",
  },
];

export function createMockSession(): GameSessionView {
  return {
    sessionId: `mock_${Date.now()}`,
    caseId: mockCase.id,
    phase: "start",
    remainingQuestions: mockCase.questionLimit,
    selectedSuspectId: "char_hanseoyeon",
    suspects: structuredClone(initialSuspects),
    questions: structuredClone(initialQuestions),
    dialogueLog: [
      {
        id: "log_opening",
        speaker: "system",
        text: "사건 파일이 열렸습니다. 질문은 선택지로만 진행되며, 답변은 기록과 진술 카드에 남습니다.",
        tag: "시스템",
        important: true,
      },
    ],
    evidence: structuredClone(initialEvidence),
    notes: [],
    records: structuredClone(initialRecords),
    relations: structuredClone(initialRelations),
    statements: structuredClone(initialStatements),
    unlockedQuestionIds: initialQuestions.map((question) => question.id),
    newlyUnlockedIds: ["ev_broken_watch", "ev_wine_glass", "ev_study_entry_log", "ev_servant_log"],
    foundContradictionIds: [],
    opening: structuredClone(mockOpening),
    storyline: structuredClone(mockStoryline),
    currentObjective: actObjective("intro"),
    currentActId: "intro",
    visibleTimeline: visibleTimelineForSession({
      evidence: initialEvidence,
      records: initialRecords,
      statements: initialStatements,
    }),
    source: "local",
    visualState: {
      suspectId: "char_hanseoyeon",
      backgroundId: "mansion-study-bg",
      characterImageState: "wary",
      emotionalState: "guarded",
      expression: "wary",
      tensionLevel: "low",
    },
    runtimeDiagnostics: {
      source: "local",
      dialogueMode: "local_mock",
      intent: "fallback",
      matchedQuestionId: null,
      provider: "deterministic-local",
      fallbackUsed: true,
      safety: "not_ai_validated",
      proposedEventsCount: 0,
      appliedEventsCount: 0,
      previousRemainingQuestions: mockCase.questionLimit,
      remainingQuestions: mockCase.questionLimit,
      remainingQuestionsDelta: 0,
      emotionalState: "guarded",
      tensionLevel: "low",
    },
  };
}

export function askMockQuestion(session: GameSessionView, suspectId: string, questionText: string): GameSessionView {
  const typedQuestion = questionText.trim();
  const candidateQuestions = session.questions.filter(
    (item) => item.suspectId === suspectId && session.unlockedQuestionIds.includes(item.id),
  );
  const question =
    candidateQuestions.find((item) => item.label === typedQuestion) ??
    candidateQuestions.find((item) => typedQuestion.includes(item.label.slice(0, 12)) || item.label.includes(typedQuestion.slice(0, 12))) ??
    candidateQuestions.find((item) => !item.used) ??
    candidateQuestions[0];
  if (!question || session.remainingQuestions <= 0) {
    return session;
  }

  const suspect = session.suspects.find((item) => item.id === suspectId);
  const unlockedEvidenceIds = question.unlockEvidenceIds ?? [];
  const logItems: DialogueLogItem[] = [
    {
      id: `log_q_${question.id}_${Date.now()}`,
      speaker: "player",
      text: typedQuestion,
      tag: "자유 질문",
    },
    {
      id: `log_a_${question.id}_${Date.now()}`,
      speaker: suspect?.name ?? "용의자",
      text: question.response,
      tag: question.statementId ? "진술 추출" : "답변",
      statementId: question.statementId,
      important: Boolean(question.statementId),
    },
  ];

  const nextEvidence = session.evidence.map((item) =>
    unlockedEvidenceIds.includes(item.id) ? { ...item, unlocked: true, viewed: false } : item,
  );
  const nextStatements = session.statements;
  const nextRecords = session.records;
  const nextActId = session.currentActId === "intro" ? "alibi_collection" : session.currentActId;

  return {
    ...session,
    phase: "investigation",
    remainingQuestions: Math.max(0, session.remainingQuestions - 1),
    selectedSuspectId: suspectId,
    dialogueLog: [...session.dialogueLog, ...logItems],
    evidence: nextEvidence,
    statements: nextStatements,
    records: nextRecords,
    questions: session.questions.map((item) => (item.id === question.id ? { ...item, used: true } : item)),
    newlyUnlockedIds: Array.from(new Set([...session.newlyUnlockedIds, ...unlockedEvidenceIds])),
    currentActId: nextActId,
    currentObjective: actObjective(nextActId),
    visibleTimeline: visibleTimelineForSession({ evidence: nextEvidence, records: nextRecords, statements: nextStatements }),
    visualState: {
      suspectId,
      backgroundId: "mansion-study-bg",
      characterImageState: "wary",
      emotionalState: "guarded",
      expression: "wary",
      tensionLevel: "low",
    },
    runtimeDiagnostics: {
      source: "local",
      dialogueMode: "local_mock",
      intent: "fallback",
      matchedQuestionId: question.id,
      provider: "deterministic-local",
      fallbackUsed: true,
      safety: "not_ai_validated",
      proposedEventsCount: 0,
      appliedEventsCount: 0,
      previousRemainingQuestions: session.remainingQuestions,
      remainingQuestions: Math.max(0, session.remainingQuestions - 1),
      remainingQuestionsDelta: session.remainingQuestions - Math.max(0, session.remainingQuestions - 1),
      emotionalState: "guarded",
      tensionLevel: "low",
    },
  };
}

export function submitMockContradiction(
  session: GameSessionView,
  statementIds: string[],
  evidenceIds: string[],
): GameSessionView {
  const exactRule = contradictionRules.find(
    (rule) =>
      rule.requiredStatementIds.every((id) => statementIds.includes(id)) &&
      rule.requiredEvidenceIds.every((id) => evidenceIds.includes(id)),
  );
  const relatedRule = contradictionRules.find(
    (rule) =>
      rule.requiredStatementIds.some((id) => statementIds.includes(id)) ||
      rule.requiredEvidenceIds.some((id) => evidenceIds.includes(id)),
  );
  const verdict: Verdict = exactRule ? "correct" : relatedRule ? "partial" : "wrong";
  const targetRule = exactRule ?? relatedRule;
  const message =
    verdict === "correct"
      ? targetRule?.message ?? "모순이 확인되었습니다."
      : verdict === "partial"
        ? "방향은 맞지만 필수 진술 또는 증거가 부족합니다. 시간대와 출입 기록을 다시 대조하세요."
        : "현재 조합은 사건 그래프상 관련성이 약합니다.";
  const unlockedStatementIds = exactRule?.unlockedStatementIds ?? [];
  const unlockedEvidenceIds = exactRule?.unlockedEvidenceIds ?? [];
  const foundContradictionIds =
    exactRule && !session.foundContradictionIds.includes(exactRule.id)
      ? [...session.foundContradictionIds, exactRule.id]
      : session.foundContradictionIds;

  const nextStatements = session.statements.map((item) =>
    unlockedStatementIds.includes(item.id) ? { ...item, unlocked: true } : item,
  );
  const nextEvidence = session.evidence.map((item) =>
    unlockedEvidenceIds.includes(item.id) ? { ...item, unlocked: true, viewed: false } : item,
  );
  const nextRecords = session.records.map((item) =>
    unlockedEvidenceIds.includes(item.id) ? { ...item, unlocked: true } : item,
  );
  const nextRelations = session.relations.map((item) =>
    unlockedEvidenceIds.includes(item.id) ? { ...item, unlocked: true } : item,
  );
  const nextActId = exactRule?.id === "con_room_claim_vs_entry_log"
    ? "motive_reveal"
    : exactRule?.id === "con_inheritance_motive"
      ? "final_accusation"
      : exactRule
        ? "first_break"
        : session.currentActId;

  return {
    ...session,
    phase: "contradiction",
    suspects: session.suspects.map((suspect) => {
      if (!targetRule || suspect.id !== targetRule.suspectId) return suspect;
      const pressure = Math.min(100, suspect.pressure + (verdict === "correct" ? 42 : 14));
      return {
        ...suspect,
        pressure,
        status: pressure >= 70 ? "broken" : "pressed",
      };
    }),
    statements: nextStatements,
    evidence: nextEvidence,
    records: nextRecords,
    relations: nextRelations,
    newlyUnlockedIds: Array.from(new Set([...session.newlyUnlockedIds, ...unlockedStatementIds, ...unlockedEvidenceIds])),
    foundContradictionIds,
    currentActId: nextActId,
    currentObjective: actObjective(nextActId),
    visibleTimeline: visibleTimelineForSession({ evidence: nextEvidence, records: nextRecords, statements: nextStatements }),
    dialogueLog: [
      ...session.dialogueLog,
      {
        id: `log_con_${Date.now()}`,
        speaker: "system",
        text: message,
        tag: verdict === "correct" ? "모순 발견" : verdict === "partial" ? "부분 판정" : "근거 부족",
        important: verdict !== "wrong",
      },
    ],
    lastVerdict: {
      verdict,
      message,
      contradictionId: exactRule?.id,
    },
  };
}

export function submitMockAccusation(session: GameSessionView, payload: AccusationPayload): GameSessionView {
  const hasPublicEvidence = payload.evidenceIds.length > 0 || payload.statementIds?.length || payload.contradictionIds?.length;
  const verdict: Verdict = hasPublicEvidence ? "insufficient" : "wrong";
  const result: ResultView = {
    verdict,
    title: "LOCAL/MOCK: 최종 판정 불가",
    message:
      "로컬 fallback은 정답/범인/해결 정보를 보유하지 않습니다. 최종 고발 판정은 BE 세션 응답으로만 확인해야 합니다.",
    usedQuestions: mockCase.questionLimit - session.remainingQuestions,
    foundContradictions: session.foundContradictionIds,
    missedClues: [],
  };

  return {
    ...session,
    phase: "result",
    result,
    currentActId: "final_accusation",
    currentObjective: actObjective("final_accusation"),
    dialogueLog: [
      ...session.dialogueLog,
      {
        id: `log_result_${Date.now()}`,
        speaker: "system",
        text: result.message,
        tag: "최종 판정",
        important: true,
      },
    ],
  };
}
