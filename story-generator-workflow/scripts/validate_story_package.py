#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

FORBIDDEN_PUBLIC_KEYS = {
    "secret", "solution", "isCulprit", "hiddenTruth", "privateTimeline",
    "privateMotive", "actualAction", "secretNote", "finalVerdict",
}

REQUIRED_TOP_KEYS = [
    "caseId", "sceneId", "title", "summary", "suspects", "evidence",
    "statements", "questions", "contradictions", "opening", "storyline", "solution",
]


def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path + "/" + str(k), k, v
            yield from walk(v, path + "/" + str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, path + f"/{i}")


def collect_ids(case):
    ids = set()
    for section in ["suspects", "evidence", "records", "statements", "questions", "contradictions"]:
        for item in case.get(section, []):
            if "id" in item:
                ids.add(item["id"])
            if "characterId" in item:
                ids.add(item["characterId"])
    for tl in case.get("storyline", {}).get("timeline", []):
        if "timelineId" in tl:
            ids.add(tl["timelineId"])
    for ctl in case.get("characterTimelines", []):
        for key in ["publicClaims", "perceivedEvents", "privateEvents"]:
            for item in ctl.get(key, []):
                if "timelineId" in item:
                    ids.add(item["timelineId"])
    return ids


def main(path: str) -> int:
    case_path = Path(path)
    case = json.loads(case_path.read_text(encoding="utf-8"))
    errors = []

    for key in REQUIRED_TOP_KEYS:
        if key not in case:
            errors.append(f"missing top-level key: {key}")

    ids = collect_ids(case)
    for con in case.get("contradictions", []):
        for ref_key in ["suspectId", "requiredStatementIds", "requiredEvidenceIds", "requiredTimelineIds", "unlocksEvidenceIds", "unlocksQuestionIds", "unlocksStatementIds"]:
            refs = con.get(ref_key, [])
            if isinstance(refs, str):
                refs = [refs]
            for ref in refs:
                if ref and ref not in ids:
                    errors.append(f"unresolved ref in {con.get('id')}.{ref_key}: {ref}")

    public_like = {
        "opening": case.get("opening"),
        "storyline": case.get("storyline"),
        "suspects": [
            {k: v for k, v in s.items() if k not in {"secret", "isCulprit"}}
            for s in case.get("suspects", [])
        ],
    }
    for path_, key, _ in walk(public_like):
        if key in FORBIDDEN_PUBLIC_KEYS:
            errors.append(f"forbidden public key candidate at {path_}: {key}")

    if errors:
        print("INVALID")
        for e in errors:
            print("-", e)
        return 1
    print("VALID")
    print(f"caseId={case.get('caseId')} ids={len(ids)} suspects={len(case.get('suspects', []))} contradictions={len(case.get('contradictions', []))}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: validate_story_package.py <case.json>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
