# Scoring-Modell V1 (`SIGNAL_SCORING_MODEL_VERSION`)

## Gewichtung (Composite)

Gewichteter Roh-Composite (vor Rejection):

| Schicht         | ENV-Gewicht (Default) | Modul                      |
| --------------- | --------------------- | -------------------------- |
| Struktur        | 0.22                  | `structure_score.py`       |
| Momentum        | 0.20                  | `momentum_score.py`        |
| Multi-Timeframe | 0.22                  | `multi_timeframe_score.py` |
| News            | 0.10                  | `news_score.py`            |
| Risiko          | 0.18                  | `risk_score.py`            |
| Historik        | 0.08                  | `history_score.py`         |

Summe der `SIGNAL_WEIGHT_*` muss **1.0** sein (Validierung in `config.py`).

## Multi-Timeframe-Gewichte (fix dokumentiert)

Fuer Alignment mit `primary_structure_sign` (`UP`=+1, `DOWN`=-1, `RANGE`=0):

| TF  | Gewicht |
| --- | ------- |
| 1m  | 0.08    |
| 5m  | 0.12    |
| 15m | 0.20    |
| 1H  | 0.30    |
| 4H  | 0.30    |

Alignment pro TF: gleiche Richtung = 1.0, neutral = 0.55, Gegenrichtung = 0.15.
Ergebnis skaliert auf 0–100.

## News / Historik ohne Daten

- **News:** `SIGNAL_DEFAULT_NEWS_NEUTRAL_SCORE` (Default 50), Flags `news_unavailable`.
- **Historik:** weniger als 5 Signale in `app.signals_v1` fuer Symbol+TF →
  `SIGNAL_DEFAULT_HISTORY_NEUTRAL_SCORE`, Flag `history_sparse`.

## Rejection / Decision

`rejection_rules.py` liefert `decision_state`:

- `rejected` — `rejection_state=true`, u. a. bei harten Gruenden (fehlende Pflichtdaten,
  veraltete Features, keine Stop-Zone, …).
- `downgraded` — `rejection_state=false`, aber weiche Regeln (z. B. schwaches RR,
  schwache Struktur fuer Directional).
- `accepted` — keine Regelverletzung.

Zusaetzlich: >=3 weiche Gruende → `rejected`.

### Strukturierter Marktkontext (SMC)

Parallel zum News-Score wertet `shared_py.structured_market_context` gespeicherte News- und
Strukturhinweise instrumentenspezifisch aus (Facetten, Decay, Surprise, Konflikt technisch vs. Event).
Weiche Codes gehen in `apply_rejections`; optionale Hard-Vetos nur mit `SMC_HARD_EVENT_VETO_ENABLED`;
Live kann ueber `live_execution_block_reasons_json` zusaetzlich gedrosselt werden bei gleicher
Berechnung wie Shadow/Paper. Doku: [structured_market_context.md](structured_market_context.md).

## Richtung (`direction`)

Gate aus Struktur-Trend, `SIGNAL_MIN_STRUCTURE_SCORE_FOR_DIRECTIONAL`,
`SIGNAL_MIN_MULTI_TF_SCORE_FOR_DIRECTIONAL` und Momentum-Struktur-Konflikt-Flags.
Sonst **`neutral`**.

## Regime-Klassifikation (Prompt 16)

Deterministische Baseline aus vorhandenen Struktur-, Candle-/Feature-,
Volatilitaets-, Liquidity- und News-Inputs. Kanonische Labels:

- `trend`
- `chop`
- `compression`
- `breakout`
- `shock`

Persistierte Regime-Felder pro Signal:

- `market_regime`
- `regime_bias` (`long|short|neutral`)
- `regime_confidence_0_1`
- `regime_reasons_json`

Prioritaet der Klassifikation:

1. `shock`
2. `breakout`
3. `compression`
4. `trend`
5. `chop`

Baseline-Heuristiken:

- `shock`: hochrelevante News und/oder klare Volatilitaets-/Liquidity-
  Dislokation (`vol_z_50`, `atrp_14`, `spread_bps`, `execution_cost_bps`,
  `volatility_cost_bps`, `open_interest_change_pct`)
- `breakout`: frisches `BREAKOUT`-Struktur-Event ohne frischen
  `FALSE_BREAKOUT`, optional bestaetigt durch Impuls/Volume
- `compression`: `compression_flag` und/oder enger Box-/Range-Zustand bei
  niedriger ATR%
- `trend`: `structure_state.trend_dir` plus brauchbares Multi-TF-Alignment
- `chop`: Default fuer Range-/Churn-/False-Breakout-Kontext

`score_risk()` und `classification.py` konsumieren das Regime direkt:

- `shock` wird klar risikoseitiger behandelt
- `breakout` kann `gross` frueher legitimieren
- `compression` wird konservativer eingestuft
- `chop` wird staerker Richtung/Qualitaet-kritisch behandelt

## Staerke vs. Wahrscheinlichkeit

- `signal_strength_0_100`: nach Rejection gekappt (rejected stark reduziert,
  downgraded leicht reduziert).
- `probability_0_1`: eigene Formel aus Composite, MTF, Risiko, Richtung und
  `decision_state` (`service.compute_probability`) — **nicht** nur `/100`.

## Meta-Label `take_trade_prob` (Prompt 17)

- `take_trade_prob` ist **nicht** dieselbe Groesse wie `probability_0_1`.
- `probability_0_1` bleibt der deterministische Heuristik-Output der
  Signal-Engine.
- `take_trade_prob` ist die kalibrierte Meta-Label-Wahrscheinlichkeit fuer
  `take_trade_label` und wird in `learning-engine` aus
  `learn.trade_evaluations` trainiert.

Baseline-Modell:

- Basis-Estimator: `HistGradientBoostingClassifier`
- Kalibrierung: explizites Chronologie-Split-Fenster mit `sigmoid`
  (Platt-Scaling) oder `isotonic`
- Feature-Vertrag: Shared-Feature-Snapshot plus Shared-Signal-Output-Snapshot,
  inklusive Regime-One-Hots, Regime-Confidence und der heuristischen
  `probability_0_1`

Persistierte Signal-Felder:

- `take_trade_prob`
- `take_trade_model_version`
- `take_trade_model_run_id`
- `take_trade_calibration_method`

Audit-/Registry-Pfade:

- `app.model_runs` speichert Artefakt-Pfad, Dataset-Hash, Kalibrierungsmethode,
  Metriken und weitere Modellmetadaten des promoteten Laufs
- `source_snapshot_json.take_trade_model` und
  `source_snapshot_json.model_contract.active_models` verankern den auf dem
  Signal verwendeten Modellstand fuer spaetere Risk-/Leverage-Entscheidungen
- Dashboard und Live-State zeigen neben `probability_0_1` jetzt auch
  `take_trade_prob`

## Bps-Projektionsmodelle (Prompt 18)

- Prompt 18 fuehrt drei **getrennte** Regressionsmodelle fuer
  `expected_return_bps`, `expected_mae_bps` und `expected_mfe_bps` ein.
- Die Modelle nutzen denselben Shared-Feature-Vector wie `take_trade_prob`
  inklusive Regime-, Liquidity-, Funding- und Multi-Timeframe-Features.
- `expected_return_bps` wird ueber `asinh_clip` skaliert; `expected_mae_bps`
  und `expected_mfe_bps` ueber `log1p_clip`. Zusaetzlich werden Vorhersagen auf
  train-basierte Bounds begrenzt, damit Risk-/Leverage-Pfade keine ungebundenen
  Ausreisser verarbeiten muessen.

Persistierte Signal-Felder:

- `expected_return_bps`
- `expected_mae_bps`
- `expected_mfe_bps`
- `target_projection_models_json`

Audit-/Registry-Pfade:

- `app.model_runs` enthaelt je Zielmodell einen eigenen promoteten Run mit
  Artefakt, Dataset-Hash, Holdout-Metriken und Scaling-Methode
- `source_snapshot_json.target_projection_summary` und
  `source_snapshot_json.target_projection_models` verankern den online
  verwendeten Modellstand fuer Replay und spaetere Risk-/Leverage-Entscheidungen
- `model_contract.active_models` fuehrt `take_trade_prob` und die aktiven
  Bps-Regressoren gemeinsam

Runtime-Konsumenten:

- `paper-broker.strategy.gating.should_auto_trade()` gate't jetzt optional auf
  `expected_return_bps`, `expected_mae_bps` und das projektierte
  `expected_mfe_bps / expected_mae_bps`
- `paper-broker.strategy.sizing.leverage_for_signal()` laesst eine
  Default-Leverage > 7x nur noch durch, wenn das projektierte Edge-/Downside-
  Profil die konfigurierten Schwellen erfuellt

## Uncertainty, OOD und Abstention (Prompt 19)

- Prompt 19 fuehrt einen expliziten Produktions-Unsicherheits-Score
  `model_uncertainty_0_1` ein. Er wird online aus fuenf Komponenten aggregiert:
  Data-Quality-Issues, Regime-Unsicherheit, Modellkonfidenz, Shadow-Divergenz
  zwischen `probability_0_1` und `take_trade_prob` sowie OOD-Signalen.
- Echte OOD-Checks basieren auf train-seitig gespeicherten Feature-Referenzen in
  `app.model_runs.metadata_json.feature_reference`. Die Online-Scorer fuer
  `take_trade_prob` und `expected_*_bps` pruefen den aktuellen Feature-Vector
  gegen diese Referenz und liefern `model_ood_score_0_1` plus `model_ood_alert`.
- Persistierte Signal-Felder fuer Prompt 19 sind:
  `model_uncertainty_0_1`, `shadow_divergence_0_1`, `model_ood_score_0_1`,
  `model_ood_alert`, `uncertainty_reasons_json`, `ood_reasons_json`,
  `abstention_reasons_json` und `trade_action`.
- Harte Abstention-Regel: wenn `model_uncertainty_0_1 > MODEL_MAX_UNCERTAINTY`
  oder `model_ood_alert=true`, wird das Signal deterministisch auf
  `trade_action=do_not_trade`, `decision_state=rejected` und `signal_class=warnung`
  gesetzt. Unsichere/OOD-Situationen bleiben damit nicht kosmetisch, sondern
  werden zu einem echten Produktions-Gate.
- `source_snapshot_json.uncertainty_assessment` speichert die Komponenten und
  Scorer-Diagnostik fuer Replay und Audit; `paper-broker.strategy.gating` blockt
  Signale zusaetzlich explizit auf `trade_action=do_not_trade`.

## Hybrid-Entscheider (Prompt 20)

- Prompt 20 fuehrt einen finalen Hybrid-Entscheider in der `signal-engine` ein.
  Er kombiniert die deterministische V1-Basis (`decision_state`, `signal_class`,
  Regime, Safety-/Quality-Gates) mit `take_trade_prob`, den
  `expected_*_bps`-Projektionen und den Prompt-19-Unsicherheits-/Abstention-
  Signalen.
- Die deterministische Safety-Layer bleibt Pflicht-Floor: bestehende
  `decision_state!=accepted`, `signal_class=warnung`, `trade_action=do_not_trade`
  oder `market_regime=shock` koennen vom Hybrid-Entscheider nicht in einen
  Trade zurueckgedreht werden.
- Neue persistierte Finalfelder fuer Prompt 20 sind:
  `decision_confidence_0_1`, `decision_policy_version` und
  `recommended_leverage`.
- Bereits vorhandene Felder `trade_action`, `direction`, `expected_return_bps`,
  `expected_mae_bps`, `expected_mfe_bps`, `model_uncertainty_0_1` und
  `abstention_reasons_json` bilden gemeinsam das minimale API-/Audit-Output des
  Hybrid-Entscheiders.
- `source_snapshot_json.hybrid_decision` dokumentiert Trade-Score,
  projected reward-to-adverse ratio, Safety-/Model-Gates, Konfidenz,
  Leverage-Hinweis und primaeren Abstention-Grund fuer Replay und Audit.

## Integer-Leverage-Allocator (Prompt 21)

- Prompt 21 erweitert den finalen Entscheidungs-Pfad um einen echten Integer-
  Leverage-Allocator 7..75. Die `signal-engine` berechnet daraus
  `allowed_leverage`, `recommended_leverage`, `leverage_policy_version` und
  `leverage_cap_reasons_json`.
- Der signal-seitige `model_cap` wird deterministisch aus Edge,
  `model_uncertainty_0_1`, `expected_volatility_band`, Spread, Slippage,
  Funding, Orderbook-Depth/Impact und Data-Quality abgeleitet.
- Harte Regel: wenn `allowed_leverage < 7`, wird das Signal auf
  `trade_action=do_not_trade` heruntergestuft.
- Der `paper-broker` fuehrt denselben Shared-Allocator vor dem Open noch einmal
  mit Execution-/Account-Caps aus: `exchange_cap`, `model_cap`,
  `liquidation_buffer_cap`, `stop_distance_cap`, `margin_usage_cap` und
  `drawdown_cap`.
- Der finale Execution-Trace landet in `paper.positions.meta.leverage_allocator`
  und im `trade_opened`-Trace; der `live-broker` schreibt den Upstream-
  Leverage-Kontext zusaetzlich in `live.execution_decisions.payload_json`.

## Signalklasse

`classification.py`: kombiniert Schwellen (`SIGNAL_MIN_SCORE_FOR_*`), `decision_state`,
`multi_timeframe_score`, `risk_score` und Layer-Flags (z. B. Fehlausbruch → `warnung`).

Erlaubte Werte in DB: `mikro`, `kern`, `gross`, `warnung`.

## Reasons-JSON

Strukturiertes Objekt mit Arrays: `bullish_factors`, `bearish_factors`,
`structural_notes`, `momentum_notes`, `timeframe_notes`, `risk_notes`,
`news_notes`, `history_notes`, `decisive_factors` — Basis fuer Prompt 14.

## Snapshot

`source_snapshot_json` enthaelt nur sichere, aggregierte Metadaten (keine Secrets).
Seit Prompt 16 liegt dort zusaetzlich ein `regime_snapshot` mit den fuer die
Klassifikation verwendeten Fakten (`structure_trend_dir`, `compression_flag`,
`range_score`, `news_relevance_score`, `dislocation_signal_count`, recenten
Struktur-Events usw.).
