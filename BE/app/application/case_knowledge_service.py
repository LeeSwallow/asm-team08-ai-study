from dataclasses import dataclass
from typing import Any

from app.domain.case_engine import (
    character_public_timeline,
    emotional_state,
    pressure_state,
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
        suspect_dialogue = [item for item in session.dialogueLog if item.suspectId == suspect_id]
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
            for item in suspect_dialogue[-recent_limit:]
        ]
        recent_pressure = self._recent_dialogue_pressure(recent_dialogue)
        speech_style = suspect.speechStyle or {}
        persona_variants = self._persona_variants(suspect)
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
            "persona": speech_style.get("persona") or suspect.publicProfile,
            "publicPersona": suspect.publicProfile,
            "publicMask": suspect.role,
            "speechStyle": speech_style,
            "personaVariants": persona_variants,
            "activePersonaOverlay": active_overlay,
            "personaSkill": speech_style,
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

    def _persona_variants(self, suspect) -> dict[str, dict[str, Any]]:
        if suspect.personaVariants:
            return self._case_persona_variants(suspect)
        suspect_id = suspect.characterId
        return {
            f"pv_{suspect_id}_default": {
                "id": f"pv_{suspect_id}_default",
                "variantId": f"pv_{suspect_id}_default",
                "label": "default",
                "tensionLevels": [],
                "pressureStates": [],
                "emotionalStates": [],
                "tone": suspect.speechStyle.get("tone") if suspect.speechStyle else "neutral",
                "evasiveness": 0.5,
                "hesitation": None,
                "allowedTone": [],
                "forbiddenTone": ["case-ending reveal", "non-public motive reveal"],
                "visibility": "public",
                "overlay": {
                    "id": f"pv_{suspect_id}_default",
                    "label": "default",
                    "tone": suspect.speechStyle.get("tone") if suspect.speechStyle else "neutral",
                    "voice": suspect.publicProfile,
                    "styleDirectives": [],
                },
            }
        }

    def _case_persona_variants(self, suspect) -> dict[str, dict[str, Any]]:
        variants: dict[str, dict[str, Any]] = {}
        for index, item in enumerate(suspect.personaVariants):
            if not isinstance(item, dict):
                continue
            variant_id = str(item.get("id") or item.get("variantId") or f"pv_{suspect.characterId}_{index}")
            overlay = dict(item.get("overlay") or {})
            overlay.setdefault("id", variant_id)
            overlay.setdefault("label", item.get("label") or variant_id)
            if "tensionLevel" not in overlay and item.get("tensionLevels"):
                levels = item.get("tensionLevels") or []
                overlay["tensionLevel"] = levels[0] if levels else None
            if "pressureState" not in overlay and item.get("pressureStates"):
                states = item.get("pressureStates") or []
                overlay["pressureState"] = states[0] if states else None
            variants[variant_id] = {
                "id": variant_id,
                "variantId": variant_id,
                "label": item.get("label") or variant_id,
                "tensionLevels": self._selector_list(item.get("tensionLevels") or item.get("tensionLevel")),
                "pressureStates": self._selector_list(item.get("pressureStates") or item.get("pressureState")),
                "emotionalStates": self._selector_list(item.get("emotionalStates") or item.get("emotionalState")),
                "minTensionScore": item.get("minTensionScore"),
                "maxTensionScore": item.get("maxTensionScore"),
                "tone": item.get("tone") or overlay.get("tone"),
                "evasiveness": item.get("evasiveness", overlay.get("evasiveness", 0.5)),
                "hesitation": item.get("hesitation", overlay.get("hesitation")),
                "allowedTone": self._selector_list(item.get("allowedTone")),
                "forbiddenTone": self._selector_list(item.get("forbiddenTone")),
                "visibility": "public",
                "overlay": overlay,
            }
        return variants or self._persona_variants(suspect.model_copy(update={"personaVariants": []}))

    def _selector_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value]
        return [str(value)]

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
        selected = self._select_persona_variant(
            persona_variants=persona_variants,
            tension=tension,
            pressure_label=pressure_label,
            emotion=emotion,
            pressure=pressure,
        )
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

    def _select_persona_variant(
        self,
        persona_variants: dict[str, dict[str, Any]],
        tension: str,
        pressure_label: str,
        emotion: str,
        pressure: int,
    ) -> str:
        best_id = next(iter(persona_variants))
        best_score = -1
        for variant_id, variant in persona_variants.items():
            score = 0
            tension_levels = set(variant.get("tensionLevels") or [])
            pressure_states = set(variant.get("pressureStates") or [])
            emotional_states = set(variant.get("emotionalStates") or [])
            if tension_levels:
                score += 3 if tension in tension_levels else -1
            if pressure_states:
                score += 2 if pressure_label in pressure_states else -1
            if emotional_states:
                score += 1 if emotion in emotional_states else -1
            min_score = variant.get("minTensionScore")
            max_score = variant.get("maxTensionScore")
            if min_score is not None:
                score += 1 if pressure >= int(min_score) else -1
            if max_score is not None:
                score += 1 if pressure <= int(max_score) else -1
            if not (tension_levels or pressure_states or emotional_states or min_score is not None or max_score is not None):
                score += 1
            if score > best_score:
                best_score = score
                best_id = variant_id
        return best_id

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
