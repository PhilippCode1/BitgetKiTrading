# Replay- und Backtest-Determinismus (Prompt 27)

Ziel: **gleiche Eingaben** (Datenbankinhalt im Fenster, Symbol, Zeitraum, CV-Parameter, ENV-relevante Caps/Seeds) liefern **dieselben technischen Artefakte** (stabile IDs, sortierte Stichproben, protokollierte Metadaten). Fachliche Trading-Entscheidungen bleiben **deterministisch aus Safety-/Risk-/Policy-Logik** plus Modelloutputs; dieses Dokument betrifft vor allem **Replay, Offline-Backtest und Vergleichbarkeit von Metriken**.

## Stabile Identifikatoren

| ID                                                      | Quelle                                                                                                                          | Wann neu?                                                                                                                                                                                                             |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Replay-Session** (`learn.replay_sessions.session_id`) | UUID5 aus Symbol, kanonische Timeframes, `from_ts_ms`, `to_ts_ms`, `speed_factor`, `dedupe_prefix`, `publish_ticks`             | Gleiche Parameter → gleiche ID (Upsert). Mit `--ephemeral-session` / `ephemeral_session=True` → frische UUID4.                                                                                                        |
| **Stream-Event** (`event_id` im `EventEnvelope`)        | UUID5 aus Stream-Name + `dedupe_key` (`stable_stream_event_id`)                                                                 | Gleiche Kerze → gleiche `event_id`. Bei Trace mit Replay-Herkunft (`trace_implies_replay_determinism`) setzt `EventEnvelope` das automatisch; mit `exchange_ts_ms` wird `ingest_ts_ms` fuer Wire-Replays angeglichen. |
| **structure_updated / drawing_updated**                 | UUID5 aus dedupe_key (Structure: `structure:…`, Drawing: `drawing:…`)                                                           | Gleiche Pipeline-Stufe + Parent-Event → gleiche `event_id`.                                                                                                                                                           |
| **signal_created**                                      | UUID5 aus `dedupe_key` `signal:<signal_id>`                                                                                     | Ableitbar aus persistierter `signal_id`.                                                                                                                                                                              |
| **signal_id (Replay)**                                  | UUID5 aus `replay_session_id`, `upstream_drawing_updated_event_id`, Symbol, TF, `analysis_ts_ms`, `SIGNAL_EVENT_SCHEMA_VERSION` | Nur wenn Trace `source=learning_engine.replay` und `SIGNAL_STABLE_REPLAY_SIGNAL_IDS=true`.                                                                                                                            |
| **decision_trace_id**                                   | UUID5 aus `signal_id` + `decision_policy_version` (Hybrid)                                                                      | In `source_snapshot_json` nach Hybrid-Schicht; vergleichbar Live vs Shadow.                                                                                                                                           |
| **Offline-Backtest-Run** (`learn.backtest_runs.run_id`) | UUID5 aus Symbol, Timeframes, Fenster, `cv_method`, `k_folds`, `embargo_pct`, `TRAIN_RANDOM_STATE`                              | Gleiche Parameter → gleiche ID. `--ephemeral-run` / `ephemeral_run=True` → UUID4.                                                                                                                                     |

**correlation_chain** (`schema: correlation-v1`) in `source_snapshot_json`: verknuepft `candle_close_event_id`, `structure_updated_event_id`, `upstream_drawing_updated_event_id`, `replay_session_id`, `signal_id`, spaeter `decision_trace_id` — gleiche Sicht fuer DB, Redis-Trace und Dashboard.

Implementierung: `shared_py.replay_determinism` (Namespaces und `REPLAY_DETERMINISM_PROTOCOL_VERSION` sind **fest**; Änderung bricht bestehende IDs).

## Kontrakte Live = Shadow = Replay

`learn.replay_sessions.manifest_json` enthaelt u. a. `policy_caps`, `hybrid_decision_policy_version`, `signal_event_schema_version` (Learning-Engine `build_replay_manifest`). Replay laeuft durch dieselbe Signal-Pipeline wie Live, solange **dieselben Service-Settings/Modell-Artefakte** geladen werden; Unterschiede entstehen bei abweichendem ENV, Registry-Champion vs Challenger oder fehlendem Trace.

Shadow-vs-Live-Forensik: [shadow_live_divergence.md](./shadow_live_divergence.md).

## Deterministische Sortierung

- **Candles im Replay-SQL:** `ORDER BY start_ts_ms ASC, timeframe ASC, ingest_ts_ms ASC`.
- **Trade-Evaluations im Offline-Backtest:** `ORDER BY decision_ts_ms ASC, closed_ts_ms ASC, evaluation_id ASC`.
- **Timeframes:** vor Verwendung in Fingerprints/SQL immer `normalized_timeframes()` (eindeutig, sortiert nach Länge dann lexikographisch).

## Random-Seed (Offline-Backtest)

Zu Beginn von `run_offline_backtest` wird `random.seed(settings.train_random_state)` gesetzt (`TRAIN_RANDOM_STATE`). Der Seed fließt in den **Fingerprint der Run-ID** ein, damit Replays dokumentiert sind, wenn sich nur der Seed ändert.

## Mitprotokollierte Metadaten

- **Replay:** `learn.replay_sessions.manifest_json` und `trace.determinism` pro Event enthalten u. a. `determinism_protocol_version`, `model_contract_version`, `feature_schema_version`, `feature_schema_hash`, `train_random_state`, `policy_caps` (Risk-/Gating-Caps aus Settings), plus Laufparameter (Speed, Ticks, Session-Flags).
- **Offline-Backtest:** `params_json.determinism_manifest` im Run-Record mit denselben Kernfeldern plus `cv_method`, `k_folds`, `embargo_pct`, `python_random_seed_applied`.

Builder: `learning_engine.backtest.determinism_manifest`.

## Wiederholte Läufe (Upsert)

- **Replay-Session** und **Backtest-Run** werden bei gleicher Primärschlüssel-ID per `ON CONFLICT DO UPDATE` aktualisiert (Status, Metriken, Manifest).
- Vor Neuaufbau der Folds löscht der Offline-Runner die alten Zeilen zu dieser `run_id` (`delete_backtest_folds_for_run`), damit keine verwaisten Folds bleiben.

## Float-Toleranzen (nur Metriken-Vergleich)

Für den **Vergleich aggregierter Metrik-Maps** (z. B. in Tests oder Report-Diffs) gilt `shared_py.replay_determinism.FLOAT_METRICS_RTOL` (Standard **1e-9**, relativ nur für `float`-Felder; Schlüssel und Nicht-Floats exakt). In Python gelten `1` und `1.0` als gleich (`==`); strikt getrennte Typen erfordern eigene Assertions, falls nötig.

**Keine fachliche Drift:** Gates, Aktionen (`do_not_trade`, Leverage-Grenzen, erlaubte Integer-Leverage 7..75) und diskrete Policy-Ergebnisse werden **nicht** über diese Toleranz „weich“ gemacht — nur numerische Summary-Metriken dürfen bei Float-Arithmetik leicht schwanken.

## Betrieb und Entwicklung

- Produktive Replays: **ohne** `ephemeral_session`, damit Sessions und Events auditierbar zusammenpassen.
- Parallele Experimente: `--ephemeral-session` / `--ephemeral-run`, um keine bestehenden Run-Records zu überschreiben.
- Bei Schema- oder Policy-Änderungen: `determinism_protocol_version` bzw. Modell-/Schema-Versionen im Manifest prüfen; gleiche Daten können andere **Modell**outputs haben — die **Replay-Infrastruktur** bleibt reproduzierbar.

## Bekannte Nicht-Determinismen (bewusst begrenzt)

- Ohne gesetzten `dedupe_key` bleiben generische `EventEnvelope`-Defaults (`event_id`, `ingest_ts_ms`) wall-clock-/UUID-basiert und daher nicht byte-identisch replaybar.
- Serviceweite Wall-Clock-Nutzung (Scheduler, Health, Reconcile, Alerting) bleibt fuer Betriebszeitstempel erhalten; fachliche Entscheidungen sollen trotzdem deterministisch bleiben.
- Research-/Benchmark-Reports enthalten bewusst Laufzeitfelder wie `generated_at_utc`; diese sind fuer Audit relevant, aber nicht deterministisch.
- Externe WS-/REST-/DB-/Redis-Latenz beeinflusst Restart-/Recovery-Timing. Deshalb werden Recovery-Tests als Vertrag auf Shapes, Status und Safety-Gates formuliert, nicht auf identische Millisekundenabfolgen.

Siehe auch: [backtesting_replay.md](./backtesting_replay.md).

## Research-Benchmark-Reports (Evidence-Harness)

Der Learning-Engine-Report `build_benchmark_evidence_report` ist **kein Replay**, aber für **Vergleichbarkeit** zwischen Läufen relevant:

- **Sortierung:** Zeilen aus `learn.trade_evaluations` werden nach DB-Stichprobe (neueste zuerst, Limit) geholt und im Harness **chronologisch** nach `(decision_ts_ms ASC, evaluation_id ASC)` sortiert. Gleiche DB-Daten + gleiche Limits → gleiche Reihenfolge und gleiche diskrete Zählmetriken.
- **Nicht-deterministisch / schwach deterministisch:**
  - `generated_at_utc` (immer neu).
  - Aggregierte **Floats** (Korrelationen, Mittelwerte) können je nach Plattform minimal differieren — Vergleich mit `shared_py.replay_determinism.FLOAT_METRICS_RTOL` wie bei Backtest-Metriken.
  - Fehlende oder unvollständige `feature_snapshot_json` / `signal_snapshot_json` ändern Heuristik-Baselines und Teilmetriken.
  - Lesende Replikas: extrem selten andere Randzeilen bei identischem Limit, wenn Schreibpfad noch repliziert.
- **Testbar:** `determinism`-Objekt im Report enthält `float_metrics_rtol` und dokumentierte Faktoren; pytest deckt stabile Sortierung und Report-Shape ab ([research_benchmarking.md](./research_benchmarking.md)).
