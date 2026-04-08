# Online-Drift (Prompt 26)

## Ueberblick

Der **Online-Drift-Evaluator** (learning-engine) wertet juengste `app.signals_v1`
aus und vergleicht sie mit Referenzen aus dem Champion-`take_trade_prob`-Run
(`metadata_json.regime_counts_train`, Metriken-Spiegel). Erkennte Dimensionen:

- **Feature-Staleness**: Anteil Signale mit sehr hohen Liquidity-Alter-Feldern im
  Feature-Snapshot (`orderbook_age_ms`, `funding_age_ms`, `open_interest_age_ms`).
- **Regime-Verteilung**: Total-Variation-Abstand zwischen Live-Histogramm und
  Trainings-Regimeanteilen.
- **OOD-Druck**: Mittelwert `model_ood_score_0_1`.
- **Modellverhalten / Score-Streuung**: Standardabweichung von `take_trade_prob`
  in der Stichprobe.
- **Inference-OOD-Alert-Rate**: Anteil Signale mit `model_ood_alert=true`.
- **Fehlende take_trade_prob**: Anteil ohne Modell-Score.
- **Shadow-vs-Champion-MAE**: falls `source_snapshot_json.take_trade_model.challenger_take_trade_prob`
  gesetzt ist, mittlere absolute Differenz zur Live-`take_trade_prob`.

Optional (Prompt 29): bei `MODEL_REGISTRY_AUTO_ROLLBACK_ON_DRIFT_HARD_BLOCK=true`
versucht die Pipeline beim **ersten** Wechsel auf `hard_block` einen Registry-Rollback
auf den stabilen Checkpoint (`docs/model_lifecycle_governance.md`).

Pro ausgeloester Dimension wird ein Eintrag in `learn.drift_events` geschrieben
(`details_json.drift_class = "online"`, `severity` = `warn` | `shadow_only` |
`hard_block`). Der **materialisierte Zustand** liegt in `learn.online_drift_state`
(Scope `global`).

## Gates

| `effective_action` | Signal-Engine (`ENABLE_ONLINE_DRIFT_BLOCK=true`) | Live-Broker (`ENABLE_ONLINE_DRIFT_BLOCK=true`)                                                                                                                                                                                                                           |
| ------------------ | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `warn`             | Metadaten in `reasons_json` / Event-Payload      | kein Zwang                                                                                                                                                                                                                                                               |
| `shadow_only`      | `online_drift_live_forbidden=true` im Event      | Live-Pfad → `shadow_recorded` / `online_drift_live_forced_shadow` wenn `SHADOW_TRADE_ENABLE=true`; bei `EXECUTION_MODE=live` erzwingt `BaseServiceSettings` derzeit `SHADOW_TRADE_ENABLE=false`, dann `blocked` / `online_drift_shadow_disabled` (harte Live-Drosselung) |
| `hard_block`       | `trade_action=do_not_trade`, Rejection           | `blocked` / `online_drift_hard_block`                                                                                                                                                                                                                                    |

Ohne `ENABLE_ONLINE_DRIFT_BLOCK` bleiben die Gates inaktiv; Dashboard und State
sind weiterhin lesbar.

## APIs

- Learning: `GET /learning/drift/online-state`, `POST /learning/drift/evaluate-now`
- Gateway: `GET /v1/learning/drift/online-state`
- Analytics-Lauf: optional `ONLINE_DRIFT_EVALUATE_ON_ANALYTICS_RUN=true` (Default)

## Audit

Wechsel von `effective_action` erzeugt einen Eintrag in `app.audit_log`
(`entity_table=online_drift_state`, Aktion `online_drift_<prev>_to_<neu>`).

## Betrieb

1. Migration `400_online_drift_state.sql` ausfuehren.
2. Schwellen ueber `ONLINE_DRIFT_*` ENV justieren (learning-engine).
3. Evaluator per Cron/Run-Now oder Analytics anstossen.
4. In Produktion `ENABLE_ONLINE_DRIFT_BLOCK=true` setzen, wenn Live wirklich
   gebremst werden soll.
