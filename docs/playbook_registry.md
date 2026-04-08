# Playbook-Register

## Ziel

Das Playbook-Register uebersetzt unscharfes Strategie-Allgemeinwissen in eine
deterministische Fachbibliothek. Es ist **kein** ML-Modell und **keine**
Order-Regelmaschine, sondern ein versionierter Katalog fuer:

- Spezialisten-Routing
- Benchmarking von Strategie-Familien
- Explainability
- Counterfactual-Kandidaten
- explizite Anti-Pattern- und Blacklist-Pruefungen

Quelle der Wahrheit im Code: `shared_py.playbook_registry`

## Registry-Vertrag

- `PLAYBOOK_REGISTRY_VERSION`
- `PLAYBOOK_REGISTRY_HASH`
- `playbook_registry_descriptor()`

Jeder Eintrag enthaelt mindestens:

- `playbook_id`
- `playbook_family`
- Zielmaerkte / `target_market_families`
- Regime-Eignung / `regime_suitability`
- `invalid_contexts`
- `preferred_stop_families`
- `exit_families`
- Mindestliquiditaet (`max_spread_bps`, `max_execution_cost_bps`,
  `min_depth_to_bar_volume_ratio`, Quality-Schwellen)
- `preferred_timeframes`
- `benchmark_rules`
- `anti_patterns`
- `blacklist_criteria`
- `counterfactual_candidates`

## Abgedeckte Playbook-Familien

- `trend_continuation`
- `breakout`
- `mean_reversion`
- `volatility_compression_expansion`
- `liquidity_sweep`
- `pullback`
- `range_rotation`
- `carry_funding`
- `news_shock`
- `session_open`
- `time_window_effect`

## Runtime-Bindung

Die Signal-Engine bindet Entscheidungen explizit an Playbooks:

- Top-Level in `app.signals_v1` / `signal_model_output`:
  - `playbook_id`
  - `playbook_family`
  - `playbook_decision_mode`
  - `playbook_registry_version`
  - optional `strategy_name`
- Detailtiefe in `source_snapshot_json.playbook_context`
- Explain-/Audit-Sicht in `reasons_json.playbook`

`playbook_decision_mode`:

- `selected`: ein registriertes Playbook wurde aktiv zugeordnet
- `playbookless`: es gab bewusst kein tragfaehiges Playbook; der Grund steht in
  `playbookless_reason`

Institutioneller Guardrail:

- `allow_trade` ohne passende Playbook-Auswahl wird im Spezialisten-Router auf
  `do_not_trade` zurueckgesetzt
- Blacklist-Kriterien blockieren ebenfalls hart

## Anti-Pattern vs. Blacklist

- `anti_pattern_hits`: bekannte schlechte Konstellationen, die die Eignung
  verschlechtern und in Erklaerung/Counterfactual sichtbar bleiben
- `blacklist_hits`: harte Ausschlusskriterien; fuehren im Router zu
  `do_not_trade`

Typische Blacklist-Klassen:

- `feature_quality_degraded`
- `liquidity_below_hard_floor`
- `missing_futures_context`

## Benchmarking

Jedes Playbook traegt `benchmark_rule_ids`. Dadurch koennen spaetere Analytics
und Backtests nicht nur nach `strategy_name`, sondern nach **Playbook-Familie**
und deren registrierten Vergleichsregeln ausgewertet werden.

Die eigentlichen Backtest-/Learning-Pipelines bleiben getrennt:

- Playbooks = fachlicher Katalog
- Strategien im `learn`-Schema = Lifecycle/Promotion
- Modell-Registry V2 = ML-Champions/Challenger

## Counterfactuals

Die Runtime haengt `counterfactual_candidates` an den Playbook-Kontext an. Das
ist absichtlich kein zweites Entscheidungssystem, sondern eine strukturierte
Liste naheliegender Alternativen fuer Explainability, Replay und spaetere
Benchmark-Auswertung.
