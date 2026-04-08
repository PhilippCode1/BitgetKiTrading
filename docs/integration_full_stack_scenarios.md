# Full-Stack-Integration und Recovery (Prompt 35)

Wiederholbare Szenarien: DB/Redis laufen in **CI** (`pytest tests/integration -m integration`); HTTP-/Compose-Pfade brauchen gesetzte URLs wie in `scripts/healthcheck.sh`.

Ohne erreichbare `TEST_DATABASE_URL` / `TEST_REDIS_URL` werden die Stack-Recovery-Tests **uebersprungen** (kein harter Fehler auf dem Laptop ohne Docker).

## 1. CI ohne Compose (Postgres + Redis)

| Szenario                          | Testmodul                                | Ausloesung                                                                                                                              |
| --------------------------------- | ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **Reconcile-Catch-up sichtbar**   | `test_db_live_recovery_contracts`        | Insert `live.reconcile_snapshots` mit `details_json.drift.total_count`; `fetch_ops_summary` (wie Gateway) liefert gleichen Drift-Total. |
| **Kill-Switch-Zaehlung**          | `test_db_live_recovery_contracts`        | SQL `arm` + `release` auf `service`/`service`; aktive Zaehlung entspricht Gateway-Subquery.                                             |
| **Safety-Latch aus Audit**        | `test_db_live_recovery_contracts`        | Letztes `live.audit_trails` mit `category=safety_latch` steuert `safety_latch_active`.                                                  |
| **Redis Fault-Injection**         | `test_redis_fault_injection`             | WRONGTYPE auf Key, neue Connection liest konsistent; Pipeline-Burst.                                                                    |
| **Falsche Modus-Flags**           | `test_integration_subprocess_mode_gates` | Subprocess: `EXECUTION_MODE=shadow` + `LIVE_TRADE_ENABLE=true` → `ValueError` bei `BaseServiceSettings`.                                |
| **Shadow-Live-Divergenz (Logik)** | `test_shadow_live_divergence_contract`   | `assess_shadow_live_divergence`: harte vs. weiche Verletzungen deterministisch.                                                         |

## 2. Mit laufendem Compose / Stack-URLs

| Szenario                          | Variablen                                           | Test / Skript                                                                                                                       |
| --------------------------------- | --------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| **Feed / Service-Reconnect**      | `MARKET_STREAM_URL`                                 | `test_http_stack_recovery::test_market_stream_ready_retry_simulates_reconnect_window` (mehrere GET-Versuche).                       |
| **Broker-Readiness nach Restart** | `LIVE_BROKER_URL`                                   | `GET /live-broker/reconcile/latest` (Shape).                                                                                        |
| **Shadow vs. Live Evaluate**      | `LIVE_BROKER_URL`                                   | Zwei `POST /live-broker/executions/evaluate`; bei Live-Candidate optional `shadow_live_divergence` in `payload_json`.               |
| **Aggregiertes Health / Feed**    | `API_GATEWAY_URL`, `INTEGRATION_GATEWAY_JWT_SECRET` | `GET /v1/system/health` inkl. `market-stream`-Eintrag.                                                                              |
| **Kill-Switch Chaos (Mutation)**  | zusätzlich `INTEGRATION_SAFETY_MUTATIONS=1`         | Gateway `POST .../kill-switch/arm` dann `release` (skip bei Broker-Fehler).                                                         |
| **Voller Smoke**                  | alle `*_URL` aus `healthcheck.sh`                   | `RUN_COMPOSE_SMOKE=1 pytest ...::test_compose_stack_smoke_via_healthcheck_script` oder `bash scripts/integration_compose_smoke.sh`. |

## 3. Chaos- und Recovery-Hinweise

- **Broker-Disconnect**: Ohne echten Exchange reicht der opt-in Kill-Switch-Test; echte Disconnects sind Betriebssache (Circuit, 503) — siehe `tests/unit/live_broker` und Live-Mock-Contracts.
- **`requestTime`-Drift in Mocks**: Private-REST aktualisiert Offsets aus Payloads; Integrations-Mocks muessen konsistente Zeiten liefern (siehe Unit-Fixes im Live-Broker-Client).
- **DB-Reconcile**: Gateway liest nur die **letzte** `reconcile_snapshots`-Zeile — Recovery-Tests pruefen genau diese Ops-Sicht.

## 4. Kommandos

```bash
# CI-aehnlich (nach Migration auf dieselbe DB)
export TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ci_dummy
export TEST_REDIS_URL=redis://localhost:6379/1
export DATABASE_URL="$TEST_DATABASE_URL"
export REDIS_URL=redis://localhost:6379/0
pytest tests/integration tests/learning_engine -m integration -q

# Optional Compose (URLs aus .env.local / healthcheck)
export API_GATEWAY_URL=http://localhost:8000
export INTEGRATION_GATEWAY_JWT_SECRET=<wie Stack>
export MARKET_STREAM_URL=http://localhost:8010
export LIVE_BROKER_URL=http://localhost:8120
pytest tests/integration -m integration -q

# Bewusste Kill-Switch-Mutation (nur isolierte Umgebung)
export INTEGRATION_SAFETY_MUTATIONS=1
pytest tests/integration/test_http_stack_recovery.py::test_gateway_kill_switch_chaos_arm_then_release_opt_in -q
```
