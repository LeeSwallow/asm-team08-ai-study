const BASE_URL = process.env.BASE_URL ?? "http://127.0.0.1:8000/api/v1";
const CASE_ID = process.env.CASE_ID ?? "case_001";
const SUSPECT_ID = process.env.SUSPECT_ID ?? "char_hanseoyeon";

const turns = [
  "안녕하세요. 잠깐 이야기할 수 있을까요?",
  "22시 이후 어디에 있었나요?",
  "방금 말한 22시 이후 행적을 다시 자세히 설명해 주세요.",
  "서재 출입 기록에는 왜 당신 이름이 남아 있나요?",
  "깨진 회중시계에 대해 알고 있나요?",
  "왜 대답을 피하는 것 같죠?",
  "그 시간에 윤재호 집사는 어디 있었나요?",
  "상속 문제로 강도준과 다툰 적 있나요?",
  "아까 답변과 출입 기록이 맞지 않습니다. 다시 말해보세요.",
];

function normalizeText(value) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function ngrams(value, size = 3) {
  const text = normalizeText(value).replace(/\s/g, "");
  if (text.length <= size) return new Set(text ? [text] : []);
  const grams = new Set();
  for (let index = 0; index <= text.length - size; index += 1) {
    grams.add(text.slice(index, index + size));
  }
  return grams;
}

function similarity(left, right) {
  const a = ngrams(left);
  const b = ngrams(right);
  if (a.size === 0 && b.size === 0) return 1;
  const intersection = [...a].filter((item) => b.has(item)).length;
  const union = new Set([...a, ...b]).size;
  return union === 0 ? 0 : intersection / union;
}

async function request(path, options) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
    ...options,
  });
  const text = await response.text();
  let body;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!response.ok) {
    const detail = typeof body === "string" ? body : JSON.stringify(body);
    throw new Error(`HTTP ${response.status} ${path}: ${detail}`);
  }
  return body;
}

function latestAnswer(payload, previousLogLength) {
  const log = Array.isArray(payload.dialogueLog) ? payload.dialogueLog : [];
  const newItems = log.slice(previousLogLength);
  const answer = [...newItems].reverse().find((item) => item?.speaker !== "player");
  return answer?.text ?? "";
}

function countRemainingQuestions(payload) {
  const questions = Array.isArray(payload.questions) ? payload.questions : [];
  const unlocked = Array.isArray(payload.unlockedQuestionIds) ? new Set(payload.unlockedQuestionIds) : null;
  const used = new Set(
    (Array.isArray(payload.dialogueLog) ? payload.dialogueLog : [])
      .filter((item) => item?.speaker === "player" && item?.questionId)
      .map((item) => item.questionId),
  );
  return questions.filter((item) => (!unlocked || unlocked.has(item.questionId)) && !used.has(item.questionId)).length;
}

function redFlag(message, details = {}) {
  return { message, details };
}

const session = await request("/sessions", {
  method: "POST",
  body: JSON.stringify({ caseId: CASE_ID }),
});

const sessionId = session.sessionId;
let previousLogLength = Array.isArray(session.dialogueLog) ? session.dialogueLog.length : 0;
const results = [];
const redFlags = [];

console.log(`dialogue repetition smoke`);
console.log(`baseUrl=${BASE_URL}`);
console.log(`caseId=${CASE_ID}`);
console.log(`sessionId=${sessionId}`);
console.log(`suspectId=${SUSPECT_ID}`);

for (const [index, message] of turns.entries()) {
  const payload = await request(`/sessions/${sessionId}/dialogue`, {
    method: "POST",
    body: JSON.stringify({ suspectId: SUSPECT_ID, message }),
  });
  const dialogueResult = payload.dialogueResult ?? {};
  const diagnostics = payload.runtimeDiagnostics ?? {};
  const answer = latestAnswer(payload, previousLogLength);
  const log = Array.isArray(payload.dialogueLog) ? payload.dialogueLog : [];
  previousLogLength = log.length;

  const result = {
    turn: index + 1,
    input: message,
    answer,
    matchedQuestionId: dialogueResult.matchedQuestionId ?? diagnostics.matchedQuestionId ?? null,
    intent: dialogueResult.intent ?? diagnostics.intent ?? null,
    dialogueMode: dialogueResult.dialogueMode ?? diagnostics.dialogueMode ?? null,
    provider: dialogueResult.provider ?? diagnostics.provider ?? payload.provider ?? null,
    model: dialogueResult.model ?? diagnostics.model ?? payload.model ?? null,
    fallback: dialogueResult.fallbackUsed ?? diagnostics.fallbackUsed ?? payload.fallbackUsed ?? false,
    degraded: dialogueResult.degraded ?? diagnostics.degraded ?? payload.degraded ?? false,
    proposedEventsCount: dialogueResult.proposedEventsCount ?? diagnostics.proposedEventsCount ?? dialogueResult.proposedEvents?.length ?? 0,
    appliedEventsCount: dialogueResult.appliedEventsCount ?? diagnostics.appliedEventsCount ?? dialogueResult.appliedEvents?.length ?? 0,
    remainingQuestions: dialogueResult.remainingQuestions ?? diagnostics.remainingQuestions ?? payload.remainingQuestions,
    remainingQuestionItems: countRemainingQuestions(payload),
  };
  results.push(result);

  console.log(`\n# turn ${result.turn}`);
  console.log(`input: ${result.input}`);
  console.log(`answer: ${result.answer}`);
  console.log(`matchedQuestionId: ${result.matchedQuestionId ?? "null"}`);
  console.log(`intent/dialogueMode: ${result.intent ?? "null"} / ${result.dialogueMode ?? "null"}`);
  console.log(`provider/model: ${result.provider ?? "null"} / ${result.model ?? "null"}`);
  console.log(`fallback/degraded: ${result.fallback} / ${result.degraded}`);
  console.log(`events proposed/applied: ${result.proposedEventsCount} / ${result.appliedEventsCount}`);
  console.log(`remaining questions: ${result.remainingQuestions} (items=${result.remainingQuestionItems})`);
}

const matchedCounts = new Map();
for (const result of results) {
  if (!result.matchedQuestionId) continue;
  matchedCounts.set(result.matchedQuestionId, (matchedCounts.get(result.matchedQuestionId) ?? 0) + 1);
}

for (const [matchedQuestionId, count] of matchedCounts.entries()) {
  if (count >= 2) redFlags.push(redFlag("repeated matchedQuestionId", { matchedQuestionId, count }));
}

for (let left = 0; left < results.length; left += 1) {
  for (let right = left + 1; right < results.length; right += 1) {
    const score = similarity(results[left].answer, results[right].answer);
    if (results[left].answer && results[left].answer === results[right].answer) {
      redFlags.push(redFlag("byte-identical answers", { left: left + 1, right: right + 1, score }));
    } else if (score >= 0.82) {
      redFlags.push(redFlag("high-similarity answers", { left: left + 1, right: right + 1, score: Number(score.toFixed(3)) }));
    }
  }
}

const greeting = results[0];
if (greeting?.matchedQuestionId || !["small_talk", "greeting"].includes(greeting?.dialogueMode ?? greeting?.intent ?? "")) {
  redFlags.push(redFlag("greeting may have consumed or mapped to case question", {
    matchedQuestionId: greeting?.matchedQuestionId,
    intent: greeting?.intent,
    dialogueMode: greeting?.dialogueMode,
    remainingQuestions: greeting?.remainingQuestions,
  }));
}

for (const result of results) {
  const unrelated = /윤재호|강도준/.test(result.input);
  if (unrelated && result.matchedQuestionId?.includes("hanseoyeon")) {
    redFlags.push(redFlag("possibly unrelated cross-suspect question mapped to active suspect canned statement", {
      turn: result.turn,
      input: result.input,
      matchedQuestionId: result.matchedQuestionId,
    }));
  }
  if ((result.fallback || result.degraded) && result.provider && !String(result.provider).includes("fallback")) {
    redFlags.push(redFlag("fallback/degraded path reported with normal-looking provider", {
      turn: result.turn,
      provider: result.provider,
      fallback: result.fallback,
      degraded: result.degraded,
    }));
  }
}

console.log("\n# matchedQuestionId counts");
for (const [matchedQuestionId, count] of matchedCounts.entries()) {
  console.log(`${matchedQuestionId}: ${count}`);
}

console.log("\n# red flags");
if (redFlags.length === 0) {
  console.log("none");
} else {
  for (const item of redFlags) {
    console.log(`- ${item.message}: ${JSON.stringify(item.details)}`);
  }
}

if (redFlags.length > 0 && process.env.ALLOW_DIALOGUE_RED_FLAGS !== "1") {
  process.exitCode = 1;
}
