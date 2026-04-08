# Recovery-Runbook — Live-Broker / Exchange-Wahrheit

Normativ ergaenzend zu `docs/emergency_runbook.md`, `docs/live_broker.md`, `docs/prod_runbook.md`.

## 1. Quellen der Wahrheit (Restart & Netzwerkfehler)

| Ebene                  | Persistenz                                          | Zweck                                                                                   |
| ---------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------------- |
| **Orders**             | `live.orders`, `live.order_actions`                 | Lokaler Order-Lifecycle inkl. Replace-Kette, `client_oid`, `exchange_order_id`, Status  |
| **Fills**              | `live.fills` (idempotent ueber `exchange_trade_id`) | Ausgefuehrte Teilausfuehrungen / komplette Fills                                        |
| **Exchange-Snapshots** | `live.exchange_snapshots`                           | Letzte REST-Catchup- und WS-aggregierte Truth fuer `orders`, `positions`, `account`     |
| **Execution-Journal**  | `live.execution_journal`                            | Audit-Pfad: `order_submit`, `order_exchange_ack`, `fill`, `reconcile`, Operator-Release |
| **Exit-Plaene**        | `live.exit_plans`                                   | Stop-/TP-/Runner-Zustand, `last_decision_json`, `context_json` — **restart-faehig**     |
| **Operator-Freigaben** | `live.execution_operator_releases`                  | Gebundene Live-Opens (kein Telegram-Write auf Strategie)                                |
| **Reconcile**          | `live.reconcile_snapshots`, `live.reconcile_runs`   | Zyklischer Gesundheits- und Drift-Report inkl. `drift.divergence`                       |
| **Shadow/Live-Gates**  | `live.shadow_live_assessments`                      | Persistierte Match-/Gate-Reports pro `execution_decision_id` (kein Chat-Write)          |

Nach Neustart rekonstruiert der Worker den Runtime-Read-Model-Pfad aus **Orders + Snapshots + Fills + Journal-Tail + aktiven Exit-Plaenen** (`LiveBrokerRepository.reconstruct_runtime_state`). Shadow-/Mirror-Freigaben vor Live bleiben in `live.shadow_live_assessments` und `live.execution_operator_releases` nachvollziehbar.

## 2. Reconcile-Loop (Worker-Intervall)

Pro Takt (Standard `LIVE_RECONCILE_INTERVAL_SEC`):

1. **Order-Timeouts** — haengende Submits (`LIVE_ORDER_TIMEOUT_SEC`).
2. **`LiveReconcileService.run_once`** — Schema, Exchange-Probe, Recovery-State, Drift + **Divergenz-Metriken**.
3. **`LiveExitService.run_once`** — aktive Exit-Plaene gegen Positions-Snapshot und Markt.

Parallel: **Private-WS** → `ExchangeStateSyncService` aktualisiert Orders/Fills/Snapshots. Bei Connect/Reconnect optional **REST-Catchup** (`LIVE_BROKER_REST_CATCHUP_ON_WS_CONNECT`).

Optional: **`LIVE_RECONCILE_REST_CATCHUP_ON_WS_STALE=true`** — wenn der Reconcile-Pfad eine stale/trennende Private-WS-Lage erkennt, stoesst der Worker eine **zusaetzliche** Catchup-Queue (`ws_stale_reconcile`) an (gleicher Pfad wie `run_rest_snapshot_catchup`).

## 3. Divergenz-Metriken (`details_json.drift.divergence`)

Strukturierte Sicht auf **Journal-Intent**, **lokale Orders** und **Exchange-Snapshots** (ohne LLM):

| Block                               | Bedeutung                                                                                                                                                                                             |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `missing_exchange_ack`              | Offene Orders ohne `exchange_order_id`, aelter als `LIVE_RECONCILE_ORDER_ACK_STALE_SEC` (fehlendes Ack / Desync-Risiko).                                                                              |
| `journal_tail`                      | Letzter bekannter `execution_journal`-Phase je Order; Zaehler offener Orders, deren **neuester** Journaleintrag noch `order_submit` ist.                                                              |
| `fill_ledger`                       | Summe der juengsten Fills vs. Ordergroesse: Hinweise auf **Teilfills**, die im Order-Status noch nicht als partial reflektiert sind (optional degradiert ueber `LIVE_RECONCILE_FILL_DRIFT_DEGRADES`). |
| `private_ws`                        | `connection_state`, Alter des letzten WS-Events, Flags `stale_while_connected`, `disconnected_while_required`, `enqueue_rest_catchup`.                                                                |
| `exit_plans_restart`                | Zusammenfassung aktiver Exit-Plaene aus der DB (Restart-Faehigkeit).                                                                                                                                  |
| `degrade_increment_from_divergence` | Anteil, der in `drift.total_count` eingeht (gesteuert durch `LIVE_RECONCILE_*_DEGRADES`).                                                                                                             |

## 4. Operator-Aktionen

| Situation                                           | Aktion                                                                                                                                   |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `missing_exchange_ack` > 0                          | Order per `client_oid` / `exchange_order_id` an der Boerse abfragen; ggf. einzeln canceln oder mit Exchange abgleichen; Journal pruefen. |
| `journal_tail` zeigt haengende `order_submit`       | REST order-detail / open-orders; Netzwerk- und Idempotenz-Keys pruefen.                                                                  |
| `snapshot_health` missing/stale                     | Private API / WS pruefen; manuell **REST-Catchup** ausloesen (Reconnect oder Ops-Prozess); Bitget-Statuspage.                            |
| `private_ws.enqueue_rest_catchup` (bei aktivem ENV) | Worker stoest Catchup an — Logs auf `rest snapshot catchup` pruefen.                                                                     |
| Reconcile `fail` + Live-Submit                      | Safety-Latch moeglich (`LIVE_SAFETY_LATCH_ON_RECONCILE_FAIL`); **Release** nur nach Ursachenanalyse (`emergency_runbook`).               |
| Exit-Plan `invalid` / `evaluation_failed`           | Audit `live.audit_trails`; Positions-Snapshot und Metadaten; kein stilles Re-Live.                                                       |

## 5. Automatische Grenzen

- **Submit-Gates** bei Reconcile `fail`/`degraded` (ENV `LIVE_BLOCK_SUBMIT_ON_RECONCILE_*`).
- **Kill-Switch** / **Safety-Latch** laut Emergency-Runbook.
- **Order-Timeout-Cancel** fuer haengende Live-Orders.
- **Execution-Guards** (Spread/Stop/Reduce-only) unabhaengig vom Reconcile-Loop.

## 6. No-Go-Zustaende (Release nicht „gruen“ ignorieren)

- Reconcile **`fail`** bei aktivem **Live-Submit** ohne dokumentierte Ursache und ohne Latch-/Operator-Entscheidung.
- **Persistenter** `missing_exchange_ack` auf Kernsymbolen trotz frischem REST-Catchup (wahrscheinlich API-/Konto- oder Routing-Fehler).
- **Gleichzeitig** hohe Order-Drift (`local_only` + `exchange_only`) und fehlende Positions-Snapshots — manueller Abgleich vor neuen Live-Opens.
- Telegram oder Chat aendert **keine** Strategieparameter; Recovery laeuft nur ueber DB/Exchange/Ops-Routen.

## 7. Verwandte ENV-Variablen

Siehe `.env.example`: `LIVE_RECONCILE_ORDER_ACK_STALE_SEC`, `LIVE_RECONCILE_PRIVATE_WS_STALE_SEC`, `LIVE_RECONCILE_JOURNAL_TAIL_LIMIT`, `LIVE_RECONCILE_MISSING_EXCHANGE_ACK_DEGRADES`, `LIVE_RECONCILE_FILL_DRIFT_DEGRADES`, `LIVE_RECONCILE_WS_STALE_DEGRADES`, `LIVE_RECONCILE_REST_CATCHUP_ON_WS_STALE`, sowie bestehende `LIVE_BROKER_REST_CATCHUP_*`.

## 8. Nachweise im Repo (Integration / CI)

| Pruefung                        | Ort                                                    | Was abgesichert ist                                                                                                                                                                                                                                                       |
| ------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Reconcile-HTTP-Vertrag          | `tests/integration/test_http_stack_recovery.py`        | `GET …/live-broker/reconcile/latest`: bei vorhandenem Snapshot `status`, `details_json` mit `drift`, `recovery_state`, `exchange_probe`, `execution_controls`, `drift.total_count`. `GET /health`: `latest_reconcile` ist Objekt; bei Daten `status` in ok/degraded/fail. |
| Ops-Summary / Drift             | `tests/integration/test_db_live_recovery_contracts.py` | `fetch_ops_summary`: Drift aus `details_json` → `latest_reconcile_drift_total` (bestehend); **neu:** FK-Kette `reconcile_runs` ↔ `reconcile_snapshots`, Abschluss `status=completed` und Join.                                                                            |
| Reconcile-Logik (ohne Exchange) | `tests/unit/live_broker/test_reconcile_service.py`     | `LiveReconcileService.run_once`: Safety-Latch, Drift, Paper-Modus, Divergenz-Journal — siehe dort fuer Szenarien.                                                                                                                                                         |

**Compose/CI:** Stack-Tests setzen `INTEGRATION_LIVE_BROKER_URL` bzw. `LIVE_BROKER_URL` und `TEST_DATABASE_URL` (siehe `.github/workflows/ci.yml`, Integration-Job). Ohne laufenden Live-Broker werden HTTP-Tests **skipped**, nicht rot.
