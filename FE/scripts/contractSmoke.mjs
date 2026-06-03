import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const root = resolve(scriptDir, "..");

const apiSource = readFileSync(resolve(root, "src/api.ts"), "utf8");
const implementationDoc = readFileSync(resolve(root, "Docs/implementation.md"), "utf8");

const requiredApiPaths = [
  "/api/v1/cases",
  "/api/v1/sessions",
  "/dialogue",
  "/events",
  "/debug/pressure",
  "/debug/unlock",
  "/accusation",
  "/notes",
  "/notes/summary",
  "/bookmarks",
  "/summary",
  "/hint",
  "/ending",
];

for (const path of requiredApiPaths) {
  if (!apiSource.includes(path) && !implementationDoc.includes(path)) {
    throw new Error(`FE API contract missing BE path: ${path}`);
  }
}

const submitContradictionMatch = apiSource.match(/export async function submitContradiction[\s\S]*?^}/m);
if (!submitContradictionMatch) {
  throw new Error("submitContradiction API client function was not found");
}

const submitContradictionSource = submitContradictionMatch[0];
if (submitContradictionSource.includes("/contradictions")) {
  throw new Error("submitContradiction must not call removed /contradictions endpoint");
}

if (!submitContradictionSource.includes("/dialogue")) {
  throw new Error("submitContradiction must submit natural-language contradiction claims through /dialogue");
}

if (!submitContradictionSource.includes("statementText") || !submitContradictionSource.includes("evidenceText")) {
  throw new Error("submitContradiction must compose public statement/evidence context into the dialogue message");
}

if (implementationDoc.includes("POST /api/v1/sessions/{sessionId}/contradictions")) {
  throw new Error("FE implementation docs still reference the removed /contradictions endpoint");
}

if (!implementationDoc.includes("POST /api/v1/sessions/{sessionId}/dialogue")) {
  throw new Error("FE implementation docs must document dialogue-based contradiction submission");
}

for (const helperName of ["createBookmark", "summarizeNotes", "getSessionSummary", "getSessionHint", "getSessionEnding"]) {
  if (!apiSource.includes(`function ${helperName}`)) {
    throw new Error(`FE API client missing helper for BE contract: ${helperName}`);
  }
}

console.log("frontend contract smoke passed");
