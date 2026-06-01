from dataclasses import dataclass
from typing import Any

from app.domain.case_engine import (
    character_public_timeline,
    emotional_state,
    pressure_state,
    public_speech_style,
    tension_level,
    visible_timeline,
)
from app.domain.models import Case, SessionState


@dataclass
class CaseKnowledgeService:
    def character_pack(
        self,
        case: Case,
        session: SessionState,
        suspect_id: str,
        recent_limit: int = 8,
    ) -> dict[str, Any]:
        suspect = next(item for item in case.suspects if item.characterId == suspect_id)
        visible_statement_ids = set(session.unlockedStatementIds)
        visible_evidence_ids = set(session.unlockedEvidenceIds)
        visible_record_ids = set(session.unlockedRecordIds)
        timeline_items = visible_timeline(case, session)
        claimed_timeline = character_public_timeline(case, session, suspect_id)
        alibi_statements = [
            item
            for item in case.statements
            if item.characterId == suspect_id and item.statementId in visible_statement_ids
        ]
        visible_evidence = [item for item in case.evidence if item.evidenceId in visible_evidence_ids]
        visible_records = [item for item in case.records if item.recordId in visible_record_ids]
        visible_relations = [item for item in case.relations if item.relationshipId in set(session.unlockedRelationIds)]
        pressure = max(0, min(100, int(session.pressureBySuspect.get(suspect_id, 0))))
        pressure_label = pressure_state(pressure)
        tension = tension_level(pressure)
        emotion = emotional_state(pressure)
        recent_dialogue = [
            {
                "speaker": item.speaker,
                "speakerType": "player" if item.speaker == "player" else "character",
                "suspectId": item.suspectId,
                "questionId": item.questionId,
                "text": item.text,
                "pressureHint": self._pressure_hint(item.text),
                "sourceRefs": [],
            }
            for item in session.dialogueLog[-recent_limit:]
        ]
        recent_pressure = self._recent_dialogue_pressure(recent_dialogue)
        persona_variants = self._persona_variants(suspect_id)
        active_overlay = self._active_persona_overlay(
            persona_variants=persona_variants,
            tension=tension,
            pressure_label=pressure_label,
            emotion=emotion,
            pressure=pressure,
            discovered_contradiction_ids=session.discoveredContradictionIds,
            recent_pressure=recent_pressure,
        )
        return {
            "packId": f"ckp_{case.caseId}_{suspect.characterId}_{session.sessionId}",
            "caseId": case.caseId,
            "sessionId": session.sessionId,
            "version": "case-knowledge-pack/v1",
            "source": "compiled-casewiki-visible-projection",
            "visibility": "public",
            "suspectId": suspect.characterId,
            "persona": public_speech_style(suspect_id).get("persona"),
            "publicPersona": suspect.publicProfile,
            "publicMask": suspect.role,
            "speechStyle": public_speech_style(suspect_id),
            "personaVariants": persona_variants,
            "activePersonaOverlay": active_overlay,
            "personaSkill": public_speech_style(suspect_id),
            "character": {
                "id": suspect.characterId,
                "name": suspect.name,
                "role": suspect.role,
                "publicProfile": suspect.publicProfile,
            },
            "claimedTimeline": claimed_timeline,
            "visibleTimeline": [
                {
                    "id": item.get("timelineId") or item.get("sourceId"),
                    "text": f"{item.get('time')}: {item.get('title')} - {item.get('description')}",
                    "timelineId": item.get("timelineId") or item.get("sourceId"),
                    "time": item.get("time"),
                    "summary": item.get("description"),
                    "sourceType": item.get("sourceType"),
                    "sourceId": item.get("sourceId"),
                    "sourceRefs": {"timelineIds": [item.get("timelineId") or item.get("sourceId")]},
                    "relatedTimelineIds": [item.get("timelineId") or item.get("sourceId")],
                    "visibility": "public",
                }
                for item in timeline_items
            ],
            "alibiSnippets": [
                {
                    "id": item.statementId,
                    "text": f"{item.timeWindow or '시간 불명'} {item.location or '장소 불명'}: {item.text}",
                    "statementId": item.statementId,
                    "sourceType": "statement",
                    "sourceId": item.statementId,
                    "sourceRefs": {"statementIds": [item.statementId]},
                    "relatedStatementIds": [item.statementId],
                    "visibility": "public",
                }
                for item in alibi_statements
            ],
            "evidenceSnippets": [
                {
                    "id": item.evidenceId,
                    "text": f"{item.name}: {item.description}",
                    "evidenceId": item.evidenceId,
                    "name": item.name,
                    "summary": item.description,
                    "sourceType": "evidence",
                    "sourceId": item.evidenceId,
                    "sourceRefs": {"evidenceIds": [item.evidenceId]},
                    "relatedEvidenceIds": [item.evidenceId],
                    "visibility": "public",
                }
                for item in visible_evidence
            ],
            "relationshipSnippets": [
                {
                    "id": item.relationshipId,
                    "relationshipId": item.relationshipId,
                    "text": f"{item.description}: {item.conflict}",
                    "summary": item.conflict,
                    "sourceType": "relationship",
                    "sourceId": item.relationshipId,
                    "sourceRefs": {"relationshipIds": [item.relationshipId]},
                    "visibility": "public",
                }
                for item in visible_relations
            ],
            "claimedAlibiStatements": [
                {
                    "statementId": item.statementId,
                    "questionText": item.questionText,
                    "text": item.text,
                    "timeWindow": item.timeWindow,
                    "location": item.location,
                }
                for item in alibi_statements
            ],
            "visibleEvidence": [
                {
                    "evidenceId": item.evidenceId,
                    "name": item.name,
                    "description": item.description,
                    "timeWindow": item.timeWindow,
                    "foundAt": item.foundAt,
                }
                for item in visible_evidence
            ],
            "visibleRecords": [
                {
                    "recordId": item.recordId,
                    "name": item.name,
                    "description": item.description,
                    "timeWindow": item.timeWindow,
                }
                for item in visible_records
            ],
            "recentDialogue": recent_dialogue,
            "blockedRefPolicy": "public_case_projection_only",
            "forbiddenRefs": [],
            "restrictedDataIncluded": False,
        }

    def _persona_variants(self, suspect_id: str) -> dict[str, dict[str, Any]]:
        base = {
            "allowedTone": ["formal", "precise", "guarded"],
            "forbiddenTone": ["confessional", "case-ending reveal", "non-public motive reveal"],
            "visibility": "public",
        }
        return {
            "baseline": {
                **base,
                "id": f"pv_{suspect_id}_baseline",
                "variantId": f"pv_{suspect_id}_baseline",
                "label": "baseline",
                "tensionLevel": "low",
                "tensionLevels": ["low"],
                "pressureState": "normal",
                "pressureStates": ["normal"],
                "emotionalState": "neutral",
                "emotionalStates": ["neutral"],
                "tone": "controlled",
                "evasiveness": 0.35,
                "hesitation": "low",
                "sample": "그 시간엔 제 방에 있었습니다. 필요한 만큼만 답하죠.",
                "overlay": {
                    "id": f"pv_{suspect_id}_baseline",
                    "label": "baseline",
                    "tone": "controlled",
                    "voice": "차분하고 예의 바르지만 거리를 두는 말투",
                    "styleDirectives": [
                        "calm",
                        "measured",
                        "polite distance",
                        "short factual answer",
                    ],
                    "tensionLevel": "low",
                    "pressureState": "normal",
                    "emotionalState": "neutral",
                },
            },
            "defensive": {
                **base,
                "id": f"pv_{suspect_id}_defensive",
                "variantId": f"pv_{suspect_id}_defensive",
                "label": "defensive",
                "tensionLevel": "medium",
                "tensionLevels": ["medium"],
                "pressureState": "pressed",
                "pressureStates": ["normal", "pressed"],
                "emotionalState": "wary",
                "emotionalStates": ["wary", "defensive"],
                "minTensionScore": 30,
                "maxTensionScore": 69,
                "tone": "guarded_defensive",
                "evasiveness": 0.55,
                "hesitation": "medium",
                "sample": "잠깐만요. 그렇게 단정하실 일은 아닙니다.",
                "overlay": {
                    "id": f"pv_{suspect_id}_defensive",
                    "label": "defensive",
                    "tone": "defensive",
                    "voice": "불편함을 숨기지 못하지만 아직 통제하려는 말투",
                    "styleDirectives": [
                        "defensive",
                        "controlled irritation",
                        "deny overreach",
                        "answer from visible alibi",
                        "avoid confession",
                    ],
                    "tensionLevel": "medium",
                    "pressureState": "pressed",
                    "emotionalState": "defensive",
                },
            },
            "pressed": {
                **base,
                "id": f"pv_{suspect_id}_pressed",
                "variantId": f"pv_{suspect_id}_pressed",
                "label": "pressed",
                "tensionLevel": "high",
                "tensionLevels": ["high"],
                "pressureState": "pressed",
                "pressureStates": ["pressed"],
                "emotionalState": "shocked",
                "emotionalStates": ["anxious", "shocked", "angry"],
                "minTensionScore": 45,
                "maxTensionScore": 69,
                "tone": "sharp_defensive",
                "evasiveness": 0.75,
                "hesitation": "high",
                "sample": "그만하시죠. 그 기록만으로 저를 몰아가실 생각인가요?",
                "overlay": {
                    "id": f"pv_{suspect_id}_pressed",
                    "label": "pressed",
                    "tone": "pressed",
                    "voice": "짧고 날카롭게 반응하며 감정이 튀어나오는 말투",
                    "styleDirectives": [
                        "curt",
                        "pressured",
                        "sharp reaction",
                        "visible agitation",
                        "stay within visible case context",
                    ],
                    "tensionLevel": "high",
                    "pressureState": "pressed",
                    "emotionalState": "shocked",
                },
            },
            "broken": {
                **base,
                "allowedTone": ["shaken", "direct", "admitting visible facts"],
                "id": f"pv_{suspect_id}_broken",
                "variantId": f"pv_{suspect_id}_broken",
                "label": "broken",
                "tensionLevel": "critical",
                "tensionLevels": ["critical"],
                "pressureState": "broken",
                "pressureStates": ["broken"],
                "emotionalState": "breakdown",
                "emotionalStates": ["breakdown", "broken"],
                "minTensionScore": 70,
                "tone": "broken_disclosure",
                "evasiveness": 0.15,
                "hesitation": "high",
                "sample": "알겠습니다. 공개된 범위에서 더 돌려 말하지 않겠습니다.",
                "overlay": {
                    "id": f"pv_{suspect_id}_broken",
                    "label": "broken",
                    "tone": "broken",
                    "voice": "무너져서 회피를 줄이고 공개된 사실을 직접 인정하는 말투",
                    "styleDirectives": [
                        "broken",
                        "direct disclosure",
                        "do not evade visible facts",
                        "stay within public case context",
                    ],
                    "tensionLevel": "critical",
                    "pressureState": "broken",
                    "emotionalState": "breakdown",
                },
            },
        }

    def _active_persona_overlay(
        self,
        persona_variants: dict[str, dict[str, Any]],
        tension: str,
        pressure_label: str,
        emotion: str,
        pressure: int,
        discovered_contradiction_ids: list[str],
        recent_pressure: float,
    ) -> dict[str, Any]:
        selected = "baseline"
        if tension == "critical" or pressure >= 70 or pressure_label == "broken" or emotion in {"breakdown", "broken"}:
            selected = "broken"
        elif tension == "high" or pressure >= 45:
            selected = "pressed"
        elif tension == "medium" or pressure >= 30 or recent_pressure >= 0.5:
            selected = "defensive"
        variant = persona_variants[selected]
        overlay = dict(variant["overlay"])
        overlay.update(
            {
                "variantId": variant["variantId"],
                "selectionReason": (
                    f"tensionLevel={tension} pressureState={pressure_label} "
                    f"emotionalState={emotion} tensionScore={pressure} recentDialoguePressure={recent_pressure}"
                ),
                "tensionLevel": tension,
                "pressureState": pressure_label,
                "emotionalState": emotion,
                "tensionScore": pressure,
                "contradictionPressure": {
                    "contradictionIds": list(discovered_contradiction_ids),
                    "newlyDiscovered": False,
                    "alreadyDiscovered": bool(discovered_contradiction_ids),
                },
                "recentDialoguePressure": recent_pressure,
                "evasiveness": variant["evasiveness"],
                "hesitation": variant["hesitation"],
                "allowedTone": list(variant["allowedTone"]),
                "forbiddenTone": list(variant["forbiddenTone"]),
                "visibility": "public",
            }
        )
        return overlay

    def _recent_dialogue_pressure(self, recent_dialogue: list[dict[str, Any]]) -> float:
        if not recent_dialogue:
            return 0.0
        pressure_hits = sum(1 for item in recent_dialogue if item.get("pressureHint"))
        return min(1.0, pressure_hits / 3)

    def _pressure_hint(self, text: str) -> str | None:
        compact = "".join(str(text or "").split())
        if any(term in compact for term in ("왜답변", "왜대답", "말이돼", "거짓", "모순", "이상", "압박")):
            return "dialogue_pressure"
        if any(term in compact for term in ("서재", "기록", "증거", "출입")):
            return "evidence_pressure"
        return None
