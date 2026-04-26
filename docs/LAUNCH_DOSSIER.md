# Launch-Dossier — Freigabeleiter, Cutover, Notfall, Blocker

Narrativer **Freigabeleiter** (Stufen, Rollback, Index). **Management-SSOT** für Checkboxen, Reihenfolge und Signoff-Fläche ist ausschließlich **`docs/LaunchChecklist.md`**.  
Technische Vorab-Automatisierung: `python tools/release_sanity_checks.py` (u. a. Version-Pinning, Dashboard-/Security-Hinweise) — nicht identisch mit der Checkliste, aber Pflicht-„grün“ vor dem Eintrag im Signoff-Block.  
Deploy- und ENV-Vertrag: `docs/Deploy.md`, `docs/env_profiles.md`. Shadow-/Ramp-Regeln: `docs/shadow_burn_in_ramp.md`. Datenbasierter Burn-in-Report: `python scripts/verify_shadow_burn_in.py`.

---

## 1. Freigabeleiter (Gates pro Stufe)

Jede Stufe ist erst **freigegeben**, wenn alle Gates der Stufe erfuellt sind und ein **schriftliches oder ticketbasiertes OK** (Owner: Trading/Risk + Infra nach Bedarf) vorliegt.

| Stufe                        | Zielmodus                                                                    | Gates (technisch)                                                                                                                                                                                                                                                                                     | Gates (betrieblich)                                                                                                           |
| ---------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **G0 — Merge**               | Entwicklungsstand auf `main`                                                 | CI gruen: Shell-Syntax, `tools/release_sanity_checks.py` (u. a. `package.json` / `pyproject` / `docker-compose` `x-btc-ai-workspace-version` gleich), Ruff, Black (Scope wie CI), Mypy (kritische `shared_py`-Module), Schema-Check, Migrationen, Pytest Unit + Integration mit Coverage-Append, `tools/check_coverage_gates.py`, Dashboard lint+test, Compose `config` + Build+Health (Workflow) | Code-Review; keine Secrets im Diff; Management-SSOT-Checklistenpflege `docs/LaunchChecklist.md` |
| **G1 — Local / Paper**       | `EXECUTION_MODE=paper`                                                       | `scripts/healthcheck.sh` gruen; lokales Profil laut `docs/Deploy.md`                                                                                                                                                                                                                                  | Nur Demo-/Dev-Daten; keine Produktions-DSN                                                                                    |
| **G2 — Shadow (Burn-in)**    | `EXECUTION_MODE=shadow`, `LIVE_TRADE_ENABLE=false`                           | Produktions-ENV ohne Fake-Provider; `LIVE_BROKER_ENABLED=true`; `LIVE_REQUIRE_EXECUTION_BINDING=true`; `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`; `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`; Gateway `GET /v1/system/health` stabil; Reconcile nicht dauerhaft `fail`                          | Repraesentative Burn-in-Matrix ueber Familien, Regime und Spezialistenrouten laut `docs/shadow_burn_in_ramp.md` abgeschlossen |
| **G3 — Live eingeschraenkt** | `EXECUTION_MODE=live`, `LIVE_TRADE_ENABLE=true`, `STRATEGY_EXEC_MODE=manual` | Erstphase bleibt **`RISK_ALLOWED_LEVERAGE_MAX=7`** und **`RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7`**; Mirror nur fuer `candidate_for_live` + `live_mirror_eligible=true` + `shadow_live_match_ok=true`; Bitget-Keys/Passphrase nur zur Laufzeit; Live-Broker enabled; erneut `healthcheck.sh`          | Explizite Live-Freigabe; Kapital- und Positionslimits operativ gesetzt; keine vollautonome Echtgeldfreigabe                   |
| **G4 — Gestufter Ausbau**    | Hebel-, Family- oder Playbook-Erweiterung                                    | Keine Coverage-/Gate-Regression; Shadow-Live-Divergenz- und Risk-Governor-Pfade verstanden (`docs/shadow_live_divergence.md`, `docs/risk_governor.md`); Model-Ops bei Registry-Aenderungen (`docs/model_registry_v2.md`)                                                                              | **Nur** bei stabiler Evidenz pro Ramp-Stufe laut `docs/shadow_burn_in_ramp.md`; schriftliche Freigabe pro Stufe               |
| **G5 — Production (voll)**   | Stabiler Live-Betrieb mit freigegebener Max-Hebel-Policy                     | Observability optional aktiv (`docs/observability.md`); Monitor-Runbook verinnerlicht (`docs/monitoring_runbook.md`); Incident-Kette definiert (siehe unten)                                                                                                                                          | Rechtliches/Compliance; On-Call; Backup/Restore getestet                                                                      |

**Referenz CI:** `.github/workflows/ci.yml`. **Coverage-Zahlen:** `tools/check_coverage_gates.py` (shared_py ≥ 80 %, live_broker ≥ 62 %, kritische Kernmodule ≥ 90 %, High-Risk-Bündel ≥ 81 %).

---

## 2. Konservativer Cutover-Pfad

1. **Local** — Paper-Profil, keine Live-Freigaben; Pipeline und Dashboard verifizieren.
2. **Paper (zentral)** — weiterhin `EXECUTION_MODE=paper` wenn nur Referenz-Paper gewuenscht; sonst Schritt 3.
3. **Shadow** — gleiche Fachlogik wie Live, **keine** echten Exchange-Orders; Reconcile/Kill-Switch/Alerts beobachten.
4. **Live-Mirror mit 7x-Deckel** — fachlich gewuenscht `RISK_ALLOWED_LEVERAGE_MAX=7`; `STRATEGY_EXEC_MODE=manual`, `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`, `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`.
5. **Erweiterung** — Hebel, Familien oder Playbook-Typen nur in Ramp-Stufen mit Messgroessen (Reconcile ok, keine P0-Incidents, Route-Stabilitaet, No-Trade-Qualitaet, Shadow-Live-Divergenz gruen).

Modus-Matrix und Operator-Sicht: `docs/execution_modes.md`, `docs/live_broker.md`.

---

## 3. Rollback, Emergency-Flatten, Kill-Switch, Incident, Forensik

| Thema                 | Vorgehen                                                                                                                                       | Detail-Doku                                          |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| **Rollback Deploy**   | Vorheriges Image/Compose-Revision; `docker compose up -d` mit bekannter Digest/Tag; DB nur bei kompatiblen Migrationen oder Restore aus Backup | `docs/prod_runbook.md`                               |
| **Emergency-Flatten** | P0; Reduce-only / Flatten-Pfad ueber Live-Broker + Gateway-Forward; Audit und Alerts                                                           | `docs/emergency_runbook.md`, `docs/live_broker.md`   |
| **Kill-Switch**       | Arm → Auto-Cancel je Scope; Release nur nach Ursachenanalyse; HTTP 423 auf normale Orders                                                      | `docs/emergency_runbook.md`                          |
| **Safety-Latch**      | Nach Reconcile-`fail` bei Live-Submit; explizites Release, kein stilles Wieder-Live                                                            | `docs/emergency_runbook.md`                          |
| **Incident Response** | P0: Trading-Stopp pruefen, Audit/Alerts; P1: Drift/Stale; Eskalation laut Runbook                                                              | `docs/prod_runbook.md`, `docs/monitoring_runbook.md` |
| **Logs**              | Strukturierte Logs (`LOG_FORMAT=json` in Prod); keine Secrets in Log-Zeilen                                                                    | `docs/Deploy.md`                                     |
| **Forensik DB**       | `live.audit_trails`, `live.kill_switch_events`, `live.reconcile_snapshots`, `live.execution_decisions`, Alert-Outbox                           | `docs/live_broker.md`, `docs/db-schema.md`           |
| **Gateway-Aggregat**  | `GET /v1/system/health` — DB, Redis, Services, Live-Broker-Ops                                                                                 | `docs/stack_readiness.md`                            |

---

## 4. Konsolidierter Doku-Index (Themen → Datei)

| Thema                                            | Datei                                                                                                |
| ------------------------------------------------ | ---------------------------------------------------------------------------------------------------- |
| Freigabeleiter / CI-Gates (Merge, RC, Prod)      | **dieses Dossier**, `docs/ci_release_gates.md`                                                       |
| **Checkliste (SSOT, Management-Abnahme)**      | `docs/LaunchChecklist.md` (allein verbindlich für /ops+Management)                                   |
| Deploy, ENV, Profile                             | `docs/Deploy.md`, `docs/env_profiles.md`, `docs/compose_runtime.md`                                  |
| Readiness, Startreihenfolge                      | `docs/stack_readiness.md`                                                                            |
| Produktions-Runbook                              | `docs/prod_runbook.md`                                                                               |
| Monitoring                                       | `docs/monitoring_runbook.md`, `docs/observability.md`                                                |
| Security / Gateway                               | `docs/api_gateway_security.md`, `docs/security_ops.md`                                               |
| Live-Broker / Bitget                             | `docs/live_broker.md`, `docs/bitget-config.md`                                                       |
| Risk / Governor / Shadow-Live                    | `docs/risk_governor.md`, `docs/shadow_live_divergence.md`, `docs/execution_modes.md`                 |
| Shadow-Burn-in / Echtgeld-Ramp                   | `docs/shadow_burn_in_ramp.md`                                                                        |
| Dashboard / Operator                             | `docs/dashboard_operator.md`, `docs/dashboard_operator_console.md`                                   |
| SOPs / Onboarding / Statussprache                | `docs/operator_sops.md`, `docs/operator_onboarding_checklist.md`, `docs/operator_status_language.md` |
| Finaler Abschlussstand (technische Endbewertung) | **`FINAL_READINESS_REPORT.md`** (Repo-Root)                                                          |
| **Launch-Paket (Index)**                         | **`docs/LAUNCH_PACKAGE.md`**                                                                         |
| Betreiberhandbuch (Edge, Health, Backup)         | `docs/OPERATOR_HANDBOOK.md`                                                                          |
| Externe Go-Live-Abhaengigkeiten                  | `docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md`                                                              |
| Plaene / Metering / Caps                         | `docs/PRODUCT_PLANS_AND_USAGE.md`, `docs/commercial_transparency.md`                                 |
| Integration / Stack-Tests                        | `docs/integration_full_stack_scenarios.md`                                                           |
| Test-/Kern-Gefahren (Unit)                       | `docs/testing_core_hazard_coverage.md`                                                               |
| Audit-Gaps (bekannte Grenzen)                    | `docs/REPO_FREEZE_GAP_MATRIX.md`; Verweis `docs/SYSTEM_AUDIT_MASTER.md`                              |
| SBOM / Lockfiles                                 | `docs/REPO_SBOM_AND_RELEASE_METADATA.md`, `infra/service-manifest.yaml` (`release_auditability`)     |

---

## 5. Echte externe Blocker (nicht durch Repo/Cursor allein loesbar)

- **Secrets:** Bitget API Key/Secret/Passphrase, DB/Redis-Produktionspasswoerter, `GATEWAY_JWT_SECRET`, Telegram-Bot-Token, Grafana-Admin — Beschaffung, Rotation, Speicher in Vault/KMS/Secret Manager.
- **Domain, TLS, Ingress:** Oeffentliche URLs, Zertifikate, Load Balancer, WAF — Infrastruktur-Team.
- **Kapitallimits und Kontofuehrung:** Exchange-Konto, Margin, erlaubte Produkte, Verlustbudget — Trading/Treasury.
- **Recht / Compliance:** DSGVO, MiCA, lokal regulatorische Freigaben — Rechts-/Compliance-Rolle.
- **Operative Sign-offs:** Freigabe fuer Live-Modus, Hebel-Erhoehung, Auto-Strategie (`STRATEGY_EXEC_MODE=auto`) — dokumentierte Entscheidung.
- **Bitget-Kontingente / API-Status:** Rate-Limits, Wartungsfenster, regionale Verfuegbarkeit — externer Dienst.
- **Backup/DR:** Postgres-Backups, RTO/RPO, Restore-Uebungen — Betrieb.
- **Webhook-Telegram (optional):** Technisch im Service implementiert, aber ohne externen Ingress, DNS und TLS nicht nutzbar — siehe `docs/alert_engine.md`.

---

## 6. Secrets-Plan

Die Produktgrenze ist erreicht, wenn diese Themen **nur noch extern** offen sind:

- Secret-Beschaffung
- Secret-Rotation
- Secret-Injektion zur Laufzeit
- Rechtevergabe fuer Operatoren und Infrastruktur

Nicht ins Repo gehoeren:

- Bitget API Key / Secret / Passphrase
- `GATEWAY_JWT_SECRET`
- `GATEWAY_INTERNAL_API_KEY`
- `ADMIN_TOKEN`
- Telegram-Bot-Token / Webhook-Secret
- DB-/Redis-Produktionscredentials

Vorgehen:

1. Werte nur aus Vault/KMS/Secret-Manager injizieren
2. keine Klartext-Secrets in `.env` committen
3. Rotation und Zugriffsrechte ausserhalb des Repo dokumentieren

---

## 7. Approval- und Telegram-Flow

### Mirror-Freigabe

- Vorbedingung: `operator_release_pending`
- Ressource: bestehende `execution_id`
- Freigabeweg:
  - Telegram-Zweistufenpfad oder
  - Gateway `manual-action/mint` + `operator-release`

### Telegram-Kommandos (kanonisch)

- Lesen:
  - `/status`
  - `/lastsignal`
  - `/lastnews`
  - `/mute`
  - `/unmute`
- Operator:
  - `/exec_recent`
  - `/exec_show <execution_uuid>`
  - `/release_step1 <execution_uuid>`
  - `/release_confirm <pending> <code>`
  - `/release_abort <pending_uuid>`
  - `/emerg_step1 <internal_order_uuid>`
  - `/emerg_confirm <pending> <code>`
  - `/emerg_abort <pending_uuid>`

Telegram bleibt dabei strikt:

- lesend
- erklärend
- bestätigend
- ausführend nur für gebundene bestehende Ressourcen

---

## 8. Recovery, Incident und Post-Trade-Review

### Recovery / Incident

- Kill-Switch
- Safety-Latch
- Emergency-Flatten
- Reconcile-Drift
- Data-Stale
- Gateway-/Telegram-Anomalien

Details: `docs/prod_runbook.md`, `docs/monitoring_runbook.md`,
`docs/runbooks/forensics_and_incidents.md`, `docs/emergency_runbook.md`

### Post-Trade-Review

Nach jeder Echtgeld-Mirror-Phase oder jedem relevanten Incident:

1. `live-broker/forensic/[id]` lesen
2. `learn.e2e_decision_records` / `learn.trade_evaluations` prüfen
3. Shadow-vs-Live- und Stop-Budget-Verhalten dokumentieren
4. Nur evidenzbasiert in die nächste Ramp-Stufe gehen

---

## 9. Endbewertung des Repos (knapp)

- **Staerken:** Deterministischer Signal-/Risk-Kern, klare Modus-Matrix (paper/shadow/live), Live-Broker als Control-Plane mit Kill-Switch, Latch, Reconcile, dokumentierte Notfallpfade, CI mit Lint, Typing (Kern), Tests, Coverage-Gates, Compose-Health.
- **Grenzen:** Vollstaendiger End-to-End-Replay inkl. aller Zufaellskomponenten ist nicht als abgeschlossen dokumentiert (`REPO_FREEZE_GAP_MATRIX.md`); einige Betriebsfaehigkeiten wie Telegram-Webhook sind zwar technisch vorhanden, aber ohne externe Infrastruktur nicht einsatzbereit.
- **Launch-Entscheidung:** Siehe Abschnitt 7.

---

## 10. Go / No-Go fuer echten Launch

**Go (technisch vorbereitet),** wenn G0–G3 erfuellt sind, Burn-in G2 abgeschlossen ist, externe Blocker aus Abschnitt 5 fuer **eure** Umgebung geklaert sind, und ein Owner **G3 Live eingeschraenkt** schriftlich freigibt.

**No-Go,** solange: Secrets fehlen oder liegen im Klartext im Repo; `healthcheck.sh` oder Migrationen schlagen fehl; dauerhaft `fail`/unklare Reconcile-Lage bei geplantem Live; keine Rollback-Revision dokumentiert; rechtliche Freigabe fehlt.

## 11. Finale 10/10-Abschlusspruefung

Vor jeder privaten Live-Freigabe muss zusaetzlich der finale Report erzeugt werden:

```bash
python scripts/final_go_no_go_report.py --output-md reports/final_go_no_go_report.md --output-json reports/final_go_no_go_report.json
```

Regel:

- `private_live_allowed` darf nur `YES` sein, wenn keine offenen P0/P1-Live-Blocker,
  keine fehlende Runtime-Evidence und ein gueltiger Owner-Release vorliegen.
- `full_autonomous_live` bleibt ohne lange echte Live-Historie immer `NO`.

---

_Letzte inhaltliche Synchronisation: CI-Workflow, `tools/check_coverage_gates.py`, Runbooks wie oben verlinkt._
