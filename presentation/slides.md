---
theme: default
canvasWidth: 1920
title: 알리바이 교차검증형 추리 게임
info: |
  AI 자연어 심문과 증거 기반 판정을 결합한 웹 추리 게임 MVP 발표자료
class: text-left
highlighter: shiki
transition: fade-out
mdc: true
fonts:
  sans: Pretendard, Inter, Noto Sans KR
  mono: JetBrains Mono, Fira Code
---

<section class="hero slide-fill">
  <div class="kicker">AI NARRATIVE DETECTIVE GAME</div>
  <h1>진실은,<br/>서로의 말 속에 있다</h1>
  <p class="lead">플레이어가 직접 질문하고, 증거와 진술을 교차검증해 알리바이의 균열을 찾아내는 자연어 추리 시뮬레이션</p>
  <div class="hero-grid">
    <div><b>플레이 방식</b><span>자연어 심문 + 증거 제시</span></div>
    <div><b>MVP 사건</b><span>폭풍우 치던 밤, 저택 서재 살인</span></div>
    <div><b>핵심 재미</b><span>말의 모순을 직접 찾아내는 쾌감</span></div>
  </div>
</section>

---

<section class="slide-fill two-col problem">
  <div>
    <p class="eyebrow">WHY NOW</p>
    <h2>추리게임은 자유롭고 싶지만,<br/>AI 게임은 쉽게 무너진다</h2>
  </div>
  <div class="stack">
    <article class="pain">
      <span>01</span>
      <h3>선택지형 추리의 한계</h3>
      <p>정해진 버튼을 순서대로 누르면 “내가 추론했다”는 감각보다 정답 루트를 따라간 느낌이 강해진다.</p>
    </article>
    <article class="pain red">
      <span>02</span>
      <h3>자유 채팅형 AI의 리스크</h3>
      <p>대화는 자유롭지만 정답 누설, 설정 붕괴, 사건 일관성 훼손이 발생하면 게임성이 사라진다.</p>
    </article>
    <article class="pain">
      <span>03</span>
      <h3>우리가 푸는 문제</h3>
      <p>플레이어에게는 자유로운 심문을, 내부에는 구조화된 사건 상태와 검증 가능한 판정을 제공한다.</p>
    </article>
  </div>
</section>

---

<section class="slide-fill solution">
  <p class="eyebrow">PRODUCT WEDGE</p>
  <h2>AI에게 사건을 맡기지 않는다.<br/>AI와 함께 추리를 플레이하게 만든다.</h2>
  <div class="triad">
    <div>
      <strong>Natural Language</strong>
      <h3>직접 묻는 심문</h3>
      <p>“22시에 어디 있었나요?”처럼 플레이어가 직접 질문을 설계한다.</p>
    </div>
    <div>
      <strong>Case Graph</strong>
      <h3>사건 상태 기반 진행</h3>
      <p>증거, 진술, 관계, 타임라인이 백엔드 상태로 관리된다.</p>
    </div>
    <div>
      <strong>Validated Events</strong>
      <h3>검증된 해금과 판정</h3>
      <p>AI 제안은 룰/이벤트 검증을 통과해야 UI 상태로 반영된다.</p>
    </div>
  </div>
  <div class="quote">“자유 입력의 몰입감”과 “추리 게임의 정답 가능성”을 동시에 잡는 구조</div>
</section>

---

<section class="slide-fill casefile">
  <div class="case-title">
    <p class="eyebrow">CASE 001</p>
    <h2>폭풍우 치던 밤,<br/>저택 2층 서재에서 벌어진 죽음</h2>
    <p>피해자 강도준은 22:10경 서재에서 쓰러진 채 발견됐다. 외부 침입 흔적은 없다. 네 명의 용의자는 각자 다른 알리바이를 주장한다.</p>
  </div>
  <div class="suspect-board">
    <div class="portrait active"><b>한서연</b><span>조카 · 상속 갈등</span></div>
    <div class="portrait"><b>윤재호</b><span>집사 · 최초 발견자</span></div>
    <div class="portrait"><b>박민규</b><span>주치의 · 처방 갈등</span></div>
    <div class="portrait"><b>최윤아</b><span>비서 · 비밀 일정</span></div>
  </div>
  <div class="evidence-strip">
    <span>깨진 회중시계</span><span>와인잔</span><span>서재 출입 기록</span><span>찢어진 유언장</span><span>정전 기록</span>
  </div>
</section>

---

<section class="slide-fill loop">
  <p class="eyebrow">CORE LOOP</p>
  <h2>질문 → 진술 → 증거 대조 → 모순 제기 → 압박/해금</h2>
  <div class="loop-line">
    <div><span>1</span><b>질문 설계</b><p>제한된 12회의 질문 안에서 누구에게 무엇을 물을지 선택</p></div>
    <div><span>2</span><b>캐릭터 답변</b><p>성격, 긴장도, 공개 가능한 정보에 맞춘 자연스러운 응답</p></div>
    <div><span>3</span><b>증거 연결</b><p>진술 카드와 증거/기록/관계도를 비교</p></div>
    <div><span>4</span><b>모순 제출</b><p>진술 A + 증거 B 조합으로 알리바이 균열 제기</p></div>
    <div><span>5</span><b>새 정보 해금</b><p>압박 상승, 추가 진술, 숨겨진 증거 공개</p></div>
  </div>
  <div class="sample-dialogue">
    <b>플레이어</b> “22시에 방에 있었다고 했죠. 그런데 출입 기록에는 22:02에 서재에 들어간 것으로 남아 있습니다.”
    <em>→ 한서연 압박 상승 / 추가 진술 해금</em>
  </div>
</section>

---

<section class="slide-fill ui-slide">
  <p class="eyebrow">PLAYER SURFACE</p>
  <h2>한 화면에서 심문, 증거, 관계, 판정이 연결되는 수사 데스크</h2>
  <div class="mock-ui">
    <aside>
      <h4>용의자</h4>
      <div class="mini-card hot">한서연 <small>심문 진행 중</small></div>
      <div class="mini-card">윤재호</div>
      <div class="mini-card">박민규</div>
      <div class="mini-card">최윤아</div>
    </aside>
    <main>
      <div class="scene">
        <div class="rain"></div>
        <div class="char-silhouette"></div>
        <div class="bubble">“저는 그 시간에 제 방에 있었어요. 서재에는 가지 않았습니다.”</div>
      </div>
      <div class="inputbar">상속 문제로 다툰 뒤 어디로 갔나요? <button>전송</button></div>
    </main>
    <aside>
      <h4>증거</h4>
      <div class="evidence-grid"><i></i><i></i><i></i><i></i><i class="locked"></i><i></i></div>
      <h4>모순 사항</h4>
      <div class="contradiction">방에 있었다는 진술 ↔ 22:02 서재 출입 기록</div>
    </aside>
  </div>
</section>

---

<section class="slide-fill architecture">
  <p class="eyebrow">SYSTEM DESIGN</p>
  <h2>생성 AI는 말하고, 백엔드는 진실을 지킨다</h2>
  <div class="pipeline">
    <div><b>사용자 입력</b><span>자연어 질문</span></div>
    <div><b>Character Agent</b><span>인물별 말투/방어 논리</span></div>
    <div><b>Light Rule Check</b><span>정답 누설·설정 붕괴 방지</span></div>
    <div><b>GameMaster Agent</b><span>노트/단서 이벤트 제안</span></div>
    <div><b>BE Event Processor</b><span>검증 후 SSE 발행</span></div>
  </div>
  <div class="guardrails three">
    <article><b>복합 모델 파이프라인</b><p>단일 챗봇이 아니라 캐릭터 반응 판단, 답변 생성, 룰 검증, 이벤트 제안, 상태 반영이 분리된 다층 구조다.</p></article>
    <article><b>치밀한 Routing 조건 분기</b><p>반복 질문, 증거 제시, 모순 제기, 압박 상승, 해금 가능성에 따라 다음 노드와 응답 전략을 다르게 선택한다.</p></article>
    <article><b>State Authority</b><p>AI가 UI 상태를 직접 바꾸지 않고, 백엔드 검증 이벤트만 상태를 변경한다.</p></article>
  </div>
</section>

---

<section class="slide-fill routing">
  <p class="eyebrow">AI ROUTING DETAIL</p>
  <h2>모델은 단순 답변 생성기가 아니라,<br/>상황별 조건 분기로 움직이는 심문 엔진</h2>
  <div class="routing-grid">
    <article><span>Intent</span><b>질문 의도 판별</b><p>알리바이 확인, 관계 추궁, 증거 제시, 모순 제기, 반복 질문을 먼저 구분한다.</p></article>
    <article><span>State</span><b>사건 상태 확인</b><p>현재 공개된 증거, 용의자 압박도, 이전 진술, 해금 조건을 함께 본다.</p></article>
    <article><span>Route</span><b>조건별 노드 분기</b><p>방어/회피/부분 인정/추가 진술/힌트 제안 등 다음 처리 경로를 선택한다.</p></article>
    <article><span>Validate</span><b>응답 검증</b><p>정답 누설, 비공개 사실 노출, 캐릭터 말투 붕괴를 Light Rule Check로 걸러낸다.</p></article>
    <article><span>Event</span><b>해금 이벤트 제안</b><p>압박 상승이나 모순 성공이 확인되면 노트, 증거, 관계도 업데이트 후보를 만든다.</p></article>
    <article><span>Commit</span><b>백엔드 상태 반영</b><p>Event Processor가 검증한 이벤트만 SSE로 UI에 반영한다.</p></article>
  </div>
</section>

---

<section class="slide-fill differentiation">
  <p class="eyebrow">DIFFERENTIATION</p>
  <h2>기존 추리게임과 AI 채팅 사이의 빈 공간</h2>
  <table>
    <thead><tr><th>구분</th><th>기존 선택지 추리</th><th>일반 AI 채팅</th><th>우리 게임</th></tr></thead>
    <tbody>
      <tr><td>플레이 감각</td><td>루트 따라가기</td><td>자유 대화</td><td>직접 질문하고 논리 연결</td></tr>
      <tr><td>사건 일관성</td><td>높음</td><td>낮아지기 쉬움</td><td>Case Graph + Validator로 보호</td></tr>
      <tr><td>재미의 중심</td><td>정답 선택</td><td>캐릭터 반응</td><td>진술과 증거의 충돌 발견</td></tr>
      <tr><td>반복 가치</td><td>낮음</td><td>높지만 산만</td><td>질문 전략과 해금 경로 변화</td></tr>
    </tbody>
  </table>
</section>

---

<section class="slide-fill demo">
  <p class="eyebrow">DEMO FLOW</p>
  <h2>3분 데모 시나리오</h2>
  <div class="timeline">
    <div><span>00:00</span><b>사건 진입</b><p>피해자, 장소, 초기 증거, 네 명의 용의자 제시</p></div>
    <div><span>00:40</span><b>한서연 심문</b><p>자연어 질문으로 22시 알리바이 확보</p></div>
    <div><span>01:20</span><b>증거 대조</b><p>서재 출입 기록과 진술의 충돌 확인</p></div>
    <div><span>02:00</span><b>모순 제기</b><p>압박 상승, 추가 진술/증거 해금</p></div>
    <div><span>02:40</span><b>최종 추리</b><p>범인·동기·수단·결정적 모순 제출</p></div>
  </div>
</section>

---

<section class="slide-fill mvp">
  <p class="eyebrow">MVP SCOPE</p>
  <h2>3주 안에 검증할 핵심: “끝까지 플레이 가능한 사건 1개”</h2>
  <div class="mvp-grid">
    <article><b>완성 사건 1개</b><p>도입, 심문, 모순 판정, 최종 지목, 엔딩 피드백</p></article>
    <article><b>용의자 4명</b><p>관계, 비밀, 압박 단계, 캐릭터별 말투</p></article>
    <article><b>증거 8개+</b><p>공개/해금 조건, 신뢰도, 관련 시간/장소</p></article>
    <article><b>BE-backed UI</b><p>세션 상태, SSE 이벤트, 증거/진술/관계 패널</p></article>
    <article><b>AI + Rule Hybrid</b><p>자연스러운 답변은 AI, 판정과 상태 변경은 검증 계층</p></article>
    <article><b>Noir Visual</b><p>몰입형 저택 수사 데스크와 고품질 캐릭터 연출</p></article>
  </div>
</section>

---

<section class="slide-fill closing">
  <p class="eyebrow">CLOSING MESSAGE</p>
  <h2>플레이어는 범인을 고르는 것이 아니라,<br/>진실이 무너지는 순간을 직접 만든다.</h2>
  <div class="closing-card">
    <p>이 게임의 차별점은 “AI가 이야기를 생성한다”가 아닙니다.</p>
    <p><b>플레이어의 질문이 캐릭터의 방어 논리를 흔들고, 증거가 말의 틈을 벌리며, 검증된 사건 상태가 추리의 정답 가능성을 지킵니다.</b></p>
  </div>
  <div class="tagline">AI 자연어 심문 × 증거 기반 판정 × 누아르 수사 데스크</div>
</section>
