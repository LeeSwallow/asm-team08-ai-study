export type AppRoute =
  | { name: "caseList" }
  | { name: "caseDetail"; caseId: string }
  | { name: "sessionDesk"; sessionId: string };

function cleanSegment(value: string | undefined): string {
  return decodeURIComponent(value ?? "").trim();
}

export function parseRoute(pathname = window.location.pathname): AppRoute {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return { name: "caseList" };
  if (segments[0] === "cases" && segments[1]) return { name: "caseDetail", caseId: cleanSegment(segments[1]) };
  if (segments[0] === "cases") return { name: "caseList" };
  if (segments[0] === "sessions" && segments[1]) return { name: "sessionDesk", sessionId: cleanSegment(segments[1]) };
  return { name: "caseList" };
}

export function caseListPath() {
  return "/cases";
}

export function caseDetailPath(caseId: string) {
  return `/cases/${encodeURIComponent(caseId)}`;
}

export function sessionPath(sessionId: string) {
  return `/sessions/${encodeURIComponent(sessionId)}`;
}
