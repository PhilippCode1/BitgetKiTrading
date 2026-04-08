# Task 40 — KI-Strategie-Workflow mit Freigabe-Grenzen

## Ziel

Ein **professioneller, sicherer** Workflow: Die KI darf aus **Chart- und Signal-Kontext** Strategieentwürfe liefern (Szenarien, Parameterideen, Chart-Annotationen, Risiko- und Gültigkeitshinweise). Diese werden **persistiert**, **angezeigt** und können nach **deterministischer Prüfung** und **expliziter menschlicher Bestätigung** nur als **Protokolleintrag** für eine spätere Stufe (Paper / Shadow / Live) markiert werden — **ohne** Orderauslösung aus der LLM-Schicht.

## Architektur (End-to-End)

| Stufe         | Komponente                                                                        | Verantwortung                                                                                     |
| ------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Schema        | `shared/contracts/schemas/ai_strategy_proposal_draft.schema.json`                 | `execution_authority` = `none`; `suggested_execution_lane_hint` nicht-bindend; Pflicht-Disclaimer |
| Prompt        | `shared/prompts/tasks/ai_strategy_proposal_draft.instruction_de.txt` + Manifest   | Keine Orders, keine API-Befehle                                                                   |
| LLM           | `llm-orchestrator` `POST /llm/analyst/ai_strategy_proposal_draft`                 | Strukturierte Ausgabe + Chart-Sanitizer (wie Signal-Explain)                                      |
| Operator-HTTP | `POST /v1/llm/operator/ai-strategy-proposal-draft`                                | Nur Forward (ohne DB)                                                                             |
| Persistenz    | `app.ai_strategy_proposal_draft` (Migration `615_ai_strategy_proposal_draft.sql`) | JSON-Payload, Lifecycle, Validierungsbericht, Promotion-Protokoll                                 |
| API           | `POST /v1/operator/ai-strategy-proposal-drafts/generate-and-store`                | LLM + Insert atomar serverseitig                                                                  |
| Validierung   | `api_gateway/ai_strategy_proposal_governance.py`                                  | Verbotene Top-Level-Keys, Lane-Hint, Disclaimer-Länge                                             |
| Promotion     | `POST .../request-promotion`                                                      | Nur bei `validation_passed` + `human_acknowledged=true` — **kein** Broker-Call                    |
| UI            | Signaldetail `StrategyProposalDraftPanel`                                         | Erzeugen, Liste, Chart-Overlay, Validierung, Promotion-Protokoll                                  |
| BFF           | `apps/dashboard/src/app/api/dashboard/operator/ai-strategy-proposal-drafts/*`     | Gateway-Proxy mit Operator-Auth                                                                   |

## Finaler Freigabepfad (Soll)

1. **Entwurf erzeugen** — KI liefert strukturiertes JSON; Gateway speichert mit serverseitig erzwungenem `execution_authority: none`.
2. **Chart** — Operator legt `chart_annotations` optional auf den KI-Chart-Layer (reine Visualisierung).
3. **Deterministische Prüfung** — `validate-deterministic` schreibt `validation_passed` oder `validation_failed` + Bericht.
4. **Mensch** — Checkbox + Zielstufe wählen (Paper-Sandbox / Shadow / Live-mit-Gates).
5. **Promotion protokollieren** — Zeile erhält `promotion_requested`, Ziel und Zeitstempel — **keine** automatische Übergabe an `paper-broker`, `live-broker` oder Exchange.
6. **Reale Umsetzung** — weiterhin über bestehende Produktpfade (Gates, Runbooks, manuelle/semantische Schritte), siehe `docs/TRADING_INTEGRATION_SECURITY_MODUL_MATE.md` und `shared_py.trading_integration_contract`.

## Technischer Nachweis (Speicherung)

- Migration: `infra/migrations/postgres/615_ai_strategy_proposal_draft.sql`
- Insert: `api_gateway/db_ai_strategy_proposal_drafts.py` → Tabelle `app.ai_strategy_proposal_draft`
- Nach erfolgreichem `generate-and-store`: Antwort enthält `draft_id` und `lifecycle_status: draft`

## UI-Nachweis (Vorschläge + Chart)

- Seite: `console/signals/[id]` — Panel **Schritt 5 — KI-Strategieentwurf**
- Nach „Entwurf erzeugen & speichern“: bei vorhandenen `chart_annotations` werden diese auf den Signaldetail-Chart gelegt (gleicher Kontext wie Schritt 4)
- „Annotationen auf Chart legen“ lädt einen gespeicherten Entwurf und setzt den KI-Layer

## Tests (Freigabegrenzen)

- `tests/unit/test_ai_strategy_proposal_governance.py` — verbotene Keys, Promotion ohne Ack/ohne Validierung
- `tests/unit/api_gateway/test_ai_strategy_proposal_drafts_routes.py` — generate-and-store mit gemocktem LLM + Insert
- `apps/dashboard/src/lib/__tests__/ai-strategy-proposal-governance.test.ts` — Client-Precheck für Promotion

## Offene Punkte / [FUTURE]

- Anbindung des Promotion-Protokolls an ein formales Ticket-/Runbook-System
- Lesefilter pro Tenant/Operator-Rolle
- Optionales Sign-off zweiter Person für Live-Stufe

## [RISK]

Fehlende Migration 615 führt zu leerer Draft-Liste und 503 auf generate-and-store — UI zeigt Hinweis.
