from __future__ import annotations

from typing import Any


_FAKE_OPERATOR_EXPLAIN_DE = (
    "[TEST-PROVIDER — kein OpenAI-Aufruf] Deterministische Smoke-Antwort. "
    "Für echtes Modell: LLM_USE_FAKE_PROVIDER=false und OPENAI_API_KEY am llm-orchestrator setzen. "
    "Diese Antwort erfüllt das Operator-Explain-JSON-Schema zur End-to-End-Verifikation."
)

_FAKE_OPERATOR_NOTE_DE = (
    "Nur technischer Testmodus; keine operative Handlungsempfehlung und keine Markteinschätzung."
)

_FAKE_STRATEGY_SIGNAL_EXPLAIN_DE = (
    "[TEST-PROVIDER — kein OpenAI-Aufruf] Deterministische Strategie-Signal-Erklaerung fuer E2E. "
    "Fuer echtes Modell: LLM_USE_FAKE_PROVIDER=false und OPENAI_API_KEY am llm-orchestrator setzen."
)

_FAKE_ASSIST_REPLY_DE = (
    "[TEST-PROVIDER — kein OpenAI-Aufruf] Assistenzschicht Smoke: mehrstufiger Dialog ohne "
    "Orderhoheit. Fuer echtes Modell: LLM_USE_FAKE_PROVIDER=false und OPENAI_API_KEY setzen."
)


class FakeProvider:
    name = "fake"
    default_model = "fake-model"

    def generate_structured(
        self,
        schema_json: dict[str, Any],
        prompt: str,
        *,
        temperature: float,
        timeout_ms: int,
        model: str | None = None,
        system_instructions_de: str | None = None,
    ) -> dict[str, Any]:
        del temperature, timeout_ms, model, system_instructions_de
        sid = str(schema_json.get("$id") or "").lower()
        # Explizit gekennzeichnete Antwort statt generischem \"fake\"-String — fuer UI/E2E nachvollziehbar.
        if "operator-explain" in sid:
            return {
                "schema_version": "1.0",
                "execution_authority": "none",
                "explanation_de": _FAKE_OPERATOR_EXPLAIN_DE,
                "referenced_artifacts_de": [],
                "non_authoritative_note_de": _FAKE_OPERATOR_NOTE_DE,
            }
        if "safety-incident-diagnosis" in sid:
            return {
                "schema_version": "1.0",
                "execution_authority": "none",
                "incident_summary_de": (
                    "[TEST-PROVIDER — kein OpenAI-Aufruf] Deterministische "
                    "Sicherheits-Diagnose: Health/Alerts-Kontext wurde nur strukturell "
                    "beachtet; im Produktionsmodell folgen detailreichere Ursachen und Schritte."
                ),
                "root_causes_de": [
                    "Testmodus: Keine Live-Analyse — Platzhalter-Ursache fuer Schema-Regression.",
                ],
                "affected_services_de": [
                    "api-gateway (Beispiel)",
                    "llm-orchestrator (Beispiel)",
                ],
                "affected_repo_paths_de": [
                    "services/api-gateway/src/api_gateway/routes_system_health.py",
                    "services/llm-orchestrator/src/llm_orchestrator/service.py",
                ],
                "recommended_next_steps_de": [
                    "Pruefe /v1/system/health und offene Monitor-Alerts manuell.",
                    "Vergleiche Logs mit X-Request-ID aus dem fehlgeschlagenen Aufruf.",
                ],
                "proposed_commands_de": [
                    "Beispiel (nicht ausfuehren ohne Review): curl -sSf $GATEWAY/v1/system/health",
                ],
                "env_or_config_hints_de": [
                    "DATABASE_URL",
                    "LLM_USE_FAKE_PROVIDER",
                    "OPENAI_API_KEY am Orchestrator",
                ],
                "non_authoritative_note_de": _FAKE_OPERATOR_NOTE_DE,
                "separation_note_de": (
                    "Diese KI fuehrt keine Befehle aus und aendert keine Limits, Broker- "
                    "oder Order-Einstellungen — nur Erklaerung und Vorschlagslisten."
                ),
            }
        if "strategy-signal-explain" in sid:
            return {
                "schema_version": "1.0",
                "execution_authority": "none",
                "strategy_explanation_de": _FAKE_STRATEGY_SIGNAL_EXPLAIN_DE,
                "risk_and_caveats_de": (
                    "Testmodus: Snapshot kann unvollstaendig sein; keine Live-Marktdaten aus dem Provider."
                ),
                "referenced_input_keys_de": [],
                "non_authoritative_note_de": _FAKE_OPERATOR_NOTE_DE,
                "chart_annotations": {
                    "schema_version": "1.0",
                    "chart_notes_de": [
                        {
                            "text": (
                                "[TEST-PROVIDER] KI-Chart-Layer ist aktiv; im Fake-Modus werden keine "
                                "echten Preislinien erzeugt — nur diese Notiz zur E2E-Struktur."
                            )
                        },
                    ],
                },
            }
        if "ai-strategy-proposal-draft" in sid:
            return {
                "schema_version": "1.0",
                "execution_authority": "none",
                "strategy_explanation_de": (
                    "[TEST-PROVIDER] KI-Strategie-Entwurf: keine Orders, nur strukturierter Text."
                ),
                "scenario_variants_de": [
                    "Basis: Range bleibt intakt bis Datenlage sich ändert.",
                    "Stress: schnellerer Bruch bei schlechter Datenqualität.",
                ],
                "parameter_ideas_de": [
                    "Stop-Abstand nur als Diskussionsgröße — nicht automatisch setzen.",
                ],
                "validity_and_assumptions_de": (
                    "Gültig solange der Snapshot repräsentativ ist; kein Echtzeit-Marktversprechen."
                ),
                "risk_and_caveats_de": "Fake-Provider: keine echte Modelllogik.",
                "referenced_input_keys_de": [],
                "non_authoritative_note_de": _FAKE_OPERATOR_NOTE_DE,
                "promotion_disclaimer_de": (
                    "Dies ist kein Orderauftrag. Paper/Shadow/Live nur nach menschlicher Freigabe "
                    "und Produkt-Gates — siehe Trading-Integrationsvertrag."
                ),
                "suggested_execution_lane_hint": "paper_sandbox",
                "chart_annotations": {
                    "schema_version": "1.0",
                    "chart_notes_de": [
                        {
                            "text": (
                                "[TEST-PROVIDER] Entwurfs-Chart-Notiz — echte Geometrie nur mit OpenAI-Pfad."
                            )
                        },
                    ],
                },
            }
        if "assistant-turn" in sid:
            base = _fake_object_from_schema(schema_json)
            base.update(
                {
                    "assistant_reply_de": _FAKE_ASSIST_REPLY_DE,
                    "referenced_context_keys_de": [],
                    "retrieval_citations_de": ["[TEST-PROVIDER] Retrieval-Stub"],
                    "trade_separation_note_de": (
                        "Diese KI fuehrt keine Trades aus und aendert keine Limits — nur Erklaerung."
                    ),
                    "non_authoritative_note_de": _FAKE_OPERATOR_NOTE_DE,
                }
            )
            return base
        del prompt
        return _fake_object_from_schema(schema_json)


def _fake_object_from_schema(schema: dict[str, Any]) -> Any:
    if not isinstance(schema, dict):
        return None
    if "const" in schema:
        return schema["const"]
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties") or {}
        req = schema.get("required") or []
        out: dict[str, Any] = {}
        for key in req:
            out[key] = _fake_object_from_schema(props.get(key, {}))
        for key, sub in props.items():
            if key not in out:
                out[key] = _fake_object_from_schema(sub)
        return out
    if t == "array":
        items = schema.get("items") or {}
        if schema.get("minItems", 0) > 0:
            return [_fake_object_from_schema(items)]
        return []
    if t == "string":
        return "fake"
    if t == "integer":
        lo = schema.get("minimum", 0)
        return int(lo)
    if t == "number":
        return float(schema.get("minimum", 0.0))
    if t == "boolean":
        return True
    if t == "null":
        return None
    return None
