# Modell-Lebenszyklus: Champion, Challenger, Promotion, Rollback (Prompt 29)

## Ablauf (final)

1. **Training** erzeugt `model_runs` inkl. `metrics_json` (`cv_summary`, Test-Metriken) und `metadata_json` (optional `shadow_validation`).
2. **Challenger** (`POST /learning/registry/v2/challenger`): Shadow-Slot fuer Vergleich; kein Live-Load durch Signal-Engine (nur Champion).
3. **Champion** (`POST /learning/registry/v2/champion`): Produktions-Run; setzt `promoted_bool` und Registry-Slot `champion`.
4. **Stabiler Checkpoint** (`POST /learning/registry/v2/stable-checkpoint`): Ops markiert den aktuellen Champion als Rollback-Ziel (`app.model_stable_champion_checkpoint`).
5. **Rollback** (`POST /learning/registry/v2/rollback-stable`): Champion wird auf Checkpoint-`run_id` gesetzt; **Promotions-Gates werden uebersprungen** (Notfallpfad).
6. **Historie** (`app.model_champion_history`): jede Champion-Periode mit `promotion_gate_report` (Audit).

## Wer darf promoten / freigeben?

| Aktion              | Technisch                                                                                                                                            | Evidenz / Policy                                                                                                                                                                                                                          |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Champion setzen     | Authentifizierte Aufrufer der Learning-Engine-API (`changed_by` im Body, Audit)                                                                      | Bei `MODEL_PROMOTION_GATES_ENABLED=true`: Walk-Forward- und Purged-CV-Mittel, Test-ROC-AUC, Brier (take_trade_prob) bzw. Accuracy (regime); optional `MODEL_PROMOTION_REQUIRE_SHADOW_EVIDENCE` + `metadata_json.shadow_validation.passed` |
| Manuelles Override  | Nur wenn `MODEL_PROMOTION_MANUAL_OVERRIDE_ENABLED=true` **und** `promotion_manual_override=true` **und** `promotion_override_reason` mind. 8 Zeichen | Vier-Augen-Prozess ausserhalb des Codes (Change-Ticket); `changed_by` muss fachlich verantwortliche Rolle abbilden                                                                                                                        |
| Gates abschalten    | `MODEL_PROMOTION_GATES_ENABLED=false`                                                                                                                | Nur in Dev oder mit explizitem Risikoakzept (Dokumentation)                                                                                                                                                                               |
| Stabiler Checkpoint | `POST .../stable-checkpoint` mit `marked_by`                                                                                                         | Nach erfolgreichem Shadow/Vergleich oder Release-Sign-Off                                                                                                                                                                                 |
| Rollback            | `POST .../rollback-stable`                                                                                                                           | Grund (`reason`) + Audit; kein Gate-Check auf Ziel-Run                                                                                                                                                                                    |

Keine automatische Champion-Promotion aus Backtest-Ranking allein — Schwellen sind konfigurierbare harte Grenzen.

## Promotion-Regeln (hart)

Konfiguration in `LearningEngineSettings` / ENV:

- `MODEL_PROMOTION_GATES_ENABLED`
- `MODEL_PROMOTION_MIN_WALK_FORWARD_MEAN_ROC_AUC`, `MODEL_PROMOTION_MIN_PURGED_KFOLD_MEAN_ROC_AUC`
- `MODEL_PROMOTION_MIN_TEST_ROC_AUC_TAKE_TRADE`, `MODEL_PROMOTION_MAX_TEST_BRIER_TAKE_TRADE`
- Regime: `MODEL_PROMOTION_MIN_WALK_FORWARD_MEAN_ACCURACY_REGIME`, `..._PURGED_...`
- `MODEL_PROMOTION_REQUIRE_SHADOW_EVIDENCE` + JSON-Felder `shadow_validation` / `shadow_vs_champion`
- **Governance-Artefakte (optional):** `MODEL_PROMOTION_REQUIRE_GOVERNANCE_ARTIFACTS` prueft u. a.
  `data_version_hash`, `dataset_hash`, `feature_contract.schema_hash`, `artifact_files.training_manifest`,
  Kalibrierungsnachweis in Metriken/Metadaten. Optional `MODEL_PROMOTION_REQUIRE_INFERENCE_BEHAVIOR_METADATA`
  fuer dokumentierte `inference_fallback_policy` / `inference_abstention_policy` in `metadata_json`.
- **Online-Drift vs. Promotion:** `MODEL_PROMOTION_APPLY_ONLINE_DRIFT_GATE` (nur `take_trade_prob`,
  **globaler** Scope): wenn `learn.online_drift_state.effective_action` in
  `MODEL_PROMOTION_ONLINE_DRIFT_BLOCKED_TIERS` (Default `shadow_only,hard_block`), schlaegt die Promotion fehl
  — kein Live-Champion nur weil der Run neu ist, solange Drift-Stufen aktiv sind.
- **Symbol-Scoped Champion:** bei `scope_type=symbol` muss `metadata_json.train_rows` mindestens
  `SPECIALIST_SYMBOL_MIN_ROWS` sein (Nachweis gegen duenne Symbol-Spezialisten).

### Spezialisten / Take-Trade: Stabilitaet, Tail, No-Trade-Qualitaet (optional)

- **`MODEL_PROMOTION_FAIL_ON_CV_SYMBOL_LEAKAGE_TAKE_TRADE`**: wenn `true`, duerfen Walk-Forward
  und Purged-KFold laut `metrics_json.cv_summary` nicht mehr als
  `MODEL_PROMOTION_MAX_CV_SYMBOL_OVERLAP_FOLDS_TAKE_TRADE` Folds mit
  `folds_with_symbol_overlap` aufweisen (Mindeststabilitaet / Leakage-Warnung aus Training).
- **`MODEL_PROMOTION_REQUIRE_TRADE_RELEVANCE_GATES_TAKE_TRADE`**: wenn `true`, muss
  `metrics_json.trade_relevance_summary.high_confidence_false_positive_rate` gesetzt sein und
  `<= MODEL_PROMOTION_TRADE_RELEVANCE_MAX_HIGH_CONF_FP_RATE` (Tail-/Abstentions-Qualitaet).
- **OOD / Online-Drift:** bleiben ueber `learn.online_drift_state` und bestehende
  Block-Regeln (kein Chat-Eingriff).

**Shadow-Bestaetigung:** weiterhin ueber `MODEL_PROMOTION_REQUIRE_SHADOW_EVIDENCE` und
`metadata_json.shadow_validation` bzw. `metrics_json.shadow_vs_champion`.

## Registry-Mutationen: nur Governance-Pfad

Wenn `MODEL_REGISTRY_MUTATION_SECRET` gesetzt ist, erfordern **alle** schreibenden
Registry-V2-Endpunkte der Learning-Engine den Header **`X-Model-Registry-Mutation-Secret`**.
Telegram, anonymes UI oder Browser koennen ohne serverseitigen Proxy mit Secret **keine**
Champion-/Challenger-/Checkpoint-Aenderungen ausloesen. Lesende Routen (`GET .../slots`)
bleiben unveraendert (Netzwerk-Auth bleibt Sache des Deployments).

## Scoped Champion: Freigabe je Marktfamilie / Regime / …

Champion und Challenger sind pro `(model_name, scope_type, scope_key)` fuehrbar
(siehe `docs/model_registry_v2.md`), inkl. **`market_cluster`** (`familie::regime`) und **`symbol`**.
Promotions-Gates gelten **je Zuweisung** (gleiche Metriken des referenzierten `run_id`). Operativ: erst globalen konservativen Champion
setzen, scoped nur nach ausreichender Evidenz und Shadow-Vergleich.

## Curriculum und Kontext-Signale (kein Policy-Rewrite)

- Readiness + Curriculum: `GET /learning/governance/expert-curriculum` (Learning-Engine) bzw.
  weiterhin `GET /learning/training/specialists-readiness` — Segmente Familie, Cluster, Regime, Playbook, Symbol
  mit Mindestzeilen (`SPECIALIST_*_MIN_ROWS`).
- Kontext fuer Learning (Shadow, Paper, Post-Trade-Review, Outcomes): `POST /learning/governance/context-signals`
  schreibt nach `learn.learning_context_signals`; **`operator_context`** erzwingt `policy_rewrite_forbidden=true\*\*
  (nur Kontextsignal, keine Strategie-Mutation im Codepfad).
- Dashboard-Report (Gateway): `GET /v1/learning/model-ops/report` — Kalibrierungs-Spiegel, Drift, Slice-Zaehler,
  Abstention-/No-Trade-Proxies.

## Block-Regeln (Online-Drift)

Der Learning-Engine-Evaluator schreibt `learn.online_drift_state.effective_action` (`ok` | `warn` | `shadow_only` | `hard_block`).

**Dimensionen** (staerkste gewinnt): u.a. OOD-Mittel, Feature-Staleness, Score-Streuung, Regime-TV, **OOD-Alert-Rate**, **fehlende take_trade_prob**, **Shadow-vs-Champion-MAE** (wenn `take_trade_model.challenger_take_trade_prob` im Snapshot liegt).

Signal-Engine / Live-Broker: bei `hard_block` + `ENABLE_ONLINE_DRIFT_BLOCK` Live-Block; bei `shadow_only` Live auf Shadow begrenzt (bestehende Logik).
Optional: `ENABLE_ONLINE_DRIFT_SHADOW_ONLY_SIGNAL_HARD_BLOCK=true` laesst die Signal-Engine **auch bei `shadow_only`**
`do_not_trade` setzen (hartes Eskalations-Verhalten; nur mit bewusstem Ops-Rollout).

## Rollback-Regeln

- **Manuell:** `rollback-stable` auf gesetzten Checkpoint.
- **Automatisch (optional):** `MODEL_REGISTRY_AUTO_ROLLBACK_ON_DRIFT_HARD_BLOCK=true` — beim **Uebergang** zu `hard_block` wird fuer `MODEL_REGISTRY_AUTO_ROLLBACK_MODEL_NAME` (Default `take_trade_prob`) ein Rollback auf den stabilen Checkpoint versucht, sofern gesetzt. Kein Rollback ohne Checkpoint.

## Migration

- `infra/migrations/postgres/410_model_champion_lifecycle.sql` — `app.model_champion_history`, `app.model_stable_champion_checkpoint`.
