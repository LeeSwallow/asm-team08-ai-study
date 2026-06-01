# Senario Schema

## ID 규칙

| 대상 | Prefix | 예시 |
| --- | --- | --- |
| Scene | `scene_` | `scene_001` |
| Character | `char_` | `char_hanseoyeon` |
| Victim | `victim_` | `victim_kangdojun` |
| Evidence | `ev_` | `ev_broken_watch` |
| Statement | `st_` | `st_hanseoyeon_room_2200` |
| Timeline Event | `tl_` | `tl_hanseoyeon_2202_study` |
| Relationship | `rel_` | `rel_hanseoyeon_victim_inheritance` |
| Contradiction | `con_` | `con_room_claim_vs_entry_log` |
| Note | `note_` | `note_player_entry_log_question` |
| Contradiction Candidate | `cand_` | `cand_con_room_claim_vs_entry_log` |
| Fact | `fact_` | `fact_hanseoyeon_claim_room_2200` |
| Rumor | `rumor_` | `rumor_will_revision` |
| Chain | `chain_` | `chain_hanseoyeon_opportunity` |

## CaseWiki / Knowledge Graph 원칙

> 상세 canonical authoring model은 `../story-knowledge-wiki-contract.md`를 기준으로 한다. 이 모델은 규칙을 계속 추가하는 대신, 캐릭터가 말할 수 있는 지식과 사회적 맥락을 풍부하게 만드는 다음 품질 마일스톤이다.

규칙:
- rules/checks는 guardrail이다. 대화 content engine은 fact/evidence/relationship/timeline/case detail wiki projection이어야 한다.
- BE는 wiki page를 검증/컴파일하여 per-session/per-character `CharacterKnowledgePack`으로 projection한다.
- AI는 공개 projection만 받는다. raw hidden truth, private timeline, culprit/finalDiscovery, solution-only authoring note는 금지다.
- BE/EventProcessor는 visibility, unlock, final contradiction/discovery, TensionPolicy, persistence, SSE 권한을 유지한다.

### Fact page 필드

| 필드 | 설명 | 필수 |
| --- | --- | --- |
| `factId` / `id` | `fact_` ID | Yes |
| `truthStatus` | `observed`, `claimed`, `rumor`, `inferred_public`, `misbelief`, `hidden_truth`, `red_herring` | Yes |
| `summary` | 사실/주장 요약 | Yes |
| `knownBy` / `unknownBy` / `misledBy` / `liedAboutBy` / `doubtedBy` | 캐릭터별 지식 경계 | Yes |
| `confidenceDefault` | 기본 신뢰도 | Yes |
| `sourceRefs` | 근거 ID | Yes |
| `visibilityGate` | 공개/해금 조건 | Yes |

### Character knowledge 필드

| 필드 | 설명 | 필수 |
| --- | --- | --- |
| `witnessedFacts` | 직접 목격/청취한 fact IDs | No |
| `heardFacts` | 소문/전언 fact IDs | No |
| `believedFacts` | 믿고 있는 fact IDs | No |
| `doubtedFacts` | 의심하는 fact IDs | No |
| `hiddenFacts` | 알고 있지만 공개 금지인 fact IDs | No |
| `unknownFacts` | 모르는 fact IDs | No |
| `misbelievedFacts` | 잘못 믿는 fact IDs | No |
| `trust/suspicion/fear/debt/jealousy/conflict` | 관계/정서 점수 | No |
| `pressureRevealConditions` | 압박/모순 후 공개 가능한 hint gate | No |

## Scene 필드

| 필드 | 설명 | 필수 |
| --- | --- | --- |
| `sceneId` | Scene 고유 ID | Yes |
| `title` | Scene 제목 | Yes |
| `summary` | 플레이어에게 공개되는 사건 개요 | Yes |
| `victimId` | 피해자 ID | Yes |
| `incidentTime` | 사건 발생 추정 시각 | Yes |
| `incidentLocation` | 사건 발생 장소 | Yes |
| `questionLimit` | 질문 가능 횟수 | Yes |
| `initialEvidenceIds` | 시작 시 공개 증거 ID 목록 | Yes |
| `solution` | 범인, 동기, 수단, 필수 모순 | Yes |

## Character 필드

| 필드 | 설명 | 필수 |
| --- | --- | --- |
| `characterId` | 인물 고유 ID | Yes |
| `name` | 표시 이름 | Yes |
| `role` | 피해자와의 역할 또는 직업 | Yes |
| `publicProfile` | 플레이어에게 공개되는 설명 | Yes |
| `secret` | 숨기는 정보 | No |
| `motiveCandidate` | 동기 후보 여부 | Yes |
| `isCulprit` | 실제 범인 여부 | Yes |

## Evidence 필드

| 필드 | 설명 | 필수 |
| --- | --- | --- |
| `evidenceId` | 증거 고유 ID | Yes |
| `name` | 증거 이름 | Yes |
| `type` | `physical`, `record`, `testimony`, `relationship`, `digital` | Yes |
| `description` | 플레이어에게 표시되는 설명 | Yes |
| `foundAt` | 발견 장소 또는 출처 | Yes |
| `timeWindow` | 관련 시간대 | No |
| `reliability` | 0.0~1.0 신뢰도 | Yes |
| `initiallyVisible` | 시작 시 공개 여부 | Yes |
| `unlockCondition` | 해금 조건 | No |
| `assetId` | 증거 카드/상세용 시각 asset ID | No |
| `assetPath` | 증거 카드/상세용 asset 경로 | No |
| `sourceRefs` | 관련 statement/record/timeline/contradiction ID 목록 | No |

## Timeline 필드

> 현재 이 섹션의 기존 per-character `actual` 중심 형태만으로는 MVP 목표에 부족하다. 공개/비공개 경계가 없고, BE public payload/AI prompt에서 무엇을 노출해도 되는지 판단할 수 없기 때문이다. Target schema는 아래처럼 global `storyline.timeline[]`과 first-class `characterTimelines[]`를 분리한다. 상세 표준은 `../story-data-contract.md`를 기준으로 한다.

### Global storyline.timeline[]

| 필드 | 설명 | 필수 | 공개 여부 |
| --- | --- | --- | --- |
| `timelineId` | 전역 타임라인 이벤트 ID (`tl_`) | Yes | 공개 가능 |
| `time` | 시각 또는 구간 | Yes | 공개 가능 |
| `title` | 표시 제목 | Yes | 공개 가능 |
| `description` | 공개 가능한 설명 | Yes | 공개 가능, hidden이면 금지 |
| `sourceType` | `evidence`, `record`, `statement`, `inference` | Yes | 공개 가능 |
| `sourceId` | 근거 ID | Yes | 공개 가능 |
| `unlockCondition` | 공개 조건 ID/규칙 | No | BE 내부 판단용 |
| `hidden` | true면 public session/dialogue/FE diagnostics 노출 금지 | No | public 금지 |

### characterTimelines[]

| 필드 | 설명 | 필수 | 공개 여부 |
| --- | --- | --- | --- |
| `timelineId` | 캐릭터 타임라인 ID (`ct_`) | Yes | 공개 가능 |
| `suspectId` | 인물 ID (`char_`) | Yes | 공개 가능 |
| `publicPersona` | 공개 가능한 성격/태도 요약 | Yes | 공개 가능 |
| `privateMotive` | 숨은 동기/사적 이유 | No | public/revealAllowed=false 금지 |
| `publicEvents[]` | 공개/해금 가능한 캐릭터별 사건 | Yes | 조건 충족 시 공개 |
| `privateEvents[]` | 실제 행적/숨은 진실/엔딩용 사건 | No | public/revealAllowed=false 금지 |
| `contradictionSeeds[]` | 모순 후보를 만들 안정 ID 연결 | No | publicPrompt만 공개 가능 |

### characterTimelines[].publicEvents[]

| 필드 | 설명 | 필수 | 공개 여부 |
| --- | --- | --- | --- |
| `timelineId` | 캐릭터 이벤트 ID (`ctl_`) | Yes | 공개 가능 |
| `time` | 시각/구간 | Yes | 공개 가능 |
| `title` | 표시 제목 | Yes | 공개 가능 |
| `summary` | 공개 가능한 요약 | Yes | 공개 가능 |
| `location` | 공개 가능한 위치 | No | 공개 가능 |
| `claimedLocation` | 인물이 주장한 위치 | No | 공개 가능 |
| `claimedAction` | 인물이 주장한 행동 | No | 공개 가능 |
| `sourceType` | `statement`, `evidence`, `record`, `inference` | Yes | 공개 가능 |
| `sourceId` | 근거 ID | Yes | 공개 가능 |
| `relatedEvidenceIds` | 관련 증거 ID 목록 | No | 공개 가능 |
| `relatedStatementIds` | 관련 진술 ID 목록 | No | 공개 가능 |
| `relatedQuestionIds` | 관련 질문 ID 목록 | No | 공개 가능 |
| `relatedContradictionIds` | 관련 모순 ID 목록 | No | 공개 가능 |
| `unlockCondition` | 공개 조건 | No | BE 내부 판단용 |
| `revealCondition` | 공개/해금 조건 | No | BE 내부 판단용 |
| `visibility` | `public` | Yes | 공개 가능 |

### characterTimelines[].privateEvents[]

| 필드 | 설명 | 필수 | 공개 여부 |
| --- | --- | --- | --- |
| `timelineId` | private 캐릭터 이벤트 ID (`ctl_`) | Yes | ID도 public payload에서 제거 권장 |
| `time` | 시각/구간 | Yes | revealAllowed=true 이전 금지 |
| `actualLocation` | 실제 위치 | No | public/revealAllowed=false 금지 |
| `actualAction` | 실제 행동 | No | public/revealAllowed=false 금지 |
| `privateNote` | 작성자/정답용 메모 | No | public 금지 |
| `sourceType` | `solution`, `inference`, etc. | Yes | public 금지 |
| `sourceId` | private source ID | Yes | public 금지 |
| `visibility` | `private` | Yes | public 금지 |
| `revealCondition` | 엔딩/최종 공개 조건 | No | BE 내부 판단용 |

### persona / speechStyle / tensionProfile

| 필드 | 설명 | 필수 | 공개 여부 |
| --- | --- | --- | --- |
| `persona.publicPersona` | AI/FE가 사용할 공개 성격 요약 | Yes | 공개 가능 |
| `persona.publicMask` | 겉으로 보이는 역할/태도 | No | 공개 가능 |
| `persona.privateMotive` | 숨은 동기 | No | public/revealAllowed=false 금지 |
| `persona.secret` | 숨은 진실 | No | public 금지 |
| `speechStyle.register` | 존댓말/반말/격식 | Yes | 공개 가능 |
| `speechStyle.baseTone` | 기본 말투 | Yes | 공개 가능 |
| `speechStyle.low|medium|high|critical` | tension별 말투 변형 | Yes | 공개 가능 |
| `tensionProfile.thresholds[]` | pressure -> tension/emotion/expression 매핑 | Yes | 공개 가능 |
| `tensionProfile.triggers[]` | contradiction/event별 pressure 변화 | No | BE 적용 후 결과만 공개 |
| `personaVariants` | baseline/calm/defensive/pressed/nervous/broken/angry 등 tension별 공개 persona overlay | Yes | 공개 가능 |
| `activePersonaOverlay` | 현재 session/tension/recentDialogue에 따라 선택된 overlay | Runtime | 공개 가능 |

규칙:
- `suspect.tensionLevel` canonical type은 `low|medium|high|critical` label이다.
- numeric intensity는 `pressure` 또는 optional `tensionScore`를 사용한다.
- AI는 `allowedStatement`가 새 사실의 기준이며, `publicTimeline`/`visibleFacts`는 stable ID로 허용된 경우에만 factual grounding에 사용한다.
- FE character asset은 canonical expression enum(`neutral,wary,defensive,angry,anxious,shocked,breakdown,confident_lying,sad,focused`)에 매핑되어야 하며, 최소 neutral fallback이 필요하다.
- `tensionProfile.triggers[]`는 BE TensionPolicy 입력이다. AI/GameMasterAgent가 `TENSION_CHANGED`를 제안하거나 적용하면 안 된다.
- tension은 새로 검증된 evidence + testimony/alibi contradiction 발견 시에만 상승한다. generic dialogue, unlock-only event, replay/re-ask, duplicate contradiction, AI degraded/failure는 tension을 올리지 않는다.
- `personaVariants` / `activePersonaOverlay` / `CharacterKnowledgePack` / 3-Agent input-output schema의 상세 canonical 기준은 `../story-agent-contract.md`를 따른다.

## Contradiction 필드

| 필드 | 설명 | 필수 |
| --- | --- | --- |
| `contradictionId` | 모순 ID | Yes |
| `title` | 모순 제목 | Yes |
| `relatedCharacterId` | 관련 인물 ID | Yes |
| `requiredStatementIds` | 필요한 진술 ID 목록 | Yes |
| `requiredEvidenceIds` | 필요한 증거 ID 목록 | Yes |
| `severity` | `minor`, `major`, `core` | Yes |
| `result` | 정답 판정 시 해금되는 정보 | Yes |
| `timelineIds` | 관련 public timeline/character timeline ID 목록 | No |
| `status` | `hidden`, `candidate`, `discovered`, `resolved` | No |
| `displayText` | public UI에 표시 가능한 설명 | No |

## Investigation read model 필드

> Runtime public API는 아래 read model을 session/dialogue response에 포함해야 한다. 자세한 canonical shape는 `../story-data-contract.md`와 `../service-contract-dialogue-story.md`를 기준으로 한다.

### caseFile

| 필드 | 설명 | 필수 |
| --- | --- | --- |
| `caseId` | 사건 ID | Yes |
| `title` | 사건 제목 | Yes |
| `opening` | 도입/목표/규칙 | Yes |
| `publicPremise` | 공개 전제 | Yes |
| `currentActId` | 현재 act ID | Yes |
| `currentObjective` | 현재 목표 | Yes |
| `visibleTimeline` | 공개/해금된 전역 타임라인 | Yes |

### relationMap

| 필드 | 설명 | 필수 |
| --- | --- | --- |
| `centerCharacterId` | 관계도 중심 인물 ID | Yes |
| `nodes[]` | suspect/victim/other node 목록 | Yes |
| `edges[]` | relationship edge 목록 | Yes |
| `nodes[].id` | character/victim/other ID | Yes |
| `edges[].id` | `rel_` ID | Yes |
| `edges[].from` / `edges[].to` | 연결 대상 ID | Yes |
| `edges[].label` | 관계 라벨 | Yes |
| `edges[].description` | 공개 가능한 관계 설명 | No |
| `edges[].evidenceIds` / `statementIds` | 관련 공개 근거 ID | No |

### notebook / notes

| 필드 | 설명 | 필수 |
| --- | --- | --- |
| `notebook.caseFile` | 사건 파일 read model | Yes |
| `notebook.evidence` | 공개 증거 목록 | Yes |
| `notebook.records` | 공개 기록 목록 | Yes |
| `notebook.statements` | 공개 진술 목록 | Yes |
| `notebook.statementsBySuspect` | suspect별 진술 그룹 | Yes |
| `notebook.questionsBySuspect` | suspect별 질문 그룹 | Yes |
| `notebook.relations` / `relationMap` | 관계 read model | Yes |
| `notebook.contradictions` | 후보/발견 모순 read model | Yes |
| `notebook.bookmarks` | BE 검증 bookmark 목록 | No |
| `notebook.notes` | BE-persisted note 목록 | Yes |
| `notes[].noteId` | note ID (`note_`) | Yes |
| `notes[].text` | note 본문 | Yes |
| `notes[].linkedEvidenceIds` | 연결 증거 ID | No |
| `notes[].linkedStatementIds` | 연결 진술 ID | No |
| `notes[].linkedRecordIds` | 연결 기록 ID | No |
| `notes[].linkedContradictionIds` | 연결 모순 ID | No |
| `notes[].linkedSuspectIds` | 연결 인물 ID | No |

규칙:
- FE `사건 파일`, `증거 목록`, `인물 관계도`, `메모`, `모순` UI는 이 read model 또는 notes endpoint/SSE를 기준으로 동작해야 한다.
- contradiction submit은 player-selected `statementIds[]` + `evidenceIds[]`를 BE에 보내야 하며, FE가 숨은 정답 ID를 로컬에서 자동 선택하면 안 된다.
