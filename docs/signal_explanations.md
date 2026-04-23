# Signal-Erklaerungen (Prompt 14)

Deterministisches Explainability-Subsystem der **signal-engine** (ohne LLM). Alle Texte sind
template- bzw. regelbasiert und referenzieren nur vorhandene Fakten (Scores, Struktur, Drawings,
Features, News-Zeile).

## Persistenz

Tabelle `app.signal_explanations` (1:1 per `signal_id` → `app.signals_v1`), Felder:

| Spalte                 | Inhalt                                                                                  |
| ---------------------- | --------------------------------------------------------------------------------------- |
| `explain_version`      | Aus `SIGNAL_EXPLAIN_VERSION`                                                            |
| `explain_short`        | 1–2 Sätze Deutsch                                                                       |
| `explain_long_md`      | Markdown mit festen Abschnitten                                                         |
| `explain_long_json`    | Strukturiert, validiert gegen `shared/contracts/schemas/signal_explanation.schema.json` |
| `risk_warnings_json`   | Regelbasierte Warnungen                                                                 |
| `stop_explain_json`    | Stop inkl. Trigger-Typ (Mark vs Fill)                                                   |
| `targets_explain_json` | Gestufte Zielzonen aus Drawings                                                         |

Bei jeder Signal-Generierung (`evaluate_and_persist`) wird nach dem Insert in `signals_v1` ein
Upsert in `signal_explanations` ausgeführt.

## API

- `GET /signals/latest?symbol=&timeframe=` — Signal inkl. `explain_short`, `explain_long` (Alias für
  `explain_long_md`), `explain_long_json`, `explain_version`, `risk_warnings`, `stop_explain_json`,
  `targets_explain_json` (sofern JOIN eine Zeile liefert).
- `GET /signals/recent?...&include_explain_md=false` (Default) — pro Eintrag Kurzinfos; ohne großes
  Markdown/JSON (`explain_long_md`, `explain_long`, `explain_long_json` werden entfernt).
- `GET /signals/by-id/{signal_id}/explain` oder `GET /signals/{signal_id}/explain` — Abschnitte
  (`sections` aus `explain_long_json`), `risk_warnings`, Stop-/Target-Begründung, vollständiges
  Markdown/JSON.

## Stop-Trigger (Mark vs Fill)

Konfiguration: `SIGNAL_DEFAULT_STOP_TRIGGER_TYPE` (`mark_price` | `fill_price`), bis ein echtes
Feld am Signal existiert.

- **mark_price**: Stop triggert auf Mark Price (Bitget `triggerType=mark_price`; robuster gegen
  kurze Spikes).
- **fill_price**: Stop triggert auf Fill/Trade-Preis (schneller, noise-anfälliger).

## Risk-Warning-Codes

| Code                     | Schwere | Bedingung                                                                       |
| ------------------------ | ------- | ------------------------------------------------------------------------------- |
| `STALE_DATA`             | high    | Feature `computed_ts_ms` zu alt vs. `analysis_ts_ms` (`SIGNAL_MAX_DATA_AGE_MS`) |
| `STOP_TOO_TIGHT_FOR_ATR` | medium  | Stop-Distanz &lt; `STOP_MIN_ATR_MULT * ATR(14)`                                 |
| `CONFLICT_HIGH_TF`       | high    | 1H/4H `trend_dir` widerspricht Long/Short                                       |
| `BREAKOUT_FALSE_RISK`    | medium  | jüngstes Struktur-Event `FALSE_BREAKOUT`                                        |
| `LOW_RR`                 | medium  | `reward_risk_ratio` &lt; `SIGNAL_MIN_REWARD_RISK`                               |
| `NEWS_SHOCK_AGAINST`     | high    | hohe Relevanz + Sentiment gegen die Richtung (Schwellen wie Scoring)            |
| `REGIME_SHOCK`           | high    | Regime-Klassifikator liefert `market_regime=shock`                              |

Jede Warnung: `{ "code", "severity", "message", "evidence" }`.

Prompt 13 ergaenzt die Input-Gates der Signal-Engine um struktur-, drawing- und
news-spezifische Alterspruefungen (`SIGNAL_MAX_STRUCTURE_AGE_MS`,
`SIGNAL_MAX_DRAWING_AGE_MS`, `SIGNAL_MAX_NEWS_AGE_MS`) sowie den Shared-
Feature-Schema-Hash in `source_snapshot_json`.

Prompt 14 erweitert `source_snapshot_json.feature_snapshot.primary_tf` um
Cost-/Microstructure-Felder wie `spread_bps`, `execution_cost_bps`,
`funding_rate_bps`, `open_interest_change_pct` und `*_age_ms`. Fehlende oder
fallback-basierte Liquidity-Kontexte tauchen dort explizit als Data-Issues wie
`liquidity_context_fallback`, `missing_funding_context` oder
`stale_orderbook_feature_data` auf.

Prompt 16 erweitert das Signal-Audit um eine kanonische Regime-Sicht:

- `market_regime` (`trend|chop|compression|breakout|shock|dislocation`)
- `regime_bias`
- `regime_confidence_0_1`
- `regime_reasons_json`
- `source_snapshot_json.regime_snapshot`
- `regime_state` (family-aware Feinregime, siehe `docs/regime_engine.md`)
- `regime_transition_state`, `regime_persistence_bars`, `regime_transition_reasons_json`

Damit ist fuer jedes Signal nachvollziehbar, ob es im Trend-, Chop-,
Kompressions-, Breakout- oder Shock-Kontext entstanden ist und welche Fakten
die Baseline-Regime-Klassifikation getragen haben.

## Regime-Kontext

`explain_long_json.sections.regime_context` buendelt die fuer Operatoren relevanten
Regime-Fakten aus `signals_v1` und `source_snapshot_json.regime_snapshot`:

- `regime_state`, `regime_substate`, `regime_transition_state`
- `regime_persistence_bars`, `regime_policy_version`
- `raw_regime_state`, `pending_regime_state` (Hysterese/Audit)
- `regime_engine_version`, `regime_ontology_version`

## Playbook-Kontext

Seit dem Playbook-Register enthaelt `explain_long_json.sections` zusaetzlich
`playbook_context`.

Dort liegen unter anderem:

- `playbook_id`
- `playbook_family`
- `decision_mode` (`selected` oder `playbookless`)
- `registry_version`
- `strategy_name`
- `selection_reasons`
- `benchmark_rule_ids`
- `anti_pattern_hits`
- `blacklist_hits`
- `counterfactual_candidates`

Damit sieht der Operator nicht nur **was** entschieden wurde, sondern auch
welcher fachliche Playbook-Rahmen die Entscheidung getragen oder blockiert hat.

## Foundation Model (TimesFM, Prompt 9)

Wenn der Signal-Pipeline-Kontext ein **TimesFM**-Ergebnis liefert, kann
`source_snapshot_json.foundation_model_tsfm` (oder das gleiche Objekt als
`ExplainInput.foundation_model_tsfm`) gesetzt werden. Die Explain-Engine
blendet es dann unter `explain_long_json.sections.decision_pipeline.foundation_model_tsfm`
sowie im Markdown unter **Endentscheid → Foundation Model (TimesFM)** ein.

Empfohlene Felder (frei erweiterbar, `additionalProperties`):

- `summary_de` — Kurztext, z. B. dass die Bewertung auf **Zero-Shot Pattern Recognition**
  eines **Foundation Models** (TimesFM) basiert, inkl. Konfidenz und Horizont.
- `model_id`, `confidence_0_1`, `directional_bias` — faktenbasierte Metadaten.

Die Kern-Scoring-Pipeline der Signal-Engine bleibt deterministisch; das
Foundation Model erscheint nur als **erklaerbarer Zusatzkontext**, sobald
Upstream-Komponenten ihn befuellen.

## Versionierung

- `SIGNAL_EXPLAIN_VERSION` wird in DB und in `explain_long_json.explain_version` gespeichert.
- JSON-Schema-Root: `schema_version` = `"1.0"` (siehe Contract-Datei).

## Sicherheit

Erklärungen und Logs enthalten keine Secrets und keine vollständigen ENV-Dumps.
