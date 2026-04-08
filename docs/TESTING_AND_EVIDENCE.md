# Testing und Evidenz (institutioneller Rahmen)

Dieses Dokument fasst **Kommandos**, **Gates**, **Marker** und **bewusste Restdefizite** zusammen.

Release-/Doku-Bereinigung und Ballast-Log: `docs/RELEASE_CLEANUP_REPORT.md`.

Produkt-Launch (Betrieb, Plaene, externe Abhaengigkeiten): `docs/LAUNCH_PACKAGE.md`. Es ersetzt keine CI-Logs, dokumentiert aber, wie Evidenz lokal und in der Pipeline erzeugt wird.

## Python (Unit + Integration)

```bash
# Schneller Kern (ohne Integration)
pytest tests shared/python/tests -m "not integration" -q

# Integration (benoetigt TEST_DATABASE_URL / Services je nach Suite)
pytest tests shared/python/tests -m integration -q

# Contract-Parity (subprocess, keine externe Infra)
python tools/check_contracts.py

# Coverage kombiniert (wie CI: zuerst Unit, dann Integration anhaengen)
coverage erase
coverage run -m pytest tests shared/python/tests -m "not integration"
coverage run -a -m pytest tests shared/python/tests -m integration
coverage report
python tools/check_coverage_gates.py
```

### Globales Coverage-Floor

- `pyproject.toml` / `.coveragerc`: `fail_under = 25` — verhindert ein triviales „0 % und grün“ bei `coverage report`.
- **Primäre harte Gates:** `tools/check_coverage_gates.py` (z. B. `shared_py` ≥ 80 %, kritische Pfade ≥ 90 %, Live-Broker-Minimum, High-Risk-Liste).

### Pytest-Marker (Auszug)

| Marker           | Bedeutung                                                                |
| ---------------- | ------------------------------------------------------------------------ |
| `integration`    | DB/Services                                                              |
| `stack_recovery` | HTTP/Redis/DB-Recovery-nahe Integrationspfade                            |
| `chaos`          | Stale/Queue/Druck-Szenarien (überwiegend Unit mit strukturierten Inputs) |
| `security`       | Auth-Klassifikation, SSE-Zugriff, Leakage-nahe Checks                    |
| `slow`           | Längere Laufzeit                                                         |

## Dashboard (Jest)

```bash
pnpm --dir apps/dashboard run test:ci
```

- Kein `--passWithNoTests`: fehlende Suites sind ein Fehler (`tools/release_sanity_checks.py` und `tools/run_tests.sh` im Einklang).
- Coverage-Schwellen: `apps/dashboard/jest.config.cjs` (`coverageThreshold`).

## Shell-Orchestrierung

```bash
bash tools/run_tests.sh
```

Führt pytest und — falls `pnpm`/`npm` vorhanden — Dashboard-Tests aus.

## Evidenz zu Auftragskategorien (Stand Repo)

API-Beispiel-Payloads (Monitor, Learning-Drift), Zahlungs-Sandbox/Live-Matrix: **`docs/PRODUCTION_READINESS_AND_API_CONTRACTS.md`**.

Windows: strukturierte Nachweise nach `artifacts/release-evidence/<ts>/`: **`pnpm run rc:evidence`**.

| Thema                                       | Wo belegt                                                                                                                 |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Capability Matrix / Market Universe         | `tests/unit/api_gateway/test_db_market_universe_queries.py`, Dashboard `MarketCapabilityMatrixTable.test.tsx`             |
| Contract Parity                             | `python tools/check_contracts.py`, `tests/unit/tools/test_contract_parity_gate.py`                                        |
| Replay-Determinismus                        | u. a. `tests/**/test_event_envelope_determinism.py`, `shared_py/replay_determinism`                                       |
| Specialist / Adversary                      | `tests/signal_engine/test_specialist_ensemble_adversary.py`, `test_specialist_hierarchy_adversary.py`                     |
| Stop-Budget / Leverage                      | `tests/signal_engine/test_stop_budget_policy.py`, `tests/shared/test_unified_leverage_allocator.py`                       |
| Live-Broker Fehler / Reconcile / Idempotenz | `tests/unit/live_broker/`, Integrations-Suites unter `tests/integration/`                                                 |
| Telegram-Governance                         | `tests/alert_engine/` (Telegram/Operator)                                                                                 |
| Auth / Manual Action / Rate Limits          | `tests/unit/api_gateway/test_gateway_auth.py`, `test_manual_action.py`, `test_rate_limit_path_classification.py`          |
| Pricing / Usage                             | `tests/unit/api_gateway/test_commerce_pricing.py`                                                                         |
| Dashboard-Auth-Sichtbarkeit                 | `SidebarNav.test.tsx`, `console-access-policy.test.ts`                                                                    |
| Shadow→Live-Mirror                          | `tests/integration/test_shadow_live_divergence_contract.py`, `tests/unit/shared_py/test_shadow_live_divergence_mirror.py` |
| Stale / Queue / Reconcile-Alerts (Unit)     | `tests/unit/monitor_engine/test_alerts_chaos_pressure.py`                                                                 |
| SSE-Schutz                                  | `test_live_sse_stream_rejects_unauthenticated_when_sensitive_enforced` in `test_gateway_security_hardening.py`            |

## Performance- und Chaos-Tests

- **Im Repo:** Überwiegend **deterministische Unit-/Integrationstests** mit klaren Inputs (z. B. Monitor-Alert-Pipeline, Stack-Recovery-Marker). Sie belegen Logik und Prioritäten, nicht physische Netzwerk-Ausfälle.
- **Extern / Staging (Blocker für „echtes“ Chaos):** Echte Bitget-WebSockets, produktionsnahe Latenz, partieller Redis-Cluster-Ausfall und brokerseitige Rate-Limits sind **ohne dedizierte Staging-Pipeline und Freigaben** nicht reproduzierbar automatisierbar; dort bleiben **manuelle oder soak/chaos-Job-Runner** erforderlich.

### Soak- und Chaos-Läufe (Staging / Operator)

Pflicht im Sinne des **Roadmap-10-Abschlusses** ist die **Dokumentation** und ein **nachvollziehbarer Staging-Prozess** — kein Dauerlauf gegen Bitget-Produktion im öffentlichen CI.

| Schritt              | Zweck                                | Belege / Kommandos                                                                                                                         |
| -------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Stack hochfahren     | Stabilität unter Last (Paper/Shadow) | `docker compose` laut `docs/Deploy.md`; optional Profil `observability` für Grafana/Prometheus                                             |
| Heartbeats & Alerts  | Keine „stille“ Pipeline              | `docs/monitoring_runbook.md`, Grafana `bitget-trading-ops` (Worker-Heartbeat-Alter)                                                        |
| Recovery / Reconcile | Ops nach simuliertem Fehler          | `docs/recovery_runbook.md` § 8; `GET /live-broker/reconcile/latest`, `GET /health` (siehe `tests/integration/test_http_stack_recovery.py`) |
| Mutations-Sicherheit | Keine blinden Live-Mutationen in CI  | Nur mit explizitem `INTEGRATION_SAFETY_MUTATIONS=1` und Staging-URLs (Runbook / Integration-README)                                        |
| Dauer (Soak)         | Memory-Leaks, WS-Reconnect           | z. B. 12–24 h Paper/Shadow; Ergebnis in Ticket/Release-Notiz — nicht im Repo als fester Log-Pfad                                           |

**ADR (Accepted Risk):** `docs/adr/ADR-0010-roadmap-accepted-residual-risks.md`.

## Security-Tests

- Auth-Bypass und unautorisierte Mutation: Gateway-Tests unter `tests/unit/api_gateway/test_gateway_*.py`.
- Replay / Idempotenz: Live-Broker- und Event-Contract-Suites (siehe Tabelle oben).
- Secret-Leakage: `shared/python/tests/test_execution_forensic_snapshot.py`, `tests/unit/shared_py/test_operator_intel.py`, `tests/unit/config/test_bootstrap.py`.

## Ehrliche Restdefizite

1. **Vollständiger WS-Reconnect gegen die Exchange:** Kein Dauer-Test gegen Live-Market-Stream ohne Staging-Credentials und SLA; aktuell nur logik-/mock-basierte Pfade.
2. **Redis/DB „hard down“ unter Last:** Integrationspfade existieren marker-basiert; ein **gleichzeitiger** Ausfall mehrerer Datenhaltungen mit Queue-Backpressure ist nicht als deterministischer Dauer-Test im Open-Source-Repo abgebildet.
3. **`check_coverage_gates.py` mit partieller `.coverage`:** Lokal schlägt das Gate fehl, wenn nur ein Teil der Suite gelaufen ist — **erwartetes Verhalten**; vollständiger Lauf wie in CI ist die Referenz.

## Referenz-Lauf (Beispiel, diese Session)

- Neu fokussierte pytest-Module: **22 passed** (Shadow-Live-Mirror, Contract-Gate, Monitor-Chaos-Alerts, Rate-Limit-Klassifikation, SSE-401).
- Dashboard `pnpm run test:ci`: **10 Suites, 46 Tests**, Coverage-Gate grün (global ca. 92 % Statements / 83 % Branches im erfassten Set).

Datum der Stichprobe: siehe Commit bzw. lokale CI-Ausführung — Werte variieren mit Suite-Umfang.
