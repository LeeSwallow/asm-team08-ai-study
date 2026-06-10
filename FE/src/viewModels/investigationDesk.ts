import type { Evidence, GameSessionView, Question } from "../types";

export type EvidenceTileView = Evidence | undefined;

export type ContradictionCandidateView = {
  statement: string;
  evidence: string;
  statementId: string;
  evidenceId: string;
};

export function buildEvidenceTiles(session: GameSessionView): EvidenceTileView[] {
  return session.evidence;
}

export function findQuestionForDraft(session: GameSessionView, draft: string): Question | undefined {
  const typed = draft.trim();
  if (!session.selectedSuspectId) return undefined;
  const pool = session.questions.filter(
    (question) => question.suspectId === session.selectedSuspectId && session.unlockedQuestionIds.includes(question.id),
  );
  if (!typed) return pool.find((question) => !question.used) ?? pool[0];
  return pool.find((question) => question.label === typed);
}

export function nextQuestionHint(session: GameSessionView): string | undefined {
  if (!session.selectedSuspectId) return undefined;
  return session.questions.find(
    (question) =>
      question.suspectId === session.selectedSuspectId &&
      session.unlockedQuestionIds.includes(question.id) &&
      !question.used,
  )?.label;
}

export function latestSuspectAnswer(session: GameSessionView, suspectId?: string | null): string {
  const latest = session.dialogueLog
    .slice()
    .reverse()
    .find(
      (item) =>
        item.speaker !== "player" &&
        item.speaker !== "system" &&
        item.speaker !== "rule_engine" &&
        (!suspectId || item.suspectId === suspectId),
    );
  return latest?.text ?? "";
}

export function buildContradictionCandidates(session: GameSessionView): ContradictionCandidateView[] {
  if (!session.selectedSuspectId) return [];
  const statementsById = new Map(session.statements.map((statement) => [statement.id, statement]));
  return session.evidence
    .filter((evidence) => evidence.unlocked)
    .flatMap((evidence) => evidence.relatedStatementIds.map((statementId) => ({ evidence, statement: statementsById.get(statementId) })))
    .filter((item) => item.statement)
    .map(({ evidence, statement }) => ({
      statement: `${statement!.speaker}: ${statement!.text}`,
      evidence: `${evidence.title} (${evidence.time}) - ${evidence.description}`,
      statementId: statement!.id,
      evidenceId: evidence.id,
    }))
    .slice(0, 2);
}
