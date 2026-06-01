const forbiddenRefTokens = [
  "secret",
  "solution",
  "culprit",
  "culpritid",
  "isculprit",
  "privatetimeline",
  "privateevents",
  "privatemotive",
  "privateref",
  "privaterefs",
  "finaldiscovery",
  "finalverdict",
  "actualaction",
  "actuallocation",
  "secretnote",
];

const publicIdPattern = /^(st|ev|rec|rel|tl|ctl|q|con|note|cand|char|victim|scene|case|evt|pv|ckp)_[a-z0-9_:-]+$/i;
const publicSourceRefKeys = new Set([
  "evidenceIds",
  "statementIds",
  "recordIds",
  "timelineIds",
  "relationshipIds",
  "questionIds",
  "contradictionIds",
]);

function normalizedRefToken(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function containsForbiddenRefToken(value: string) {
  const normalized = normalizedRefToken(value);
  return forbiddenRefTokens.some((token) => normalized.includes(token));
}

export function sanitizePublicDiagnosticValue(value?: string | null): string | undefined {
  if (!value) return undefined;
  return containsForbiddenRefToken(value) ? "[suppressed-public-diagnostic]" : value;
}

export function sanitizePublicId(value: string): string | undefined {
  if (containsForbiddenRefToken(value)) return undefined;
  return publicIdPattern.test(value) ? value : undefined;
}

export function sanitizePublicIds(values?: string[]): string[] {
  return (values ?? []).map(sanitizePublicId).filter((item): item is string => Boolean(item));
}

export function sanitizeSourceRefs(refs?: Record<string, string[]>): Record<string, string[]> | undefined {
  if (!refs) return undefined;
  const sanitized = Object.fromEntries(
    Object.entries(refs)
      .map(([key, values]) => {
        if (!publicSourceRefKeys.has(key) || containsForbiddenRefToken(key)) return undefined;
        const cleanValues = values.map(sanitizePublicId).filter((item): item is string => Boolean(item));
        return cleanValues.length ? [key, cleanValues] : undefined;
      })
      .filter((item): item is [string, string[]] => Boolean(item)),
  );
  return Object.keys(sanitized).length ? sanitized : undefined;
}
