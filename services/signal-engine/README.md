# signal-engine

Deterministisches Scoring aus Feature-, Struktur- und Drawing-Daten; persistiert in
`app.signals_v1`, Erklaerungen in `app.signal_explanations`, publiziert `events:signal_created`.

## Start

```bash
cd services/signal-engine
python -m venv .venv
pip install -e .
set DATABASE_URL=...
set REDIS_URL=...
python -m signal_engine.main
```

## Trigger

Worker konsumiert **`events:drawing_updated`** (nach Drawing-Engine).

## Modellvertrag / Data Quality

- Feature-Inputs werden as-of `analysis_ts_ms` geladen und gegen den Shared-Contract
  aus `shared_py.model_contracts` validiert.
- `source_snapshot_json` enthaelt den Feature-Snapshot ueber alle Modell-Timeframes,
  Schema-Hashes und das Ergebnis des Input-Quality-Gates.
- Relevante Gates: `SIGNAL_MAX_DATA_AGE_MS`, `SIGNAL_MAX_STRUCTURE_AGE_MS`,
  `SIGNAL_MAX_DRAWING_AGE_MS`, `SIGNAL_MAX_NEWS_AGE_MS`.
- Prompt 14 erweitert die Primary-Feature-Gates um Orderbook-/Funding-/OI-Kontext:
  `SIGNAL_MAX_ORDERBOOK_AGE_MS`, `SIGNAL_MAX_FUNDING_FEATURE_AGE_MS`,
  `SIGNAL_MAX_OPEN_INTEREST_AGE_MS`, `SIGNAL_MAX_SPREAD_BPS`,
  `SIGNAL_MAX_EXECUTION_COST_BPS`, `SIGNAL_MAX_ADVERSE_FUNDING_BPS`.
- `liquidity_source != orderbook_levels`, fehlende Slippage-Proxies oder stale
  `*_age_ms` fuehren nicht zu stillen Defaults, sondern zu echten
  `data_issues` und harten Rejection-Pfaden.
- `score_risk()` und `apply_rejections()` nutzen jetzt `spread_bps`,
  `execution_cost_bps`, `funding_cost_bps_window`, `open_interest_change_pct`
  und den Fallback-Status direkt.
- Prompt 16 fuehrt einen kanonischen Regime-Klassifikator ein:
  `trend`, `chop`, `compression`, `breakout`, `shock`.
- Persistierte Signal-Felder fuer Regime sind jetzt `market_regime`,
  `regime_bias`, `regime_confidence_0_1` und `regime_reasons_json`.
- `source_snapshot_json.regime_snapshot` haelt die konkreten Struktur-/News-/
  Volatilitaetsfakten fuer Audit und Dashboard bereit.
- `score_risk()` und `classification.py` konsumieren das Regime direkt, damit
  Shock-/Chop-/Breakout-Kontexte nicht nur sichtbar, sondern fachlich wirksam
  sind.
- Prompt 17 fuehrt zusaetzlich ein kalibriertes Meta-Label-Output `take_trade_prob`
  ein. Die Heuristik `probability_0_1` bleibt als deterministischer Scoring-Wert
  erhalten; `take_trade_prob` ist dagegen die gelernte Wahrscheinlichkeit fuer
  `take_trade_label`.
- Persistierte Meta-Model-Felder pro Signal sind jetzt `take_trade_prob`,
  `take_trade_model_version`, `take_trade_model_run_id` und
  `take_trade_calibration_method`.
- `source_snapshot_json.take_trade_model` und `model_contract.active_models`
  verweisen auf das promotete Modell aus `app.model_runs`, damit Audit und
  spaetere Risk-/Leverage-Konsumenten denselben Modellstand sehen.
- Prompt 18 fuehrt zusaetzlich drei getrennte Regressionsoutputs ein:
  `expected_return_bps`, `expected_mae_bps` und `expected_mfe_bps`.
- Diese Projektionen werden pro Signal in `app.signals_v1` persistiert und in
  `target_projection_models_json` bzw. `source_snapshot_json.target_projection_models`
  mit Version/Run-ID/Scaling-Method dokumentiert.
- `source_snapshot_json.target_projection_summary` fasst Edge, adverse excursion
  und reward-to-adverse-Verhaeltnis fuer Audit- und Replay-Pfade zusammen.
- Der `paper-broker` nutzt die persistierten Projektionen jetzt direkt fuer
  Auto-Trade-Gates und die Freigabe einer Default-Leverage > 7x.
- Prompt 19 fuehrt zusaetzlich eine explizite Produktions-Inference-Policy ein:
  `model_uncertainty_0_1`, `model_ood_score_0_1`, `model_ood_alert`,
  `shadow_divergence_0_1`, `abstention_reasons_json` und `trade_action`.
- Oberhalb von `MODEL_MAX_UNCERTAINTY` oder bei einem OOD-Alarm wird das Signal
  deterministisch auf `trade_action=do_not_trade`, `decision_state=rejected` und
  `signal_class=warnung` gesetzt.
- `source_snapshot_json.uncertainty_assessment` dokumentiert die Komponenten
  (Data-Quality, Regime, Modellkonfidenz, Shadow-Divergenz, OOD) fuer Audit,
  Replay und spaetere Risk-Analysen.
- Prompt 20 fuehrt darauf aufbauend einen Hybrid-Entscheider ein, der den
  deterministischen Safety-Floor, Regime, `take_trade_prob`,
  `expected_return_bps`/`expected_mae_bps`/`expected_mfe_bps` und die
  Unsicherheits-/Abstention-Signale zu einer finalen Entscheidung verdichtet.
- Finale Hybrid-Outputs pro Signal sind jetzt zusaetzlich
  `decision_confidence_0_1`, `decision_policy_version` und
  `recommended_leverage`.
- Prompt 21 erweitert den Hybrid-Pfad um einen regelbasierten Integer-
  Leverage-Allocator. Er erzeugt pro Signal `allowed_leverage`,
  `recommended_leverage`, `leverage_policy_version` und
  `leverage_cap_reasons_json`.
- Der signal-seitige `model_cap` nutzt jetzt Edge, Uncertainty, Volatilitaet,
  Spread, Slippage, Funding, Orderbook-Depth und Data-Quality aus
  `source_snapshot_json.feature_snapshot`.
- Wenn der signal-seitige `allowed_leverage` unter `RISK_ALLOWED_LEVERAGE_MIN`
  faellt, wird das Signal deterministisch auf `trade_action=do_not_trade`
  heruntergestuft.
- `source_snapshot_json.hybrid_decision` und
  `signal_components_history_json[layer=hybrid_decision]` halten die finalen
  Hybrid-Faktoren, Gates und den primaeren Abstention-Grund fuer Audit/Replay
  fest.
- Der Hybrid-Entscheider kann die Safety-Layer nicht ueberstimmen: vorhandene
  `decision_state!=accepted`, `signal_class=warnung`, `trade_action=do_not_trade`
  oder `market_regime=shock` bleiben harte No-Trade-Floors.

## API

- `GET /health`
- `GET /signals/latest?symbol=<example_symbol>&timeframe=1m`
- `GET /signals/recent?symbol=<example_symbol>&timeframe=1m&limit=50`
- `GET /signals/by-id/{uuid}`
- `GET /signals/by-id/{uuid}/explain` oder `GET /signals/{uuid}/explain` — Abschnitte, Markdown, Risiko-Warnungen
- Antwortfelder bei `latest` (JOIN): `explain_short`, `explain_long` / `explain_long_md`,
  `explain_long_json`, `explain_version`, `risk_warnings`, …
- `GET /signals/recent?...&include_explain_md=true|false` (Default: ohne langes Markdown/JSON)

Siehe `docs/signal_engine.md`, `docs/scoring_model_v1.md`, `docs/signal_explanations.md`.
