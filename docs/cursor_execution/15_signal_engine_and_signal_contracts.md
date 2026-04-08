# 15 — Signal-Engine, Gateway-Vertrag und Erklärungsebenen

## Ziel

Ein stabiler, dokumentierter **Signal-API-Vertrag** über:

- Persistenz: `app.signals_v1`, `app.signal_explanations` (geschrieben von **signal-engine**)
- Gateway: `GET /v1/signals/recent`, `GET /v1/signals/{id}`, `GET /v1/signals/{id}/explain`, Facetten
- Dashboard: Signalliste, Signaldetail, gespeicherte Erklärung vs. deterministische Gründe vs. **Live-LLM** (separater BFF-/Operator-Pfad)

**Keine stillen Feldabweichungen** zwischen DB-Spalten, flachen Gateway-Feldern und der gruppierten Sicht `signal_view`.

## Implementierung (Repo)

| Komponente                                             | Pfad                                                                                                    |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| Vertragslogik (Gruppierung, Version, Erklärungsebenen) | `services/api-gateway/src/api_gateway/signal_contract.py`                                               |
| SQL → JSON (inkl. `signal_view`, Explain-`layers`)     | `services/api-gateway/src/api_gateway/db_dashboard_queries.py`                                          |
| Routen                                                 | `services/api-gateway/src/api_gateway/routes_signals_proxy.py`                                          |
| Dashboard-Typen                                        | `apps/dashboard/src/lib/types.ts`                                                                       |
| Signaldetail-UI                                        | `apps/dashboard/src/app/(operator)/console/signals/[id]/page.tsx`                                       |
| Fixture-Beispiel                                       | `tests/fixtures/signal_api_contract_sample.json`                                                        |
| Tests                                                  | `tests/unit/api_gateway/test_signal_contract.py`, `tests/unit/api_gateway/test_db_dashboard_queries.py` |

**Vertragsversion:** Konstante `SIGNAL_API_CONTRACT_VERSION` (aktuell `1.1.0`) — wird als `signal_contract_version` auf **Recent**, **Detail** und **Explain** ausgegeben; zusätzlich steht dieselbe Version in `signal_view.contract_version`.

## Feldgruppen (`signal_view`)

Die flachen Felder bleiben **abwärtskompatibel**. `signal_view` ist eine **read-only Gruppierung** derselben Werte (ohne neue DB-Spalten).

### Liste (`GET /v1/signals/recent` → `items[].signal_view`)

| Gruppe                 | Inhalt (Kurz)                                                                                |
| ---------------------- | -------------------------------------------------------------------------------------------- |
| `identity`             | `signal_id`, Symbol, TF, Richtung, Zeiten, `canonical_instrument_id`, `market_family`        |
| `decision_and_status`  | `signal_class`, `decision_state`, `trade_action`, Meta-Entscheidung                          |
| `strategy_and_routing` | Strategie, Playbook, Router, Exit-Familien                                                   |
| `regime`               | Marktregime, Bias, Konfidenz, Regime-Zustände, Lane                                          |
| `scores_and_leverage`  | Stärke, Wahrscheinlichkeiten, Erwartungs-Bps, Unsicherheit, Hebel-Felder                     |
| `risk_stops`           | Stop-Distanz, Budget, Qualität, Fragilität, Policy-Version                                   |
| `risk_governor`        | Live-Blocks, universelle Hard-Blocks, `live_execution_clear_for_real_money`                  |
| `execution_and_alerts` | letzte Execution, Operator-Release, Telegram, Shadow/Mirror                                  |
| `outcome`              | `outcome_badge`                                                                              |
| `deterministic_engine` | Hinweis: **keine** vollständige `reasons_json` in der Liste — nur Verweis auf Detail/Explain |

### Detail (`GET /v1/signals/{id}` → `signal_view`)

Zusätzlich zu den Listen-Gruppen (mit erweiterter `decision_and_status` inkl. `rejection_*`):

| Gruppe                    | Inhalt                                                                                                                           |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `instrument_and_metadata` | alle `instrument_*`-Kurzfelder aus dem Gateway-Payload                                                                           |
| `scoring_diagnostics`     | Ziel-Modelle, Divergenz, OOD, diverse `*_reasons_json` / Regime-Gründe                                                           |
| `portfolio`               | `portfolio_risk_synthesis_json`                                                                                                  |
| `deterministic_engine`    | `reasons_json_ref: "reasons_json"`, **shape** (Top-Level-Keys/Länge), keine Payload-Verdopplung der großen Struktur auf dem Wire |

**Korrektur Feldabgleich:** `meta_decision_action` und `meta_decision_kernel_version` werden im Detail-Payload wieder aus `app.signals_v1` ausgeliefert (zuvor fehlten sie im flachen `fetch_signal_by_id`-Ergebnis trotz `SELECT s.*`).

## Erklärungsebenen (`GET /v1/signals/{id}/explain`)

Top-Level-Felder bleiben wie bisher (`explain_short`, `explain_long_md`, `risk_warnings_json`, `stop_explain_json`, `targets_explain_json`, `reasons_json`).

Neu: **`explanation_layers`** mit fester Semantik:

| Layer                  | Quelle                           | Rolle                                                                                                                      |
| ---------------------- | -------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `persisted_narrative`  | `app.signal_explanations`        | Menschlich lesbar, deterministisch aus Templates/Regeln der signal-engine; unabhängig von Live-LLM                         |
| `deterministic_engine` | `app.signals_v1.reasons_json`    | Autoritativer Engine-Audit-Pfad; `reasons_json` in diesem Layer ist **identisch** zum Top-Level `reasons_json` der Antwort |
| `live_llm_advisory`    | separater Request (BFF/Operator) | Beratender Overlay; ersetzt weder Persistenz noch `reasons_json`                                                           |

Damit können **gespeicherte Erklärung**, **deterministische Gründe** und **Live-LLM** nebeneinander existieren, ohne sich gegenseitig zu überschreiben.

## Beispiel-Payloads (Auszug)

Vollständige flache Beispielobjekte: `tests/fixtures/signal_api_contract_sample.json` (`list_item_flat`, `detail_flat`).

**Explain (logisch):**

```json
{
  "signal_id": "…",
  "signal_contract_version": "1.1.0",
  "explain_short": "…",
  "explain_long_md": "…",
  "risk_warnings_json": [],
  "stop_explain_json": {},
  "targets_explain_json": {},
  "reasons_json": { "decision_control_flow": {} },
  "explanation_layers": {
    "persisted_narrative": {
      "source": "app.signal_explanations",
      "semantic": "human_persisted_copy"
    },
    "deterministic_engine": {
      "source": "app.signals_v1.reasons_json",
      "semantic": "engine_audit_trail"
    },
    "live_llm_advisory": {
      "separate_request": true,
      "semantic": "advisory_overlay"
    }
  }
}
```

## Nachweis HTTP (Gateway)

Voraussetzung: laufender API-Gateway, gültiger Operator-/JWT-Kontext wie in eurer Umgebung üblich.

```http
GET /v1/signals/recent?limit=5
GET /v1/signals/{signal_id}
GET /v1/signals/{signal_id}/explain
```

Erwartung: In **Recent** und **Detail** je `signal_contract_version` und `signal_view`; in **Explain** zusätzlich `explanation_layers`. Bei DB-Degradation liefert Explain weiterhin `signal_contract_version`; `explanation_layers` kann `null` sein (siehe `routes_signals_proxy`).

**Live-LLM:** nicht Teil dieser drei Routen — weiterhin z. B. Operator-BFF „Strategie-Signal erklären“ (Dashboard: `StrategySignalExplainPanel`), Snapshot bewusst **ohne** `signal_view` / `signal_contract_version`, um Duplikat zu vermeiden.

## Tests

```powershell
python -m pytest tests/unit/api_gateway/test_db_dashboard_queries.py tests/unit/api_gateway/test_signal_contract.py -q
```

## Bezug Handoff (05 / 06 / 07)

- Daten- und Persistenzkontext Signale / Erklärungen: `docs/chatgpt_handoff/05_*`
- Orchestrierung KI vs. deterministische Pfade: `docs/chatgpt_handoff/06_*`
- UX-Trennung operatorseitig (Übersicht vs. Tiefe): `docs/chatgpt_handoff/07_*`

## Offene Punkte

- `[FUTURE]` Facetten-Endpoint könnte optional `signal_contract_version` im Envelope spiegeln (derzeit nicht nötig).
- `[TECHNICAL_DEBT]` Sehr große `reasons_json`-Payloads: `signal_view` liefert nur **shape**; Clients, die nur die Gruppenköpfe brauchen, können `signal_view` nutzen; Vollbild weiterhin `reasons_json`.
