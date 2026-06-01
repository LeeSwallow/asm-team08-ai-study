import type { Evidence, SuspectStatus } from "../types";

export const QUESTION_LIMIT = 12;

export const statusLabels: Record<SuspectStatus, string> = {
  normal: "관찰 중",
  pressed: "압박 중",
  broken: "알리바이 붕괴",
};

export const canonicalExpressions = [
  "neutral",
  "wary",
  "defensive",
  "angry",
  "anxious",
  "shocked",
  "breakdown",
  "confident_lying",
  "sad",
  "focused",
] as const;

export type CanonicalExpression = typeof canonicalExpressions[number];

const expressionSet = new Set<string>(canonicalExpressions);

export const suspectAssetBasePaths: Record<string, string> = {
  char_hanseoyeon: "/assets/char_hanseoyeon",
  char_yoonjaeho: "/assets/char_yoonjaeho",
  char_parkmingyu: "/assets/char_parkmingyu",
  char_choiyuna: "/assets/char_choiyuna",
};

export const suspectAssetPaths: Record<string, string> = Object.fromEntries(
  Object.entries(suspectAssetBasePaths).map(([suspectId, basePath]) => [suspectId, `${basePath}_neutral.png`]),
);

export const suspectExpressionAssetCoverage: Record<string, readonly CanonicalExpression[]> = {
  char_hanseoyeon: canonicalExpressions,
  char_yoonjaeho: ["neutral"],
  char_parkmingyu: ["neutral"],
  char_choiyuna: ["neutral"],
};

export const evidenceIconByType: Record<Evidence["type"], string> = {
  physical: "◉",
  record: "▤",
  digital: "▣",
  relationship: "◎",
};

export const evidenceAssetPaths: Record<string, string> = {
  ev_broken_watch: "/assets/evidence_watch.png",
  ev_wine_glass: "/assets/evidence_wine.png",
  ev_study_entry_log: "/assets/evidence_entry_log.png",
  ev_servant_log: "/assets/evidence_servant_log.png",
  ev_torn_will: "/assets/evidence_will.png",
  ev_phone_call: "/assets/evidence_phone.png",
  ev_medicine_box: "/assets/evidence_medicine.png",
  ev_storm_blackout: "/assets/evidence_blackout.png",
};

export const lockedEvidenceAssetPath = "/assets/evidence_locked.svg";
export const backgroundAssetPaths: Record<string, string> = {
  "mansion-study-bg": "/assets/mansion-study-bg.png",
  mansion_study_night: "/assets/mansion-study-bg.png",
};

export const flowSteps = [
  { icon: "●●●", title: "사용자 입력", detail: "자연어 질문" },
  { icon: "◕", title: "Character Agent", detail: "화자의 답변 생성" },
  { icon: "▧", title: "Light Rule Check", detail: "규칙 기반 검증" },
  { icon: "⚖", title: "GameMaster Agent", detail: "대화 흐름 및 상태 관리" },
  { icon: "▤", title: "결과 기록", detail: "증언/모순 사항 저장" },
] as const;

export function normalizeExpression(expression?: string): CanonicalExpression {
  return expression && expressionSet.has(expression) ? (expression as CanonicalExpression) : "neutral";
}

export function suspectAsset(suspectId?: string, expression?: string) {
  if (!suspectId) return undefined;
  const basePath = suspectAssetBasePaths[suspectId];
  if (!basePath) return undefined;
  const normalized = normalizeExpression(expression);
  const covered = suspectExpressionAssetCoverage[suspectId]?.includes(normalized);
  return `${basePath}_${covered ? normalized : "neutral"}.png`;
}

export function evidenceAsset(evidenceId?: string) {
  return evidenceId ? evidenceAssetPaths[evidenceId] : undefined;
}

export function backgroundAsset(backgroundId?: string) {
  return backgroundId ? backgroundAssetPaths[backgroundId] : undefined;
}

export function suspectStatusText(status: SuspectStatus, isSelected: boolean) {
  return isSelected ? "심문 진행 중" : statusLabels[status];
}
