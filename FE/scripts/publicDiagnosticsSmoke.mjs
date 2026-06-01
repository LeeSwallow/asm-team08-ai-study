import { sanitizePublicDiagnosticValue, sanitizePublicId, sanitizeSourceRefs } from "../src/utils/publicDiagnostics.ts";

const forbiddenValues = [
  "private_timeline",
  "private-refs",
  "private_motive",
  "final_discovery",
  "final-verdict",
  "actual_action",
  "actual-location",
  "is_culprit",
  "secret_note",
  "solution",
  "culprit",
  "technical_private_ref",
];

for (const value of forbiddenValues) {
  if (sanitizePublicDiagnosticValue(value) !== "[suppressed-public-diagnostic]") {
    throw new Error(`diagnostic value was not suppressed: ${value}`);
  }
  if (sanitizePublicId(`ev_${value}`) !== undefined) {
    throw new Error(`public id was not suppressed: ev_${value}`);
  }
}

const sourceRefs = sanitizeSourceRefs({
  evidenceIds: ["ev_study_entry_log", "ev_private_timeline"],
  statementIds: ["st_hanseoyeon_room_2200"],
  recordIds: ["rec_public_entry"],
  timelineIds: ["tl_public_2200"],
  relationshipIds: ["rel_public_family"],
  questionIds: ["q_hanseoyeon_alibi"],
  contradictionIds: ["con_call_record"],
  private_timeline: ["tl_hidden"],
  private_refs: ["pv_hidden"],
  private_motive: ["pv_motive"],
  final_discovery: ["case_final"],
  final_verdict: ["case_verdict"],
  actual_action: ["evt_action"],
  actual_location: ["evt_location"],
  is_culprit: ["char_hanseoyeon"],
  secret_note: ["note_hidden"],
  publicLookingButUnknownIds: ["ev_study_entry_log"],
});

const expectedKeys = ["evidenceIds", "statementIds", "recordIds", "timelineIds", "relationshipIds", "questionIds", "contradictionIds"];
const actualKeys = Object.keys(sourceRefs ?? {});
for (const key of expectedKeys) {
  if (!actualKeys.includes(key)) throw new Error(`allowed sourceRef key was dropped: ${key}`);
}
for (const key of actualKeys) {
  if (!expectedKeys.includes(key)) throw new Error(`unknown or private sourceRef key survived: ${key}`);
}
if (sourceRefs?.evidenceIds?.includes("ev_private_timeline")) {
  throw new Error("forbidden sourceRef value survived under allowed key");
}

console.log("public diagnostics sanitizer smoke passed");
