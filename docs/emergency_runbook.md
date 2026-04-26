# Notfallablauf (Prompt 18) — Safety-Schicht

## Prioritaeten (was passiert wann)

| Prioritaet                     | Situation                                                                                 | Systemreaktion                                                                                                                               | Operator                                                                                                                           |
| ------------------------------ | ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **P0 — sofort handeln**        | Service-/Account-Kill-Switch ARM                                                          | Auto **Cancel-All** (Exchange) + lokale Cancellations; Alerts `events:system_alert`                                                          | Ursache beheben, dann Release                                                                                                      |
| **P0**                         | **Emergency Flatten** ausgeloest                                                          | Reduce-Order / Flatten-Pfad + Audit + Alert                                                                                                  | Position/Exposure pruefen                                                                                                          |
| **P0**                         | **Operator Cancel-All** (`POST .../safety/orders/cancel-all`)                             | Exchange cancel-all + lokale aktive Orders; Audit `emergency_cancel_all`                                                                     | —                                                                                                                                  |
| **P1 — blockieren**            | Kill-Switch aktiv (beliebiger Scope)                                                      | Neue Orders (nicht reduce_only) → HTTP 423; Replace blockiert bei Latch                                                                      | Release oder gezielte reduce-only                                                                                                  |
| **P1**                         | **Safety-Latch** nach Reconcile **fail** (bei `LIVE_TRADE_ENABLE=true`)                   | Signal-Live **blockiert** (`live_safety_latch_active`); normale Submits blockiert; **Replace immer blockiert**; **reduce_only** erlaubt      | Explizites `POST .../safety-latch/release` mit Begründung                                                                          |
| **P1**                         | `LIVE_ORDER_REPLACE_ENABLED=false`                                                        | Alle **Replace** → 412/service_disabled                                                                                                      | ENV anpassen wenn fachlich freigegeben                                                                                             |
| **P1**                         | **Execution-Guards** (Spread-/Stop-/Reduce-only-/Replace-Size)                            | Order-Submit/Replace abgelehnt (`BitgetRestError` validation); **Audit** `execution_guard` / **Alert** `live-broker:execution-guard:blocked` | Spread/Volatilitaet, Stop-Abstand, Position-Truth pruefen; Parameter `LIVE_EXECUTION_*` / `LIVE_PRESET_STOP_*` oder Hebel/No-Trade |
| **P1**                         | **Reconcile-Submit-Gate** (`LIVE_BLOCK_SUBMIT_ON_RECONCILE_*`)                            | Submit blockiert bei letztem Snapshot `fail` oder optional `degraded`                                                                        | Alerts `live-broker:execution-guard:reconcile_fail_block` / `reconcile_degraded_block` — Reconcile-Logs, Exchange-Zustand          |
| **P1**                         | **Public-Probe vor Submit** (`LIVE_PROBE_PUBLIC_API_BEFORE_ORDER_SUBMIT=true`)            | Submit blockiert wenn Public nicht erreichbar (`LIVE_REQUIRE_EXCHANGE_HEALTH`)                                                               | Alert `live-broker:execution-guard:public_probe_fail`                                                                              |
| **P1**                         | **Duplicate-Recovery Safety-Latch** (`LIVE_SAFETY_LATCH_ON_DUPLICATE_RECOVERY_FAIL=true`) | Nach nicht aufloesbarer Duplicate-Antwort Latch + Alert `live-broker:safety-latch:armed:duplicate_recovery`                                  | Orderbuch/Client-OIDs pruefen, Latch release nach Klaerung                                                                         |
| **P2 — nur beobachten / Gate** | Reconcile **degraded** (Drift)                                                            | Kein automatischer Latch; Monitor/Alerts; optional Truth-Gate                                                                                | Drift analysieren                                                                                                                  |
| **P3 — Freigabe**              | Kill-Switch **release**, Latch **release**                                                | Wiederherstellung nur nach Audit; **kein** automatisches „silent live“ — ENV `LIVE_TRADE_ENABLE` + `STRATEGY_EXEC_MODE` bleiben explizit     | Runbook / Change-Ticket                                                                                                            |

## Datenfluss Audit / Alerting

- **Audit:** `live.audit_trails` — Kategorien u. a. `kill_switch`, `emergency_flatten`, `emergency_cancel_all`, `safety_latch`, `order_timeout`, **`execution_guard`** (blockierte Submits/Replaces nach Spread/Stop/Reduce-only/Replace-Size).
- **Kill-Switch-Events:** `live.kill_switch_events` (arm, release, auto*cancel, flatten*\*).
- **Alerts:** `publish_system_alert` → Redis Stream (vom Monitor/Alert-Pfad konsumiert).
- **Gateway:** `GET /v1/live-broker/audit/recent?category=safety_latch` — gefilterte Einsicht.
- **Metrik:** `live_safety_latch_active` (Monitor-Engine), **Health-Warning:** `live_broker_safety_latch_active`.

## API-Pfade (intern live-broker vs Gateway)

| Aktion                | live-broker (intern)                            | Gateway (Forward, benötigt `LIVE_BROKER_BASE_URL`)     |
| --------------------- | ----------------------------------------------- | ------------------------------------------------------ |
| Kill-Switch arm       | `POST /live-broker/kill-switch/arm`             | `POST /v1/live-broker/safety/kill-switch/arm`          |
| Kill-Switch release   | `POST /live-broker/kill-switch/release`         | `POST /v1/live-broker/safety/kill-switch/release`      |
| Cancel-All (Operator) | `POST /live-broker/safety/orders/cancel-all`    | `POST /v1/live-broker/safety/orders/cancel-all`        |
| Emergency flatten     | `POST /live-broker/orders/emergency-flatten`    | `POST /v1/live-broker/safety/orders/emergency-flatten` |
| Safety-Latch release  | `POST /live-broker/safety/safety-latch/release` | `POST /v1/live-broker/safety/safety-latch/release`     |

Gateway-Mutationen erfordern **sichere Auth** (`audited_sensitive` / `live_broker_safety_mutate`).

## Kein stilles Wieder-Live

- **Safety-Latch** verlangt ein **explizites Release** in der DB (Audit), unabhaengig davon, ob Reconcile wieder `ok` wird.
- **Kill-Switch** verlangt **release** pro Scope/Key.
- Kombination mit Modusmodell: siehe `docs/execution_modes.md`.

## Drill-Evidence vor Live

Simulierte Checks reichen nicht fuer `private_live_allowed`. Vor Live muss der
secret-freie Contract in
`docs/production_10_10/live_safety_drill.template.json` mit echter
Staging-/Shadow-Evidence befuellt und strict geprueft werden:

```bash
python scripts/live_safety_drill.py \
  --evidence-json docs/production_10_10/live_safety_drill.template.json \
  --strict \
  --output-md reports/live_safety_drill.md \
  --output-json reports/live_safety_drill.json
```

Der Nachweis muss Kill-Switch-Arm/Release, Safety-Latch-Submit/Replace-Block,
Emergency-Flatten reduce-only, Exchange-Truth, Cancel-All, Audit, Alert,
Main-Console-State und Reconcile `ok` nach dem Drill belegen. Echte
Exchange-Orders im Drill sind fuer dieses Repo kein Freigabegrund, sondern ein
Blocker.

## ENV

- `LIVE_SAFETY_LATCH_ON_RECONCILE_FAIL` (default `true`) — Latch bei Reconcile `fail` + aktivem Live-Submit.
- `LIVE_ORDER_REPLACE_ENABLED` (default `true`) — globale Replace-Freigabe.
- `LIVE_PREFLIGHT_MAX_CATALOG_METADATA_AGE_SEC` — Katalog-Metadata maximal so alt (Sekunden); `0` = Check aus.
- `LIVE_EXECUTION_MAX_SPREAD_HALF_BPS_MARKET` — Market-Orders: halbe Spread-Breite in bps cap; leer = aus.
- `LIVE_PRESET_STOP_MIN_DISTANCE_BPS` / `LIVE_PRESET_STOP_MIN_SPREAD_MULT` — Preset-Stop vs. Referenz/Spread; leer = aus.
- `LIVE_BLOCK_SUBMIT_ON_RECONCILE_FAIL` / `LIVE_BLOCK_SUBMIT_ON_RECONCILE_DEGRADED` — harte Submit-Sperre bei Reconcile-Status.
- `LIVE_REQUIRE_EXCHANGE_POSITION_FOR_REDUCE_ONLY` (default `true`) — Reduce-only nur mit bekannter Exchange-Position (Snapshot).
- `LIVE_PROBE_PUBLIC_API_BEFORE_ORDER_SUBMIT` — optionaler Public-Health-Check unmittelbar vor Submit.
- `LIVE_SAFETY_LATCH_ON_DUPLICATE_RECOVERY_FAIL` — Latch wenn Duplicate-Response nicht sicher aufgeloest werden kann.

### Alert-Keys (Monitor / `events:system_alert`)

| `alert_key`                                            | Bedeutung                                                            |
| ------------------------------------------------------ | -------------------------------------------------------------------- |
| `live-broker:execution-guard:blocked`                  | Spread-/Stop-/Reduce-only-/Replace-Guard hat Submit/Replace gestoppt |
| `live-broker:execution-guard:reconcile_fail_block`     | Submit wegen Reconcile-Status `fail`                                 |
| `live-broker:execution-guard:reconcile_degraded_block` | Submit wegen Reconcile-Status `degraded` (wenn ENV aktiv)            |
| `live-broker:execution-guard:public_probe_fail`        | Public-Probe vor Submit fehlgeschlagen                               |
| `live-broker:safety-latch:armed:duplicate_recovery`    | Safety-Latch nach Duplicate-Recovery-Failure                         |

Siehe auch: `docs/live_broker.md`, `docs/recovery_runbook.md` (Restart, Exchange-Wahrheit, Divergenz-Metriken, **Postgres-Restore-DR**), `docs/Deploy.md`.

**CI/Integration:** Synchroner Abbruch bei aktivem Safety-Latch (ohne Exchange-Order) wird in
`tests/integration/test_kill_switch_behavior.py` mit migrierter `TEST_DATABASE_URL` geprueft
(siehe `docs/recovery_runbook.md` Abschnitt 8).
