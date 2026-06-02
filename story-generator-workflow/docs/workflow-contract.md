# Workflow Contract

## 1. Agent Roles

### Writer
역할: 원천 스토리를 게임 가능한 사건 설계로 변환한다.

Writer 산출물:
- public premise
- hidden truth
- culprit method/motive/opportunity
- suspect roster
- global truth timeline
- per-character claimed/perceived/private timelines
- evidence list
- statements/questions
- contradiction graph
- clue paths
- pressure defense plan
- asset seeds

Writer 금지:
- 편집자 승인 없이 에셋 생성
- 단일 직선 추리만 설계
- 범인 외 용의자를 장식용으로 배치
- hidden truth를 public statement에 섞기

### Cross-check Writer
역할: 작가 산출물을 공격적으로 깨 본다.

검토 축:
- 시간축 모순: 모든 인물의 위치/행동이 동시에 성립 가능한가?
- 증거-진술 링크: 각 증거가 어떤 진술을 흔드는지 명확한가?
- 교차증언 유기성: A의 말이 B의 알리바이/동기/기회를 드러내는가?
- 범인 방어 논리: 범인이 초반/중반/후반 압박에서 그럴듯하게 변호하는가?
- red herring 공정성: 무고한 인물의 수상함이 억지가 아닌가?
- 추리 난이도: 플레이어가 추론 가능한 단서가 충분히 공개되는가?

Cross-check 산출물:
- blocking issues
- suggested fixes
- contradiction-route coverage table
- suspect usefulness matrix
- public/private leakage risks

### Editor
역할: 승인 게이트. 편집자가 허용할 때까지 Writer는 수정한다.

편집자 판단 기준:
1. 게임성
   - 다른 용의자의 증언이 특정 용의자의 범행을 밝히는 데 유기적으로 도움이 되는가?
   - 증거 풀이가 “증거 하나 = 정답”이 아니라 비교/대조/압박으로 흥미롭게 구성되는가?
   - 플레이어가 어떤 질문을 해야 할지 act/objective/clue path가 자연스럽게 안내하는가?
   - 핵심 단서와 보조 단서, false lead, innocent secret의 역할이 분리되어 있는가?
2. 스토리 흐름
   - opening hook → 알리바이 수집 → 첫 모순 → 동기/기회 압박 → 최종 고발 흐름이 자연스러운가?
   - reveal 순서가 감정적/논리적 상승곡선을 만드는가?
   - 용의자 압박도 변화가 대화 톤과 방어 전략에 반영되는가?
3. 성립성
   - 범행 수법, 시간, 장소, 증거가 물리적으로 성립하는가?
   - 공개 정보만으로 플레이어가 결론에 도달 가능한가?
   - hidden truth 없이도 AI 캐릭터가 답할 public knowledge pack이 충분한가?
4. 런타임 적합성
   - stable ID, visibility gate, unlock condition, contradiction IDs가 DB로 컴파일 가능한가?
   - FE/AI/BE 공개 경계가 지켜지는가?
   - Asset manifest가 UI 상태와 연결 가능한가?

승인 상태:
- `approved`: DB/Asset 생성 진행 가능
- `revise`: Writer가 수정 후 재제출
- `blocked`: 원천 설계 자체 재구성 필요

## 2. Iteration Loop

```text
DRAFT_0 by Writer
  -> REVIEW_0 by Cross-check Writer
  -> EDIT_0 by Editor
  -> if approved: compile
  -> else Writer applies required changes and creates DRAFT_1
```

루프 종료 조건:
- Editor `approved=true`
- no blocker issues
- all required matrices pass minimum thresholds
- public/private lint pass

## 3. Minimum Quality Thresholds

- suspects: 4 recommended for MVP, minimum 3
- each suspect: at least 3 public claims + 1 pressure reveal + 1 relationship/knowledge edge
- culprit: at least 3-stage defense arc (deny → explain away → partial concession → collapse)
- contradictions: minimum 4, with at least 2 cross-suspect dependencies
- evidence: minimum 8, at least 4 initially visible, at least 3 unlockable
- acts: minimum 4 (opening/alibi, first break, motive/opportunity, final accusation)
- asset states: background + each suspect low/medium/high/critical + evidence thumbnails
