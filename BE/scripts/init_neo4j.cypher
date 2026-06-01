// ============================================================
// Detective Agent — Neo4j 케이스 초기화 Cypher
// case_001: 진실은, 서로의 말 속에 있다
//
// 실행 방법:
//   neo4j-client -u neo4j -p detective_secret < scripts/init_neo4j.cypher
// 또는 Neo4j Browser에서 직접 붙여넣기
// ============================================================

// ── 기존 케이스 데이터 삭제 (idempotent) ────────────────────────────────────
MATCH (n {caseId: 'case_001'}) DETACH DELETE n;

// ── Case 노드 ────────────────────────────────────────────────────────────────
CREATE (c:Case {
  caseId:           'case_001',
  sceneId:          'scene_001',
  title:            '진실은, 서로의 말 속에 있다',
  summary:          '폭풍우가 저택을 고립시킨 밤, 73세 실업가 강도준이 2층 서재에서 쓰러진 채 발견됐다.',
  victimId:         'victim_kangdojun',
  victimName:       '강도준',
  incidentTime:     '22:00~22:10',
  incidentLocation: '저택 2층 서재',
  questionLimit:    12
});

// ── Character 노드 ────────────────────────────────────────────────────────────
CREATE (ch1:Character {
  caseId:       'case_001',
  characterId:  'char_hanseoyeon',
  name:         '한서연',
  role:         '조카',
  publicPersona:'강도준의 조카. 사업 실패 후 상속에 기대는 처지였다.',
  isCulprit:    true,
  secret:       '22:02에 서재에 들어갔고 정전 중 현장을 조작했다.',
  speechStyleTic:'…',
  speechStyleVocabulary: '사실은,아니,그게,그냥'
});

CREATE (ch2:Character {
  caseId:       'case_001',
  characterId:  'char_yoonjaeho',
  name:         '윤재호',
  role:         '집사',
  publicPersona:'강도준을 30년째 모신 집사. 저택 구조와 가족 사정을 속속들이 안다.',
  isCulprit:    false,
  secret:       '피해자의 유언장 변경 사실과 한서연의 재정 상태를 알고 있었다.',
  speechStylePrefix: '말씀드리자면 ',
  speechStyleVocabulary: '회장님,정확히는,확인하건대,제가 기억하기론'
});

CREATE (ch3:Character {
  caseId:       'case_001',
  characterId:  'char_parkmingyu',
  name:         '박민규',
  role:         '주치의',
  publicPersona:'강도준의 주치의. 15년간 건강을 관리해 왔다.',
  isCulprit:    false,
  secret:       '처방 변경 문제로 피해자와 마지막으로 언쟁을 벌인 사람이다.',
  speechStyleVocabulary: '의학적으로,임상적으로,확인하건대,기록상'
});

CREATE (ch4:Character {
  caseId:       'case_001',
  characterId:  'char_choiyuna',
  name:         '최윤아',
  role:         '비서',
  publicPersona:'강도준의 비서. 일정과 업무를 7년째 관리해 왔다.',
  isCulprit:    false,
  secret:       '피해자가 비밀리에 유언장 변경을 준비한 사실을 알고 있었다.',
  speechStyleTic: '네,',
  speechStyleVocabulary: '일정상,회장님,확인했습니다,기록에'
});

// Case → Character
MATCH (c:Case {caseId: 'case_001'})
MATCH (ch:Character {caseId: 'case_001'})
CREATE (c)-[:HAS_CHARACTER]->(ch);

// ── Evidence 노드 ─────────────────────────────────────────────────────────────
MATCH (c:Case {caseId: 'case_001'})

CREATE (e1:Evidence {
  caseId: 'case_001', evidenceId: 'ev_broken_watch',
  name: '깨진 회중시계', type: 'physical',
  description: '서재 바닥. 21:40에 멈춰 있지만 유리 파편 흩어짐이 부자연스럽다.',
  foundAt: '서재 바닥', timeWindow: '21:40',
  reliability: 0.65, initiallyVisible: true, unlockCondition: ''
}),
(e2:Evidence {
  caseId: 'case_001', evidenceId: 'ev_wine_glass',
  name: '와인잔', type: 'physical',
  description: '서재 책상. 특정 색상의 립스틱 흔적.',
  foundAt: '서재 책상', timeWindow: '22:00 전후',
  reliability: 0.8, initiallyVisible: true, unlockCondition: ''
}),
(e3:Evidence {
  caseId: 'case_001', evidenceId: 'ev_study_entry_log',
  name: '서재 출입 기록', type: 'record',
  description: '22:02에 한서연의 카드키 출입 기록. 퇴실 기록 없음.',
  foundAt: '저택 보안 시스템', timeWindow: '22:02',
  reliability: 0.95, initiallyVisible: true, unlockCondition: ''
}),
(e4:Evidence {
  caseId: 'case_001', evidenceId: 'ev_servant_log',
  name: '부검 전 현장 기록', type: 'record',
  description: '사망 추정 시각 22:00~22:10. 두부 외상이 1차 사인.',
  foundAt: '현장 기록', timeWindow: '22:00~22:10',
  reliability: 0.9, initiallyVisible: true, unlockCondition: ''
}),
(e5:Evidence {
  caseId: 'case_001', evidenceId: 'ev_torn_will',
  name: '찢어진 유언장', type: 'physical',
  description: '한서연의 상속 비율이 크게 줄어드는 내용.',
  foundAt: '서재 금고 옆', timeWindow: '불명',
  reliability: 0.85, initiallyVisible: false, unlockCondition: 'con_room_claim_vs_entry_log'
}),
(e6:Evidence {
  caseId: 'case_001', evidenceId: 'ev_phone_call',
  name: '통화 기록', type: 'digital',
  description: '21:55에 피해자가 최윤아에게 전화. 3분 12초.',
  foundAt: '피해자 휴대폰', timeWindow: '21:55',
  reliability: 0.9, initiallyVisible: false, unlockCondition: 'q_choiyuna_last_call'
}),
(e7:Evidence {
  caseId: 'case_001', evidenceId: 'ev_medicine_box',
  name: '약 상자', type: 'physical',
  description: '복용 시간 21:30. 치명적 약물 반응 흔적 없음.',
  foundAt: '피해자 침실', timeWindow: '21:30',
  reliability: 0.75, initiallyVisible: false, unlockCondition: 'q_parkmingyu_medicine'
}),
(e8:Evidence {
  caseId: 'case_001', evidenceId: 'ev_storm_blackout',
  name: '정전 기록', type: 'record',
  description: '22:05~22:07 저택 2층 정전. CCTV도 꺼짐.',
  foundAt: '관리실 로그', timeWindow: '22:05~22:07',
  reliability: 0.88, initiallyVisible: false, unlockCondition: 'q_yoonjaeho_blackout'
}),
(e9:Evidence {
  caseId: 'case_001', evidenceId: 'ev_ring_near_victim',
  name: '반지', type: 'physical',
  description: '피해자 발 근처 은색 아트 누보 반지.',
  foundAt: '서재 피해자 주변', timeWindow: '22:00~22:10',
  reliability: 0.9, initiallyVisible: false, unlockCondition: 'con_room_claim_vs_entry_log'
}),
(e10:Evidence {
  caseId: 'case_001', evidenceId: 'ev_lipstick_tube',
  name: '립스틱 케이스', type: 'physical',
  description: '서재 쓰레기통. 와인잔 흔적과 색상 일치.',
  foundAt: '서재 쓰레기통', timeWindow: '불명',
  reliability: 0.7, initiallyVisible: false, unlockCondition: 'q_choiyuna_wine'
}),
(e11:Evidence {
  caseId: 'case_001', evidenceId: 'ev_window_bolt',
  name: '창문 빗장 상태', type: 'record',
  description: '서재 모든 창문 빗장이 안쪽에서 잠김. 외부 진입 불가.',
  foundAt: '서재 창문', timeWindow: '22:10',
  reliability: 0.98, initiallyVisible: true, unlockCondition: ''
}),
(e12:Evidence {
  caseId: 'case_001', evidenceId: 'ev_deleted_cctv',
  name: 'CCTV 공백 구간', type: 'digital',
  description: '22:05~22:07 2층 복도 CCTV 2분 12초 공백. 직전 프레임 실루엣 포착.',
  foundAt: '저택 CCTV 시스템', timeWindow: '22:05~22:07',
  reliability: 0.75, initiallyVisible: false, unlockCondition: 'con_watch_time_manipulated'
})

CREATE (c)-[:HAS_EVIDENCE]->(e1),
       (c)-[:HAS_EVIDENCE]->(e2),
       (c)-[:HAS_EVIDENCE]->(e3),
       (c)-[:HAS_EVIDENCE]->(e4),
       (c)-[:HAS_EVIDENCE]->(e5),
       (c)-[:HAS_EVIDENCE]->(e6),
       (c)-[:HAS_EVIDENCE]->(e7),
       (c)-[:HAS_EVIDENCE]->(e8),
       (c)-[:HAS_EVIDENCE]->(e9),
       (c)-[:HAS_EVIDENCE]->(e10),
       (c)-[:HAS_EVIDENCE]->(e11),
       (c)-[:HAS_EVIDENCE]->(e12);

// ── Statement 노드 + MADE_STATEMENT 관계 ─────────────────────────────────────
MATCH (ch1:Character {caseId: 'case_001', characterId: 'char_hanseoyeon'})
MATCH (ch2:Character {caseId: 'case_001', characterId: 'char_yoonjaeho'})
MATCH (ch3:Character {caseId: 'case_001', characterId: 'char_parkmingyu'})
MATCH (ch4:Character {caseId: 'case_001', characterId: 'char_choiyuna'})
MATCH (c:Case {caseId: 'case_001'})

CREATE (s1:Statement {
  caseId: 'case_001', statementId: 'st_hanseoyeon_room_2200',
  text: '저는 22:00에 제 방에 있었어요.',
  questionText: '22:00에 어디 있었나요?',
  timeWindow: '22:00', location: '자기 방', initiallyVisible: true
}),
(s2:Statement {
  caseId: 'case_001', statementId: 'st_hanseoyeon_no_reason',
  text: '상속 문제로 다툰 적은 있지만 죽일 이유는 없었어요.',
  questionText: '상속 문제로 다툰 적 있나요?',
  timeWindow: '불명', location: '불명', initiallyVisible: true
}),
(s3:Statement {
  caseId: 'case_001', statementId: 'st_hanseoyeon_wine_deny',
  text: '와인잔은 제 것이 아니에요. 그날 저는 와인을 마시지 않았습니다.',
  questionText: '서재의 와인잔을 알고 있나요?',
  timeWindow: '불명', location: '불명', initiallyVisible: true
}),
(s4:Statement {
  caseId: 'case_001', statementId: 'st_hanseoyeon_pressure',
  text: '잠깐 들어갔을 뿐이에요. 그때 이미 상황이 이상했습니다.',
  questionText: '서재 출입 기록을 제시한다',
  timeWindow: '22:02', location: '서재', initiallyVisible: false, unlockCondition: 'con_room_claim_vs_entry_log'
}),
(s5:Statement {
  caseId: 'case_001', statementId: 'st_hanseoyeon_ring_missing',
  text: '…반지가 없어졌는데, 어디서 잃어버렸는지 모르겠어요.',
  questionText: '반지를 잃어버린 적 있나요?',
  timeWindow: '불명', location: '불명', initiallyVisible: false, unlockCondition: 'ev_ring_near_victim'
}),
(s6:Statement {
  caseId: 'case_001', statementId: 'st_yoonjaeho_found_2210',
  text: '22:10쯤 서재 문이 열려 있는 걸 보고 발견했습니다.',
  questionText: '피해자를 언제 발견했나요?',
  timeWindow: '22:10', location: '서재 앞', initiallyVisible: true
}),
(s7:Statement {
  caseId: 'case_001', statementId: 'st_yoonjaeho_1f_2200',
  text: '말씀드리자면 22:00부터는 1층 식당에서 정리 작업을 하고 있었습니다.',
  questionText: '22:00에 어디 있었나요?',
  timeWindow: '22:00', location: '1층 식당', initiallyVisible: true
}),
(s8:Statement {
  caseId: 'case_001', statementId: 'st_yoonjaeho_key_only_victim',
  text: '말씀드리자면 서재 열쇠는 회장님 것과 제 것 두 개뿐입니다. 카드키는 가족에게도 발급됩니다만.',
  questionText: '서재 열쇠 관리는 어떻게 됩니까?',
  timeWindow: '불명', location: '불명', initiallyVisible: true
}),
(s9:Statement {
  caseId: 'case_001', statementId: 'st_yoonjaeho_blackout',
  text: '관리실 쪽 전등이 꺼져 복도를 확인하고 있었습니다.',
  questionText: '정전 당시 무엇을 했나요?',
  timeWindow: '22:05~22:07', location: '2층 복도', initiallyVisible: false, unlockCondition: 'q_yoonjaeho_blackout'
}),
(s10:Statement {
  caseId: 'case_001', statementId: 'st_parkmingyu_guestroom_2200',
  text: '손님방에서 의료 기록을 정리하고 있었습니다.',
  questionText: '22:00에 어디 있었나요?',
  timeWindow: '22:00', location: '손님방', initiallyVisible: true
}),
(s11:Statement {
  caseId: 'case_001', statementId: 'st_parkmingyu_medicine',
  text: '21:30 복용분까지 확인했고 이후에는 손대지 않았습니다.',
  questionText: '약은 언제 확인했나요?',
  timeWindow: '21:30', location: '침실', initiallyVisible: false, unlockCondition: 'q_parkmingyu_medicine'
}),
(s12:Statement {
  caseId: 'case_001', statementId: 'st_parkmingyu_left_early',
  text: '의학적으로 더 할 일이 없어서 21:45에 손님방을 나와 1층으로 내려왔습니다.',
  questionText: '21:45 이후 무엇을 했나요?',
  timeWindow: '21:45', location: '1층 응접실', initiallyVisible: true
}),
(s13:Statement {
  caseId: 'case_001', statementId: 'st_choiyuna_call_2155',
  text: '21:55에 전화를 받았지만 직접 만나진 않았습니다.',
  questionText: '피해자와 마지막으로 연락한 때는?',
  timeWindow: '21:55', location: '응접실', initiallyVisible: true
}),
(s14:Statement {
  caseId: 'case_001', statementId: 'st_choiyuna_no_wine',
  text: '네, 저는 그날 와인을 마시지 않았습니다. 립스틱 색도 제 것이 아닙니다.',
  questionText: '와인잔에 대해 알고 있나요?',
  timeWindow: '불명', location: '불명', initiallyVisible: true
}),
(s15:Statement {
  caseId: 'case_001', statementId: 'st_choiyuna_location_2200',
  text: '네, 응접실에서 내일 일정 서류를 정리하고 있었어요.',
  questionText: '22:00에 어디 있었나요?',
  timeWindow: '22:00', location: '응접실', initiallyVisible: true
}),
(s16:Statement {
  caseId: 'case_001', statementId: 'st_choiyuna_call_record',
  text: '회장님은 내일 변호사를 부르라고 지시했습니다. 유언장 때문이라고 들었습니다.',
  questionText: '통화 내용을 말해 주세요.',
  timeWindow: '21:55', location: '응접실', initiallyVisible: false, unlockCondition: 'q_choiyuna_last_call'
})

// Case → Statement
CREATE (c)-[:HAS_STATEMENT]->(s1),
       (c)-[:HAS_STATEMENT]->(s2),
       (c)-[:HAS_STATEMENT]->(s3),
       (c)-[:HAS_STATEMENT]->(s4),
       (c)-[:HAS_STATEMENT]->(s5),
       (c)-[:HAS_STATEMENT]->(s6),
       (c)-[:HAS_STATEMENT]->(s7),
       (c)-[:HAS_STATEMENT]->(s8),
       (c)-[:HAS_STATEMENT]->(s9),
       (c)-[:HAS_STATEMENT]->(s10),
       (c)-[:HAS_STATEMENT]->(s11),
       (c)-[:HAS_STATEMENT]->(s12),
       (c)-[:HAS_STATEMENT]->(s13),
       (c)-[:HAS_STATEMENT]->(s14),
       (c)-[:HAS_STATEMENT]->(s15),
       (c)-[:HAS_STATEMENT]->(s16)

// Character → Statement (MADE_STATEMENT)
CREATE (ch1)-[:MADE_STATEMENT]->(s1),
       (ch1)-[:MADE_STATEMENT]->(s2),
       (ch1)-[:MADE_STATEMENT]->(s3),
       (ch1)-[:MADE_STATEMENT]->(s4),
       (ch1)-[:MADE_STATEMENT]->(s5),
       (ch2)-[:MADE_STATEMENT]->(s6),
       (ch2)-[:MADE_STATEMENT]->(s7),
       (ch2)-[:MADE_STATEMENT]->(s8),
       (ch2)-[:MADE_STATEMENT]->(s9),
       (ch3)-[:MADE_STATEMENT]->(s10),
       (ch3)-[:MADE_STATEMENT]->(s11),
       (ch3)-[:MADE_STATEMENT]->(s12),
       (ch4)-[:MADE_STATEMENT]->(s13),
       (ch4)-[:MADE_STATEMENT]->(s14),
       (ch4)-[:MADE_STATEMENT]->(s15),
       (ch4)-[:MADE_STATEMENT]->(s16);

// ── Question 노드 + HAS_QUESTION 관계 ────────────────────────────────────────
MATCH (c:Case {caseId: 'case_001'})
MATCH (ch1:Character {caseId: 'case_001', characterId: 'char_hanseoyeon'})
MATCH (ch2:Character {caseId: 'case_001', characterId: 'char_yoonjaeho'})
MATCH (ch3:Character {caseId: 'case_001', characterId: 'char_parkmingyu'})
MATCH (ch4:Character {caseId: 'case_001', characterId: 'char_choiyuna'})

CREATE (q1:Question {
  caseId: 'case_001', questionId: 'q_hanseoyeon_alibi', characterId: 'char_hanseoyeon',
  text: '22:00에 어디 있었나요?',
  answer: '제 방에 있었습니다. 폭풍 때문에 밖으로 나갈 생각도 못 했어요.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q2:Question {
  caseId: 'case_001', questionId: 'q_hanseoyeon_inheritance', characterId: 'char_hanseoyeon',
  text: '상속 문제로 다툰 적 있나요?',
  answer: '말다툼은 있었지만 가족끼리 그럴 수 있잖아요.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q3:Question {
  caseId: 'case_001', questionId: 'q_hanseoyeon_study_entry', characterId: 'char_hanseoyeon',
  text: '22:02 서재 출입 기록을 설명해 주세요.',
  answer: '정확히 기억나지 않습니다.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q4:Question {
  caseId: 'case_001', questionId: 'q_hanseoyeon_wine', characterId: 'char_hanseoyeon',
  text: '서재의 와인잔을 알고 있나요?',
  answer: '와인잔은 제 것이 아닙니다.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q5:Question {
  caseId: 'case_001', questionId: 'q_hanseoyeon_after_pressure', characterId: 'char_hanseoyeon',
  text: '서재에 들어갔다면 무엇을 봤나요?',
  answer: '이미 회장님이 쓰러진 것처럼 보였습니다.',
  initiallyUnlocked: false, unlockCondition: 'con_room_claim_vs_entry_log'
}),
(q6:Question {
  caseId: 'case_001', questionId: 'q_yoonjaeho_discovery', characterId: 'char_yoonjaeho',
  text: '피해자를 언제 발견했나요?',
  answer: '22:10쯤 순찰 중 서재 문이 열려 있는 걸 보고 안을 확인했습니다.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q7:Question {
  caseId: 'case_001', questionId: 'q_yoonjaeho_blackout', characterId: 'char_yoonjaeho',
  text: '정전 당시 무엇을 했나요?',
  answer: '22:05부터 몇 분간 전등이 꺼졌습니다.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q8:Question {
  caseId: 'case_001', questionId: 'q_yoonjaeho_will', characterId: 'char_yoonjaeho',
  text: '유언장 변경 사실을 알고 있었나요?',
  answer: '회장님이 변호사를 부르라고 하신 건 들었습니다.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q9:Question {
  caseId: 'case_001', questionId: 'q_yoonjaeho_key', characterId: 'char_yoonjaeho',
  text: '서재 열쇠 관리는 어떻게 됩니까?',
  answer: '카드키는 가족 포함 발급 가능합니다.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q10:Question {
  caseId: 'case_001', questionId: 'q_parkmingyu_alibi', characterId: 'char_parkmingyu',
  text: '22:00에 어디 있었나요?',
  answer: '손님방에서 의료 기록을 정리하고 있었습니다.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q11:Question {
  caseId: 'case_001', questionId: 'q_parkmingyu_medicine', characterId: 'char_parkmingyu',
  text: '피해자의 약은 언제 확인했나요?',
  answer: '21:30 복용분을 확인했습니다.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q12:Question {
  caseId: 'case_001', questionId: 'q_choiyuna_last_call', characterId: 'char_choiyuna',
  text: '피해자와 마지막으로 연락한 때는?',
  answer: '21:55에 전화를 받았습니다.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q13:Question {
  caseId: 'case_001', questionId: 'q_choiyuna_schedule', characterId: 'char_choiyuna',
  text: '비밀 일정이 있었나요?',
  answer: '내일 변호사와 만날 예정이었습니다.',
  initiallyUnlocked: true, unlockCondition: ''
}),
(q14:Question {
  caseId: 'case_001', questionId: 'q_choiyuna_wine', characterId: 'char_choiyuna',
  text: '서재의 와인잔을 알고 있나요?',
  answer: '저는 와인을 마시지 않았습니다.',
  initiallyUnlocked: true, unlockCondition: ''
})

// Case → Question
CREATE (c)-[:HAS_QUESTION]->(q1), (c)-[:HAS_QUESTION]->(q2),
       (c)-[:HAS_QUESTION]->(q3), (c)-[:HAS_QUESTION]->(q4),
       (c)-[:HAS_QUESTION]->(q5), (c)-[:HAS_QUESTION]->(q6),
       (c)-[:HAS_QUESTION]->(q7), (c)-[:HAS_QUESTION]->(q8),
       (c)-[:HAS_QUESTION]->(q9), (c)-[:HAS_QUESTION]->(q10),
       (c)-[:HAS_QUESTION]->(q11), (c)-[:HAS_QUESTION]->(q12),
       (c)-[:HAS_QUESTION]->(q13), (c)-[:HAS_QUESTION]->(q14)

// Character → Question (HAS_QUESTION)
CREATE (ch1)-[:HAS_QUESTION]->(q1), (ch1)-[:HAS_QUESTION]->(q2),
       (ch1)-[:HAS_QUESTION]->(q3), (ch1)-[:HAS_QUESTION]->(q4),
       (ch1)-[:HAS_QUESTION]->(q5),
       (ch2)-[:HAS_QUESTION]->(q6), (ch2)-[:HAS_QUESTION]->(q7),
       (ch2)-[:HAS_QUESTION]->(q8), (ch2)-[:HAS_QUESTION]->(q9),
       (ch3)-[:HAS_QUESTION]->(q10), (ch3)-[:HAS_QUESTION]->(q11),
       (ch4)-[:HAS_QUESTION]->(q12), (ch4)-[:HAS_QUESTION]->(q13),
       (ch4)-[:HAS_QUESTION]->(q14);

// ── Question → UNLOCKS 관계 ───────────────────────────────────────────────────
// q_hanseoyeon_alibi → st_hanseoyeon_room_2200
MATCH (q:Question {caseId:'case_001',questionId:'q_hanseoyeon_alibi'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_hanseoyeon_room_2200'})
CREATE (q)-[:UNLOCKS]->(s);

MATCH (q:Question {caseId:'case_001',questionId:'q_hanseoyeon_inheritance'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_hanseoyeon_no_reason'})
CREATE (q)-[:UNLOCKS]->(s);

MATCH (q:Question {caseId:'case_001',questionId:'q_hanseoyeon_wine'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_hanseoyeon_wine_deny'})
CREATE (q)-[:UNLOCKS]->(s);

MATCH (q:Question {caseId:'case_001',questionId:'q_hanseoyeon_after_pressure'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_hanseoyeon_pressure'})
CREATE (q)-[:UNLOCKS]->(s);

MATCH (q:Question {caseId:'case_001',questionId:'q_yoonjaeho_discovery'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_yoonjaeho_found_2210'})
CREATE (q)-[:UNLOCKS]->(s);

MATCH (q:Question {caseId:'case_001',questionId:'q_yoonjaeho_blackout'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_yoonjaeho_blackout'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_storm_blackout'})
CREATE (q)-[:UNLOCKS]->(s), (q)-[:UNLOCKS]->(e);

MATCH (q:Question {caseId:'case_001',questionId:'q_yoonjaeho_key'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_yoonjaeho_key_only_victim'})
CREATE (q)-[:UNLOCKS]->(s);

MATCH (q:Question {caseId:'case_001',questionId:'q_parkmingyu_alibi'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_parkmingyu_guestroom_2200'})
CREATE (q)-[:UNLOCKS]->(s);

MATCH (q:Question {caseId:'case_001',questionId:'q_parkmingyu_medicine'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_parkmingyu_medicine'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_medicine_box'})
CREATE (q)-[:UNLOCKS]->(s), (q)-[:UNLOCKS]->(e);

MATCH (q:Question {caseId:'case_001',questionId:'q_choiyuna_last_call'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_choiyuna_call_record'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_phone_call'})
CREATE (q)-[:UNLOCKS]->(s), (q)-[:UNLOCKS]->(e);

MATCH (q:Question {caseId:'case_001',questionId:'q_choiyuna_wine'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_choiyuna_no_wine'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_lipstick_tube'})
CREATE (q)-[:UNLOCKS]->(s), (q)-[:UNLOCKS]->(e);

// ── Contradiction 노드 + 관계 ─────────────────────────────────────────────────
MATCH (c:Case {caseId: 'case_001'})
MATCH (ch1:Character {caseId: 'case_001', characterId: 'char_hanseoyeon'})
MATCH (ch4:Character {caseId: 'case_001', characterId: 'char_choiyuna'})

CREATE (con1:Contradiction {
  caseId: 'case_001', contradictionId: 'con_room_claim_vs_entry_log',
  title: '방에 있었다는 진술과 서재 출입 기록의 충돌',
  message: '한서연의 22:00 방 알리바이는 22:02 서재 출입 기록과 충돌합니다.',
  reasonCode: 'time_location_conflict', severity: 'core', pressureDelta: 40
}),
(con2:Contradiction {
  caseId: 'case_001', contradictionId: 'con_watch_time_manipulated',
  title: '회중시계 시각 조작 의혹',
  message: '정전 시간과 부자연스러운 회중시계 파편은 현장 조작 가능성을 뒷받침합니다.',
  reasonCode: 'scene_manipulation_during_blackout', severity: 'major', pressureDelta: 25
}),
(con3:Contradiction {
  caseId: 'case_001', contradictionId: 'con_inheritance_motive',
  title: '상속 갈등과 찢어진 유언장',
  message: '죽일 이유가 없다는 진술은 상속 비율 변경 흔적이 있는 찢어진 유언장과 충돌합니다.',
  reasonCode: 'inheritance_motive_confirmed', severity: 'core', pressureDelta: 35
}),
(con4:Contradiction {
  caseId: 'case_001', contradictionId: 'con_call_record',
  title: '피해자의 마지막 통화와 비서의 진술',
  message: '통화 기록은 3분 12초의 상세 지시가 있었음을 보여줍니다.',
  reasonCode: 'hidden_will_schedule', severity: 'minor', pressureDelta: 10
}),
(con5:Contradiction {
  caseId: 'case_001', contradictionId: 'con_ring_vs_no_entry',
  title: '현장 발견 반지와 서재 출입 부정',
  message: '한서연의 반지가 피해자 근처에서 발견됐습니다.',
  reasonCode: 'physical_evidence_at_scene', severity: 'major', pressureDelta: 30
}),
(con6:Contradiction {
  caseId: 'case_001', contradictionId: 'con_wine_glass_lipstick',
  title: '와인잔 립스틱과 부인 진술',
  message: '한서연은 와인을 마시지 않았다고 했지만 립스틱 케이스와 와인잔 흔적 색상이 일치합니다.',
  reasonCode: 'physical_trace_contradiction', severity: 'minor', pressureDelta: 15
})

CREATE (c)-[:HAS_CONTRADICTION]->(con1),
       (c)-[:HAS_CONTRADICTION]->(con2),
       (c)-[:HAS_CONTRADICTION]->(con3),
       (c)-[:HAS_CONTRADICTION]->(con4),
       (c)-[:HAS_CONTRADICTION]->(con5),
       (c)-[:HAS_CONTRADICTION]->(con6)

// Contradiction → ABOUT
CREATE (con1)-[:ABOUT]->(ch1),
       (con2)-[:ABOUT]->(ch1),
       (con3)-[:ABOUT]->(ch1),
       (con4)-[:ABOUT]->(ch4),
       (con5)-[:ABOUT]->(ch1),
       (con6)-[:ABOUT]->(ch1);

// Contradiction → REQUIRES_STATEMENT
MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_room_claim_vs_entry_log'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_hanseoyeon_room_2200'})
CREATE (con)-[:REQUIRES_STATEMENT]->(s);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_watch_time_manipulated'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_hanseoyeon_pressure'})
CREATE (con)-[:REQUIRES_STATEMENT]->(s);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_inheritance_motive'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_hanseoyeon_no_reason'})
CREATE (con)-[:REQUIRES_STATEMENT]->(s);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_call_record'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_choiyuna_call_2155'})
CREATE (con)-[:REQUIRES_STATEMENT]->(s);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_ring_vs_no_entry'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_hanseoyeon_ring_missing'})
CREATE (con)-[:REQUIRES_STATEMENT]->(s);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_wine_glass_lipstick'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_hanseoyeon_wine_deny'})
CREATE (con)-[:REQUIRES_STATEMENT]->(s);

// Contradiction → REQUIRES_EVIDENCE
MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_room_claim_vs_entry_log'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_study_entry_log'})
CREATE (con)-[:REQUIRES_EVIDENCE]->(e);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_watch_time_manipulated'})
MATCH (e1:Evidence {caseId:'case_001',evidenceId:'ev_broken_watch'})
MATCH (e2:Evidence {caseId:'case_001',evidenceId:'ev_storm_blackout'})
CREATE (con)-[:REQUIRES_EVIDENCE]->(e1), (con)-[:REQUIRES_EVIDENCE]->(e2);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_inheritance_motive'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_torn_will'})
CREATE (con)-[:REQUIRES_EVIDENCE]->(e);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_call_record'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_phone_call'})
CREATE (con)-[:REQUIRES_EVIDENCE]->(e);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_ring_vs_no_entry'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_ring_near_victim'})
CREATE (con)-[:REQUIRES_EVIDENCE]->(e);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_wine_glass_lipstick'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_lipstick_tube'})
CREATE (con)-[:REQUIRES_EVIDENCE]->(e);

// Contradiction → UNLOCKS
MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_room_claim_vs_entry_log'})
MATCH (s:Statement {caseId:'case_001',statementId:'st_hanseoyeon_pressure'})
MATCH (q:Question {caseId:'case_001',questionId:'q_hanseoyeon_after_pressure'})
MATCH (e1:Evidence {caseId:'case_001',evidenceId:'ev_torn_will'})
MATCH (e2:Evidence {caseId:'case_001',evidenceId:'ev_ring_near_victim'})
CREATE (con)-[:UNLOCKS]->(s), (con)-[:UNLOCKS]->(q),
       (con)-[:UNLOCKS]->(e1), (con)-[:UNLOCKS]->(e2);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_watch_time_manipulated'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_deleted_cctv'})
CREATE (con)-[:UNLOCKS]->(e);

MATCH (con:Contradiction {caseId:'case_001',contradictionId:'con_call_record'})
MATCH (r:Record {caseId:'case_001',recordId:'rec_will_revision_notice'})
CREATE (con)-[:UNLOCKS]->(r);

// ── TimelineEvent 노드 ────────────────────────────────────────────────────────
MATCH (c:Case {caseId: 'case_001'})

CREATE (t1:TimelineEvent {
  caseId: 'case_001', timelineId: 'tl_incident_time',
  time: '22:00~22:10', title: '사망 추정 시간',
  description: '강도준은 이 시간대에 사망한 것으로 추정된다.',
  sourceType: 'evidence', sourceId: 'ev_servant_log', hidden: false
}),
(t2:TimelineEvent {
  caseId: 'case_001', timelineId: 'tl_global_2202_study_entry',
  time: '22:02', title: '한서연 서재 출입 기록',
  description: '보안 시스템에 한서연의 카드키 출입 기록이 남아 있다.',
  sourceType: 'evidence', sourceId: 'ev_study_entry_log', hidden: false
}),
(t3:TimelineEvent {
  caseId: 'case_001', timelineId: 'tl_last_call',
  time: '21:55', title: '마지막 통화',
  description: '피해자가 최윤아에게 전화를 걸어 다음 날 일정을 지시했다.',
  sourceType: 'evidence', sourceId: 'ev_phone_call', hidden: true,
  unlockCondition: 'q_choiyuna_last_call'
}),
(t4:TimelineEvent {
  caseId: 'case_001', timelineId: 'tl_blackout',
  time: '22:05~22:07', title: '저택 2층 정전',
  description: '관리실 로그에 짧은 정전이 기록됐다. CCTV도 꺼졌다.',
  sourceType: 'evidence', sourceId: 'ev_storm_blackout', hidden: true,
  unlockCondition: 'q_yoonjaeho_blackout'
}),
(t5:TimelineEvent {
  caseId: 'case_001', timelineId: 'tl_medicine_check',
  time: '21:30', title: '약 복용 확인',
  description: '피해자의 21:30 복용분이 확인됐다.',
  sourceType: 'evidence', sourceId: 'ev_medicine_box', hidden: true,
  unlockCondition: 'q_parkmingyu_medicine'
})

CREATE (c)-[:HAS_TIMELINE_EVENT]->(t1),
       (c)-[:HAS_TIMELINE_EVENT]->(t2),
       (c)-[:HAS_TIMELINE_EVENT]->(t3),
       (c)-[:HAS_TIMELINE_EVENT]->(t4),
       (c)-[:HAS_TIMELINE_EVENT]->(t5);

// TimelineEvent → SOURCED_FROM
MATCH (t:TimelineEvent {caseId:'case_001',timelineId:'tl_incident_time'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_servant_log'})
CREATE (t)-[:SOURCED_FROM]->(e);

MATCH (t:TimelineEvent {caseId:'case_001',timelineId:'tl_global_2202_study_entry'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_study_entry_log'})
CREATE (t)-[:SOURCED_FROM]->(e);

MATCH (t:TimelineEvent {caseId:'case_001',timelineId:'tl_last_call'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_phone_call'})
CREATE (t)-[:SOURCED_FROM]->(e);

MATCH (t:TimelineEvent {caseId:'case_001',timelineId:'tl_blackout'})
MATCH (e:Evidence {caseId:'case_001',evidenceId:'ev_storm_blackout'})
CREATE (t)-[:SOURCED_FROM]->(e);

// ── Solution 노드 (내부 전용) ─────────────────────────────────────────────────
MATCH (c:Case {caseId: 'case_001'})
CREATE (sol:Solution {
  caseId: 'case_001',
  culpritId: 'char_hanseoyeon',
  motive: '유언장 변경으로 상속이 크게 줄어들 것을 알고, 변경 전 피해자를 제거하려 했다.',
  method: '22:02 서재에 들어가 피해자와 대면했고, 정전 중 현장을 조작했다.',
  requiredContradictionIds: ['con_room_claim_vs_entry_log', 'con_inheritance_motive'],
  requiredEvidenceIds: ['ev_study_entry_log', 'ev_torn_will'],
  requiredStatementIds: ['st_hanseoyeon_room_2200', 'st_hanseoyeon_no_reason']
})
CREATE (c)-[:HAS_SOLUTION]->(sol);

// ── 인물 관계 (IN_RELATION) ───────────────────────────────────────────────────
MATCH (ch1:Character {caseId:'case_001',characterId:'char_hanseoyeon'})
MATCH (ch2:Character {caseId:'case_001',characterId:'char_yoonjaeho'})
MATCH (ch3:Character {caseId:'case_001',characterId:'char_parkmingyu'})
MATCH (ch4:Character {caseId:'case_001',characterId:'char_choiyuna'})

CREATE (ch1)-[:IN_RELATION {
  relationshipId: 'rel_hanseoyeon_inheritance',
  description: '조카이자 상속 후보',
  conflict: '상속 비율 변경으로 강한 갈등이 있었다.',
  initiallyVisible: true
}]->(ch2),
(ch2)-[:IN_RELATION {
  relationshipId: 'rel_yoonjaeho_loyalty',
  description: '30년 집사',
  conflict: '유언장 변경 사실을 숨겼다.',
  initiallyVisible: false
}]->(ch1),
(ch3)-[:IN_RELATION {
  relationshipId: 'rel_parkmingyu_medical',
  description: '15년 주치의',
  conflict: '처방 변경으로 인한 책임 논란 가능성이 있었다.',
  initiallyVisible: true
}]->(ch1),
(ch4)-[:IN_RELATION {
  relationshipId: 'rel_choiyuna_schedule',
  description: '비서 7년',
  conflict: '피해자의 비밀 일정을 관리하며 한서연에게 알리지 말라는 지시를 받았다.',
  initiallyVisible: false
}]->(ch1);

// ── Record 노드 ───────────────────────────────────────────────────────────────
MATCH (c:Case {caseId: 'case_001'})
CREATE (r1:Record {
  caseId: 'case_001', recordId: 'rec_opening_report',
  name: '초동 수사 보고',
  description: '외부 침입 흔적 없음. 서재 내부에서 충돌 흔적 발견.',
  timeWindow: '22:10', initiallyVisible: true
}),
(r2:Record {
  caseId: 'case_001', recordId: 'rec_hallway_patrol',
  name: '2층 복도 순찰 기록',
  description: '윤재호는 22:10에 서재 앞 복도에서 열린 서재 문을 발견했다.',
  timeWindow: '22:10', initiallyVisible: true
}),
(r3:Record {
  caseId: 'case_001', recordId: 'rec_will_revision_notice',
  name: '유언장 변경 예약 기록',
  description: '피해자는 사건 다음 날 변호사를 만나 유언장 변경 확정 예정. 한서연 상속 대폭 축소.',
  timeWindow: '사건 다음 날', initiallyVisible: false
}),
(r4:Record {
  caseId: 'case_001', recordId: 'rec_ring_ownership',
  name: '반지 소유자 확인 기록',
  description: '현장에서 발견된 반지는 한서연이 평소 착용하던 것으로 확인됐다.',
  timeWindow: '사건 이후', initiallyVisible: false
})
CREATE (c)-[:HAS_RECORD]->(r1),
       (c)-[:HAS_RECORD]->(r2),
       (c)-[:HAS_RECORD]->(r3),
       (c)-[:HAS_RECORD]->(r4);

// ── 인덱스 ────────────────────────────────────────────────────────────────────
CREATE INDEX case_id_idx IF NOT EXISTS FOR (n:Case) ON (n.caseId);
CREATE INDEX character_id_idx IF NOT EXISTS FOR (n:Character) ON (n.caseId, n.characterId);
CREATE INDEX evidence_id_idx IF NOT EXISTS FOR (n:Evidence) ON (n.caseId, n.evidenceId);
CREATE INDEX statement_id_idx IF NOT EXISTS FOR (n:Statement) ON (n.caseId, n.statementId);
CREATE INDEX contradiction_id_idx IF NOT EXISTS FOR (n:Contradiction) ON (n.caseId, n.contradictionId);
CREATE INDEX question_id_idx IF NOT EXISTS FOR (n:Question) ON (n.caseId, n.questionId);
CREATE INDEX timeline_id_idx IF NOT EXISTS FOR (n:TimelineEvent) ON (n.caseId, n.timelineId);
