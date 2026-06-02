# Editor Gate

편집자는 “재밌는 추리 게임이 되는가”를 승인한다. 문장이 예쁘거나 설정이 복잡한 것만으로 승인하지 않는다.

## 1. Game Fun Rubric

각 항목 0~3점. 2점 미만 항목이 있으면 `revise`, 핵심 항목 0점이면 `blocked`.

| 항목 | 0 | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| 교차증언 유기성 | 용의자들이 서로 무관 | 일부만 연결 | 대부분 연결 | 모든 주요 증언이 다른 증언/증거를 흔듦 |
| 증거 풀이 흥미 | 증거 하나로 정답 | 단순 대조 | 단계적 대조 | 증거+증언+시간축 조합으로 발견감 있음 |
| 범인 방어 전략 | 바로 들킴/무논리 | 얕은 변명 | 단계별 방어 | 압박도별 설득력 있는 방어와 붕괴 |
| 무고한 용의자 역할 | 장식 | 단순 용의선상 | false lead 있음 | innocent secret이 핵심 추론을 우회적으로 도움 |
| 스토리 상승곡선 | 평면적 | 일부 reveal만 있음 | act 진행 명확 | 감정/논리 압박이 함께 상승 |
| 공정한 난이도 | 찍기/불가능 | 단서 부족 | 추론 가능 | 어렵지만 되짚으면 납득 가능 |
| 런타임 구조성 | DB화 어려움 | ID/게이트 부족 | 대부분 구조화 | 바로 JSON/Graph/SQL 컴파일 가능 |

승인 기준:
- 총점 15점 이상
- 교차증언 유기성, 증거 풀이, 범인 방어 전략이 각각 2점 이상
- blocker issue 0개

## 2. Required Matrices

### Suspect Usefulness Matrix

| suspectId | self-alibi claim | helps expose whom | exposed by whom/evidence | innocent secret/false lead | pressure reveal |
| --- | --- | --- | --- | --- | --- |

편집자 체크:
- 모든 용의자가 “누군가를 밝히거나, 누군가에게 밝혀지는” 연결을 가져야 한다.
- 범인만 많은 정보를 갖고 나머지가 빈칸이면 revise.

### Contradiction Route Matrix

| contradictionId | player compares | required statement | required evidence/timeline | unlocks | fun note |
| --- | --- | --- | --- | --- | --- |

편집자 체크:
- 핵심 contradiction은 단서 발견 → 질문 → 반박 → 해금 흐름이 있어야 한다.
- 너무 직접적인 증거명/설명은 revise.

### Culprit Defense Arc

| pressure | defense mode | what they admit | what they deny | misdirection | break trigger |
| --- | --- | --- | --- | --- | --- |
| low | calm denial | harmless public fact | presence/motive | blame circumstance | first objective record |
| medium | explain away | partial contact | intent/opportunity | point to false lead | cross-suspect testimony |
| high | counterattack | inconsistency | method | attack evidence reliability | physical evidence |
| critical | collapse | public contradiction | final truth until accusation | emotional appeal | required contradiction set |

## 3. Editor Output Schema

```yaml
editorDecision: approved|revise|blocked
score:
  crossTestimony: 0
  evidencePuzzle: 0
  culpritDefense: 0
  innocentSuspects: 0
  storyFlow: 0
  fairDifficulty: 0
  runtimeStructure: 0
blockingIssues: []
requiredRevisions:
  - id: rev_001
    severity: blocker|high|medium|low
    target: writer|cross_checker
    issue: ...
    requiredChange: ...
acceptanceCheck: ...
assetGate:
  allowed: false
  reason: editor not approved yet
```

## 4. Asset Gate

Editor가 `approved`를 내리기 전까지:
- 이미지 생성 금지
- asset prompt 초안 작성은 가능
- 캐릭터 수/압박도/증거 목록 확정 금지

Editor 승인 후:
- asset manifest freeze
- 생성 prompt lint
- provider 실행
- 파일명/ID를 case JSON visualProfiles와 연결
