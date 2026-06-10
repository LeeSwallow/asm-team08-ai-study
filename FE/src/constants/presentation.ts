import type { Evidence, SuspectStatus } from "../types";

export const QUESTION_LIMIT = 30;

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

export const suspectDirectAssetPaths: Record<string, string> = {
  char_helen_stoner: "/assets/cases/case_speckled_band/characters/char_helen_stoner/low.png",
  char_grimesby_roylott: "/assets/cases/case_speckled_band/characters/char_grimesby_roylott/low.png",
  char_housekeeper: "/assets/cases/case_speckled_band/characters/char_housekeeper/low.png",
  char_gypsy_camp: "/assets/cases/case_speckled_band/characters/char_gypsy_camp/low.png",
  char_son_junsik: "/assets/cases/case_body_and_onsen/characters/char_son_junsik/low.png",
  char_lim_hoseon: "/assets/cases/case_body_and_onsen/characters/char_lim_hoseon/low.png",
  char_kwon_juri: "/assets/cases/case_body_and_onsen/characters/char_kwon_juri/low.png",
  char_gyeong_daesu: "/assets/cases/case_body_and_onsen/characters/char_gyeong_daesu/low.png",
  char_woo_suyeon: "/assets/cases/case_body_and_onsen/characters/char_woo_suyeon/low.png",
};

export const suspectAssetPaths: Record<string, string> = Object.fromEntries(
  [
    ...Object.entries(suspectAssetBasePaths).map(([suspectId, basePath]) => [suspectId, `${basePath}_neutral.png`]),
    ...Object.entries(suspectDirectAssetPaths),
  ],
);

export const suspectExpressionAssetCoverage: Record<string, readonly CanonicalExpression[]> = {
  char_hanseoyeon: canonicalExpressions,
  char_yoonjaeho: canonicalExpressions,
  char_parkmingyu: canonicalExpressions,
  char_choiyuna: canonicalExpressions,
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
  ev_ring_near_victim: "/assets/evidence_ring.png",
  ev_lipstick_tube: "/assets/evidence_lipstick_tube.png",
  ev_window_bolt: "/assets/evidence_window_bolt.png",
  ev_deleted_cctv: "/assets/evidence_deleted_cctv.png",
  ev_prescription_dispute_note: "/assets/evidence_prescription_dispute_note.png",
  ev_admin_schedule_note: "/assets/evidence_admin_schedule_note.png",
  ev_doctor_guestroom_record: "/assets/evidence_doctor_guestroom_record.png",
  ev_yoon_route_log: "/assets/evidence_yoon_route_log.png",
  ev_key_cabinet_check: "/assets/evidence_key_cabinet_check.png",
  ev_household_account_note: "/assets/evidence_household_account_note.png",
  ev_hanseoyeon_tremor_note: "/assets/evidence_hanseoyeon_tremor_note.png",
  ev_yoonjaeho_folded_route_copy: "/assets/evidence_yoonjaeho_folded_route_copy.png",
  ev_parkmingyu_chart_backup: "/assets/evidence_parkmingyu_chart_backup.png",
  ev_choiyuna_shredded_schedule: "/assets/evidence_choiyuna_shredded_schedule.png",
  ev_pancreatic_diagnosis: "/assets/evidence_pancreatic_diagnosis.png",
  ev_narcotic_supply_record: "/assets/evidence_narcotic_supply_record.png",
  ev_childhood_photo: "/assets/evidence_childhood_photo.png",
  ev_choiyuna_ring_receipt: "/assets/evidence_choiyuna_ring_receipt.png",
  ev_coroner_report: "/assets/cases/case_speckled_band/evidence/ev_coroner_report.png",
  ev_gypsy_scarves: "/assets/cases/case_speckled_band/evidence/ev_gypsy_scarves.png",
  ev_fireplace_poker: "/assets/cases/case_speckled_band/evidence/ev_fireplace_poker.png",
  ev_iron_safe: "/assets/cases/case_speckled_band/evidence/ev_iron_safe.png",
  ev_looped_whip: "/assets/cases/case_speckled_band/evidence/ev_looped_whip.png",
  ev_milk_saucer: "/assets/cases/case_speckled_band/evidence/ev_milk_saucer.png",
  ev_fixed_bed: "/assets/cases/case_speckled_band/evidence/ev_fixed_bed.png",
  ev_ventilator: "/assets/cases/case_speckled_band/evidence/ev_ventilator.png",
  ev_fake_bell_pull: "/assets/cases/case_speckled_band/evidence/ev_fake_bell_pull.png",
  ev_mothers_will: "/assets/cases/case_speckled_band/evidence/ev_mothers_will.png",
  ev_bloodied_stone: "/assets/cases/case_body_and_onsen/evidence/ev_bloodied_stone.png",
  ev_hoseon_yukata_tear: "/assets/cases/case_body_and_onsen/evidence/ev_hoseon_yukata_tear.png",
  ev_mens_door_thread: "/assets/cases/case_body_and_onsen/evidence/ev_mens_door_thread.png",
  ev_victim_basket_disturbed: "/assets/cases/case_body_and_onsen/evidence/ev_victim_basket_disturbed.png",
  ev_silenced_pistol: "/assets/cases/case_body_and_onsen/evidence/ev_silenced_pistol.png",
  ev_pistol_oil_on_hoseon_hand: "/assets/cases/case_body_and_onsen/evidence/ev_pistol_oil_on_hoseon_hand.png",
  ev_lobby_dry_floor: "/assets/cases/case_body_and_onsen/evidence/ev_lobby_dry_floor.png",
  ev_hoseon_phone_message: "/assets/cases/case_body_and_onsen/evidence/ev_hoseon_phone_message.png",
  ev_suyeon_photo: "/assets/cases/case_body_and_onsen/evidence/ev_suyeon_photo.png",
  ev_daesu_cash: "/assets/cases/case_body_and_onsen/evidence/ev_daesu_cash.png",
  ev_daesu_matches: "/assets/cases/case_body_and_onsen/evidence/ev_daesu_matches.png",
  ev_suyeon_knife: "/assets/cases/case_body_and_onsen/evidence/ev_suyeon_knife.png",
  ev_suyeon_note: "/assets/cases/case_body_and_onsen/evidence/ev_suyeon_note.png",
  ev_juri_ticket: "/assets/cases/case_body_and_onsen/evidence/ev_juri_ticket.png",
  ev_junsik_promotion_note: "/assets/cases/case_body_and_onsen/evidence/ev_junsik_promotion_note.png",
  ev_bank_statement: "/assets/cases/case_body_and_onsen/evidence/ev_bank_statement.png",
  ev_junsik_marijuana: "/assets/cases/case_body_and_onsen/evidence/ev_junsik_marijuana.png",
  ev_victim_juri_photo_schedule: "/assets/cases/case_body_and_onsen/evidence/ev_victim_juri_photo_schedule.png",
};

export const lockedEvidenceAssetPath = "/assets/evidence_locked.svg";
export const backgroundAssetPaths: Record<string, string> = {
  "mansion-study-bg": "/assets/mansion-study-bg.png",
  mansion_study_night: "/assets/mansion-study-bg.png",
  case_001: "/assets/mansion-study-bg.png",
  "case-001": "/assets/mansion-study-bg.png",
  case_002: "/assets/cases/case_body_and_onsen/backgrounds/main.png",
  "case-002": "/assets/cases/case_body_and_onsen/backgrounds/main.png",
  case_speckled_band: "/assets/cases/case_speckled_band/backgrounds/main.png",
  "case_speckled_band/main": "/assets/cases/case_speckled_band/backgrounds/main.png",
  case_003: "/assets/cases/case_speckled_band/backgrounds/main.png",
  "case-003": "/assets/cases/case_speckled_band/backgrounds/main.png",
  case_body_and_onsen: "/assets/cases/case_body_and_onsen/backgrounds/main.png",
  "case_body_and_onsen/main": "/assets/cases/case_body_and_onsen/backgrounds/main.png",
};

export const caseCoverAssetPaths: Record<string, string> = {
  case_001: "/assets/case_001_cover_v2.png",
  "case-001": "/assets/case_001_cover_v2.png",
  case_002: "/assets/case_002_cover.png",
  "case-002": "/assets/case_002_cover.png",
  case_speckled_band: "/assets/cases/case_speckled_band/backgrounds/main.png",
  case_003: "/assets/cases/case_speckled_band/backgrounds/main.png",
  "case-003": "/assets/cases/case_speckled_band/backgrounds/main.png",
  case_body_and_onsen: "/assets/cases/case_body_and_onsen/backgrounds/main.png",
};

export function normalizeExpression(expression?: string): CanonicalExpression {
  return expression && expressionSet.has(expression) ? (expression as CanonicalExpression) : "neutral";
}

export function suspectAsset(suspectId?: string, expression?: string) {
  if (!suspectId) return undefined;
  const directPath = suspectDirectAssetPaths[suspectId];
  if (directPath) return directPath;
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

export function caseCoverAsset(caseId?: string, sceneId?: string) {
  if (caseId && caseCoverAssetPaths[caseId]) return caseCoverAssetPaths[caseId];
  if (sceneId && caseCoverAssetPaths[sceneId]) return caseCoverAssetPaths[sceneId];
  return backgroundAsset(defaultBackgroundIdForCase(caseId));
}

export function defaultBackgroundIdForCase(caseId?: string) {
  return caseId && backgroundAssetPaths[caseId] ? caseId : "mansion-study-bg";
}

export function suspectStatusText(status: SuspectStatus, isSelected: boolean) {
  return isSelected ? "심문 진행 중" : statusLabels[status];
}
