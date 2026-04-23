from __future__ import annotations

import copy
import logging
from typing import Any

from llm_orchestrator.validation.schema_validate import (
    SchemaValidationError,
    validate_against_schema,
)

logger = logging.getLogger("llm_orchestrator.validation.structured_fallback")

# Explizit nutzer-/dashboard-sichtbar, guardrail-sicher.
FALLBACK_TEXT_DE = "Antwort konnte nicht strukturiert generiert werden."

NOTE_NON_AUTH_DE = (
    "Diese KI erteilt hier keine Anweisung für Order/Limits und bewertet keinen Markt verbindlich. "
    "Dieser Eintrag stammt aus technischem Struktur-Fallback."
)


def _schema_id_key(schema: dict[str, Any]) -> str:
    return str(schema.get("$id") or "").lower()


def _resolve_ref(ref: str, root: dict[str, Any]) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise KeyError(f"Unsupported JSON Schema $ref: {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    if not isinstance(node, dict):
        raise TypeError(f"Ref {ref!r} does not point to an object schema")
    return node


def _synthesize_minimal(  # noqa: PLR0911, PLR0912
    sub: dict[str, Any], root: dict[str, Any], string_default: str, depth: int
) -> Any:
    if depth <= 0:
        return string_default
    s = sub
    if not isinstance(s, dict):
        return string_default
    if "$ref" in s:
        return _synthesize_minimal(
            _resolve_ref(str(s["$ref"]), root), root, string_default, depth - 1
        )
    if "const" in s:
        return copy.deepcopy(s["const"])
    enums = s.get("enum")
    if isinstance(enums, list) and enums:
        return copy.deepcopy(enums[0])
    one = s.get("oneOf")
    if isinstance(one, list) and one:
        for br in one:
            if not isinstance(br, dict):
                continue
            if br.get("type") == "null":
                continue
            return _synthesize_minimal(
                br, root, string_default, depth - 1
            )
    any_of = s.get("anyOf")
    if isinstance(any_of, list) and any_of and isinstance(any_of[0], dict):
        return _synthesize_minimal(
            any_of[0], root, string_default, depth - 1
        )
    t = s.get("type")
    if t == "object" or (t is None and isinstance(s.get("required"), list)):
        props: dict[str, Any] = s.get("properties") or {}
        req: list[str] = list(s.get("required") or [])
        out: dict[str, Any] = {}
        for k in req:
            p = props.get(k) if k in props else {"type": "string"}
            out[k] = _synthesize_minimal(
                p if isinstance(p, dict) else {"type": "string"},
                root,
                string_default,
                depth - 1,
            )
        return out
    if t == "array":
        n = int(s.get("minItems", 0) or 0)
        items = s.get("items")
        if not isinstance(items, dict):
            if n > 0:
                return [string_default] * n
            return []
        if n <= 0:
            return []
        return [
            _synthesize_minimal(items, root, string_default, depth - 1) for _ in range(n)
        ]
    if t == "string":
        mx = s.get("maxLength")
        tval = string_default
        if isinstance(mx, int) and mx > 0 and len(tval) > mx:
            tval = tval[:mx]
        return tval
    if t == "integer":
        lo = s.get("minimum")
        if isinstance(lo, (int, float)):
            return int(lo)
        return 0
    if t in ("number",):
        lo = s.get("minimum")
        if isinstance(lo, (int, float)):
            return float(lo)
        return 0.0
    if t == "boolean":
        return False
    if t == "null":
        return None
    if t is None and "properties" in s and isinstance(s.get("required"), list):
        return _synthesize_minimal({**s, "type": "object"}, root, string_default, depth)
    return string_default


def _fallback_by_known_id(
    key: str,
    *,
    fallback_binds: dict[str, Any],
) -> dict[str, Any] | None:
    m = f"{FALLBACK_TEXT_DE} (Schema-Fallback, keine Live-KI-Formatierung)."

    if "news-summary" in key:
        return {
            "schema_version": "1.0",
            "headline_de": m,
            "summary_de": f"{FALLBACK_TEXT_DE} {NOTE_NON_AUTH_DE}",
            "relevance_score_0_100": 0,
            "sentiment_neg1_to_1": 0.0,
            "impact_keywords": [FALLBACK_TEXT_DE],
            "entities_mentioned": ["—"],
            "confidence_0_1": 0.0,
        }
    if "analyst-hypotheses" in key:
        return {
            "schema_version": "1.0",
            "hypotheses": [
                {
                    "statement_de": f"{FALLBACK_TEXT_DE} (Platzhalter, nicht inhaltlich bewertet).",
                    "corroborates_direction": "neutral",
                    "confidence_0_1": 0.0,
                    "disconfirming_evidence_de": "Nicht bewertbar: valide KI-Strukturabgabe fehlt.",
                }
            ],
            "chief_risk_de": f"{FALLBACK_TEXT_DE} (kein Risikojudgement).",
            "null_hypothesis_de": "Nicht bewertbar, da keine valide KI-Strukturabgabe empfangen wurde.",
            "confidence_0_1": 0.0,
        }
    if "analyst-context-classification" in key:
        return {
            "schema_version": "1.0",
            "primary_bucket": "unknown",
            "secondary_buckets": ["unknown"],
            "conflict_with_pure_technical_de": f"{FALLBACK_TEXT_DE} (Klassifikation unbestimmt).",
            "suggested_smc_facets_hints": [FALLBACK_TEXT_DE],
            "confidence_0_1": 0.0,
        }
    if "post-trade-review" in key:
        return {
            "schema_version": "1.0",
            "outcome_vs_plan_de": f"{FALLBACK_TEXT_DE} (kein inhaltliches Post-Trade-Review).",
            "lessons_de": [f"{FALLBACK_TEXT_DE} (kein verwertbares KI-JSON)."],
            "what_worked_de": "Nicht bewertbar: kein valider strukturierter Text.",
            "what_failed_de": f"{FALLBACK_TEXT_DE}",
            "bias_check_de": "Nicht bewertbar: keine gültigen Modelltexte empfangen.",
            "review_confidence_0_1": 0.0,
        }
    if "operator-explain" in key:
        return {
            "schema_version": "1.0",
            "execution_authority": "none",
            "explanation_de": f"{FALLBACK_TEXT_DE} {NOTE_NON_AUTH_DE}",
            "referenced_artifacts_de": [FALLBACK_TEXT_DE],
            "non_authoritative_note_de": NOTE_NON_AUTH_DE,
        }
    if "safety-incident-diagnosis" in key:
        return {
            "schema_version": "1.0",
            "execution_authority": "none",
            "incident_summary_de": f"{FALLBACK_TEXT_DE} (keine inhaltliche Diagnose). {NOTE_NON_AUTH_DE}",
            "root_causes_de": [FALLBACK_TEXT_DE],
            "affected_services_de": ["(unbestimmt)"],
            "affected_repo_paths_de": ["(unbestimmt)"],
            "recommended_next_steps_de": [f"{FALLBACK_TEXT_DE} (manuelle Sichtprüfung empfohlen)."],
            "proposed_commands_de": ["(keine Befehle; nur manuelle Prüfung)"],
            "env_or_config_hints_de": [FALLBACK_TEXT_DE],
            "non_authoritative_note_de": NOTE_NON_AUTH_DE,
            "separation_note_de": "Keine KI-Order- oder Limit-Änderung; nur als Lesetext.",
        }
    if "strategy-signal-explain" in key:
        return {
            "schema_version": "1.0",
            "execution_authority": "none",
            "strategy_explanation_de": f"{FALLBACK_TEXT_DE} {NOTE_NON_AUTH_DE}",
            "risk_and_caveats_de": f"{FALLBACK_TEXT_DE} (kein Modell-Detail).",
            "referenced_input_keys_de": [],
            "non_authoritative_note_de": NOTE_NON_AUTH_DE,
        }
    if "ai-strategy-proposal-draft" in key:
        return {
            "schema_version": "1.0",
            "execution_authority": "none",
            "strategy_explanation_de": f"{FALLBACK_TEXT_DE} {NOTE_NON_AUTH_DE}",
            "scenario_variants_de": [FALLBACK_TEXT_DE],
            "parameter_ideas_de": [FALLBACK_TEXT_DE],
            "validity_and_assumptions_de": "Nicht bestimmbar, da keine valide KI-Strukturabgabe.",
            "risk_and_caveats_de": f"{FALLBACK_TEXT_DE}",
            "referenced_input_keys_de": [],
            "non_authoritative_note_de": NOTE_NON_AUTH_DE,
            "promotion_disclaimer_de": "Kein Order- oder Systemauftrag; manuelle Prüfung nötig.",
            "suggested_execution_lane_hint": "none",
        }
    if "strategy-journal-summary" in key:
        return {
            "schema_version": "1.0",
            "period_label_de": "(unbestimmt)",
            "themes_de": [FALLBACK_TEXT_DE],
            "playbook_performance_hints_de": f"{FALLBACK_TEXT_DE} (keine Auswertung).",
            "risk_events_de": [FALLBACK_TEXT_DE],
            "suggested_operator_followups_de": [f"{FALLBACK_TEXT_DE} (keine inhaltlichen Vorschläge)."],
            "summary_confidence_0_1": 0.0,
        }
    if "assistant-turn" in key:
        role = (fallback_binds.get("assist_role_echo") or "").strip() or "unknown"
        return {
            "schema_version": "1.0",
            "execution_authority": "none",
            "assist_role_echo": role,
            "assistant_reply_de": f"{FALLBACK_TEXT_DE} {NOTE_NON_AUTH_DE}",
            "referenced_context_keys_de": [FALLBACK_TEXT_DE],
            "retrieval_citations_de": ["(keine — Struktur-Fallback)"],
            "trade_separation_note_de": "Diese KI führt aus dieser Antwort heraus keine Trades aus und ändert keine Limits.",
            "non_authoritative_note_de": NOTE_NON_AUTH_DE,
        }
    return None


def build_structured_fallback(
    schema_json: dict[str, Any],
    *,
    task_type: str | None,
    last_schema_error: SchemaValidationError,
    fallback_binds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if task_type:
        logger.debug("build_structured_fallback task_type=%s", task_type)
    binds: dict[str, Any] = dict(fallback_binds or {})
    key = _schema_id_key(schema_json)
    err_preview = (last_schema_error.errors or [])[:3]

    cand = _fallback_by_known_id(key, fallback_binds=binds)
    if isinstance(cand, dict):
        try:
            validate_against_schema(schema_json, cand)
        except SchemaValidationError as ve:
            logger.warning(
                "known structured fallback widerspricht dem Schema: id=%s err=%s (preview %s)",
                key,
                ve,
                err_preview,
            )
        else:
            return cand

    msg = f"{FALLBACK_TEXT_DE} (generischer Schema-Aufbau) {NOTE_NON_AUTH_DE}"
    try:
        gen = _synthesize_minimal(schema_json, schema_json, string_default=msg, depth=36)
    except (KeyError, TypeError, RecursionError, ValueError) as exc:
        raise RuntimeError(
            f"strukturierter Fallback: Synthese abgebrochen: {exc!s}"
        ) from exc
    if not isinstance(gen, dict):
        raise RuntimeError("strukturierter Fallback: Synthese liefert kein Objekt")
    validate_against_schema(schema_json, gen)
    return gen
