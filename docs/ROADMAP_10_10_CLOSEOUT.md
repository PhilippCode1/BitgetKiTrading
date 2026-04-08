# Roadmap 10-Stufen — Abschlussaudit (Monorepo)

**Stand:** 2026-04-01  
**Regel:** Gleiche Evidenzdisziplin wie `docs/FINAL_SCORECARD.md` — **keine Behauptung „10/10 gesamt“**, wo material offene Lücken oder **Accepted Risk** ohne Produktionsnachweis bleiben.

## Zielbild „10/10“ (Repo-Sinn)

Wie `docs/FINAL_READINESS_REPORT.md` / Masterplan: **operator-gated, auditierbar, beobachtbar, reproduzierbar** — nicht vollautonomer Live ohne Grenzen.  
**10** pro Scorecard-Zeile nur, wenn Truth-/Gap-Matrix und CI für diese Dimension keinen **major**-Befund mehr listen.

## Umsetzungsmatrix (Stufen 1–10)

| Stufe | Thema                           | Primäre Belege im Repo                                                                                                |
| ----- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| 1     | Config-/Profil-Freeze           | `config/paths.py`, `COMPOSE_ENV_FILE`, `docs/env_profiles.md`, `tests/unit/config/test_env_path_resolution.py`        |
| 2     | Risk / Hebel vs. Burn-in        | `RISK_ELEVATED_LEVERAGE_LIVE_ACK`, `config/settings.py`, Launch-/Checklisten-Doku                                     |
| 3     | Multi-Asset / Fixture-Drift     | Paper-Fixtures, `.env.production.example`, `tests/paper_broker/test_contract_config_family_matrix.py`                 |
| 4     | Replay-Determinismus (Envelope) | `shared_py/eventbus/envelope.py`, `docs/replay_determinism.md`, Tests                                                 |
| 5     | LLM-Pfad / API-Vertrag          | `llm_orchestrator/constants.py`, `service.py` health, Backoff ohne RNG                                                |
| 6     | Security-Gates CI               | `tools/pip_audit_supply_chain_gate.py`, `tools/check_production_env_template_security.py`, `.github/workflows/ci.yml` |
| 7     | Observability 1.0               | `infra/observability/grafana/dashboards/bitget-trading-ops.json`, Worker-`touch_worker_heartbeat` in Kern-Loops       |
| 8     | Contract-Parität                | `tools/check_contracts.py` (Katalog↔TS↔Schema↔OpenAPI-Kern), `tests/unit/contracts/test_openapi_export_sync.py`       |
| 9     | Live-Broker Reconcile/Recovery  | `tests/integration/test_http_stack_recovery.py`, `test_db_live_recovery_contracts.py`, `docs/recovery_runbook.md` § 8 |
| 10    | Abschlussaudit                  | Dieses Dokument; Aktualisierung `FINAL_SCORECARD`, `REPO_FREEZE_GAP_MATRIX`, `TESTING_AND_EVIDENCE`                   |

## Accepted Risk (bewusst nicht „10“ ohne Staging)

| Thema                                                     | Begründung                                                                                                                     | Nachziehen                                             |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| **Multi-Asset über ein Symbol pro market-stream-Instanz** | Katalog/metadata sind da; vollständiger Parallel-Betrieb mehrerer Primärinstrumente pro Deployment ist Betriebs-/Sizing-Thema. | Staging-Matrix, `REPO_TRUTH_MATRIX`                    |
| **Echte Exchange-Chaos / Soak**                           | Kein Dauerlauf gegen Bitget-Produktion im Open-Source-CI.                                                                      | Staging: `docs/TESTING_AND_EVIDENCE.md` Soak-Abschnitt |
| **Vollständige Payload-Schemas aller `event_type`**       | Kern-Envelope + Katalog gesichert; Payload-Tiefe iterativ.                                                                     | `shared/contracts/schemas/`, `contracts_extension.md`  |
| **Gateway-Response-Typing 100 %**                         | OpenAPI-Sync für Gateway; nicht jede BFF-Antwort ist generiert.                                                                | `shared/ts`, Contract-Gates                            |

## Evidenz-Checkliste (Release)

- [ ] `python tools/release_sanity_checks.py`
- [ ] `python tools/check_contracts.py`
- [ ] `python tools/check_production_env_template_security.py` (bei Bedarf)
- [ ] CI-Äquivalent: `.github/workflows/ci.yml` (inkl. Coverage-Gates, pip-audit, Compose-Smoke)
- [ ] Optional Staging: Integration mit `TEST_DATABASE_URL`, `INTEGRATION_LIVE_BROKER_URL` / Compose

## Verweis

- Scorecard-Zahlen: **`docs/FINAL_SCORECARD.md`**
- Detaillierte Lücken: **`docs/REPO_FREEZE_GAP_MATRIX.md`**
- Restrisiken ADR-Kurzform: **`docs/adr/ADR-0010-roadmap-accepted-residual-risks.md`**
