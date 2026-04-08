# Unified Leverage Allocator (`unified-lev-v2`)

Implementierung: `shared/python/src/shared_py/unified_leverage_allocator.py`  
Aufruf: Signal-Engine **Hybrid** (Proxy-Stop aus MAE) und erneut nach **Stop-Budget-Assessment** (reale Stop-Distanz).

## Rollen der Hebel-Felder

| Feld                     | Bedeutung                                                                                                                                            |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `allowed_leverage`       | Harte Obergrenze aus Hybrid-Faktor-Caps, Governor, Instrument-Metadaten, Live-Ramp; ggf. nach Stop-Budget reduziert.                                 |
| `recommended_leverage`   | Betriebspunkt ≤ `allowed_leverage` (Integer-Allocator).                                                                                              |
| `execution_leverage_cap` | Max-Hebel fuer **automatisierte** Ausfuehrung (Shadow-Event, Paper-Default, Live-Intent ohne manuelle Freigabe). Immer ≤ `recommended`.              |
| `mirror_leverage`        | Referenz fuer **manuell bestaetigte** Realtrades: volles Signal-Ziel nach allen deterministischen Gates (typisch = `recommended` bei `allow_trade`). |

Notional-/Positionsbudget: `max_position_notional_fraction_0_1` kombiniert Governor-Exposure-Tier mit zusaetzlichem Shrink bei **sehr engen** Stops (konfigurierbare Schwelle), damit enge Stops nicht durch zu grosse Positionsgroessen faktisch unbrauchbar werden.

## Eingaben (deterministisch)

- Edge / Modelllage: bereits in `allowed` / `recommended` enthalten; Allocator verschärft nur Ausfuehrung vs. Mirror.
- Stop-Distanz: nach Hybrid MAE-Proxy (`expected_mae_bps / 10000`); nach Stop-Budget echtes `stop_distance_pct`.
- Volatilitaet/Tiefe: indirekt ueber Hybrid-Caps; zusaetzlich `leverage_stop_distance_scale_bps` vs. Stop-Distanz (analog Paper `LEVERAGE_STOP_DISTANCE_SCALE_BPS`).
- Kontohitze: `risk_account_snapshot.margin_utilization_0_1` — bei Ueberschreitung weicher Schwelle wird `execution_leverage_cap` multiplikativ reduziert (nicht `mirror_leverage`).
- Unsicherheit / Shadow: `shadow_divergence_0_1` — weiche Zusatzkappe (unterhalb hartem Abstinenz-Gate).

## Instrument-Evidenz (Cold Start)

Fehlt `instrument_evidence_json.prior_signal_count` im Snapshot (oder Zaehler &lt; `LEVERAGE_COLD_START_PRIOR_SIGNALS_THRESHOLD`), gilt **Cold-Start**: zusaetzliche Kappe `LEVERAGE_COLD_START_MAX_CAP` auf `execution_leverage_cap`.  
Nachreichen der Evidenz (z. B. aus Operator-Pipeline oder Lern-Metriken) erlaubt **kontrolliertes Hochfahren** ohne Aenderung der Strategie-Registry.

## Marktfamilien-Zusatzkappen

`LEVERAGE_FAMILY_MAX_CAP_SPOT` / `_MARGIN` / `_FUTURES` schneiden gegen `allowed` (zusaetzlich zu Bitget-Metadaten). Keine Fantasie-Produkte: nur konfigurierte Familien; echte Produktgrenzen bleiben in `instrument`-Metadaten massgeblich.

## ENV-Profile (Basis)

Siehe `config/settings.py`: `LEVERAGE_AUTO_EXECUTION_*`, `LEVERAGE_FAMILY_MAX_CAP_*`, `LEVERAGE_COLD_START_*`, `LEVERAGE_SHADOW_DIVERGENCE_*`, `LEVERAGE_STOP_DISTANCE_SCALE_BPS`, `LEVERAGE_TIGHT_STOP_EXPOSURE_*`, `LEVERAGE_ACCOUNT_HEAT_*`.

## Broker-Verhalten

- **Paper**: `allocate_paper_execution_leverage` beruecksichtigt `signal_execution_leverage_cap` aus dem Snapshot; Strategy-Sizing bevorzugt `execution_leverage_cap` vor `recommended_leverage`.
- **Live (Signal-Event)**: Intent-Hebel nutzt `execution_leverage_cap` falls gesetzt, sonst `recommended_leverage`; Payload enthaelt zusaetzlich `signal_mirror_leverage` / `signal_recommended_leverage` fuer Audit und manuelle Freigaben.

## Evidenzbasierte Caps (v2)

`evidence_cap_breakdown_json` listet die **bindenden** und **nicht-bindenden** Kappen mit Quelle (Exchange/Modell, Governor, Familie, Stop-Distanz, Drawdown-Kill-Switch, Liquidationspuffer aus Snapshot, Cold-Start, Shadow, Margin-Heat). `binding_caps_json` fasst nur diejenigen zusammen, die die finale Ausfuehrungskappe begrenzen.

Zusaetzliche ENV: `RISK_LEVERAGE_CAP_DAILY_DRAWDOWN_THRESHOLD_0_1`, `RISK_LEVERAGE_CAP_WEEKLY_DRAWDOWN_THRESHOLD_0_1`, `RISK_LEVERAGE_MAX_UNDER_DRAWDOWN` (siehe `config/settings.py`).

## Telegram / Chat

Keine Veraenderung von Hebel-Policys ueber Chat; Allocator laeuft ausschliesslich in der Signal-Engine und determinierten Brokern.
