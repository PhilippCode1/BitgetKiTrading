# Ops-Quickstart — ein Einstieg für Betrieb & On-Call

**Ziel:** Ohne Umwege Stack verstehen, starten, prüfen und eskalieren. Details bleiben in den verlinkten Dokumenten.

**Kanoneinstieg (dieses Dokument):** Hier findest du Start/Stop, Health, Logs, Keys und wohin du bei Problemen springst. Produktions-Architektur (Proxy, TLS): danach [`docs/OPERATOR_HANDBOOK.md`](OPERATOR_HANDBOOK.md).

## 0. Frischer Clone — minimal bis „läuft“ (Windows / WSL)

1. **Repo** geklont; **Docker Desktop** an (unter WSL2: Docker-Integration).
2. **ENV:** `Copy-Item .env.local.example .env.local` — Pflichtwerte (siehe [`docs/LOCAL_START_MINIMUM.md`](LOCAL_START_MINIMUM.md)); prüfen:  
   `python tools/validate_env_profile.py --env-file .env.local --profile local`
3. **Abhängigkeiten:** `pnpm install` (Repo-Root).
4. **Dashboard → Gateway (Server-JWT):**  
   `python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file`  
   Danach Stack neu hochfahren oder Dashboard-Container neu starten, damit Next die Variable sieht.
5. **Stack starten:** `pnpm dev:up` (intern: `scripts/dev_up.ps1`).  
   Optional End-to-End-Check: `pwsh scripts/dev_up.ps1 -Smoke`.  
   **Alternative:** `pnpm bootstrap:local` (= `bootstrap_stack.ps1 local`, staged + Migrationen).
6. **Prüfen:** `GET /v1/system/health` mit Bearer-JWT (Beispiel in LOCAL_START_MINIMUM §5); Browser **Console → Health** ohne 503 durch fehlendes `DASHBOARD_GATEWAY_AUTHORIZATION`; `http://127.0.0.1:8000/ready`; **Smoke:** `pnpm smoke`.

**WSL/Linux:** `bash scripts/start_local.sh` (`.env.local` wie oben).

## 1. Start & Stop (lokal / Compose)

| Aktion                        | Befehl                                                  |
| ----------------------------- | ------------------------------------------------------- |
| Voraussetzungen & Minimal-ENV | [`docs/LOCAL_START_MINIMUM.md`](LOCAL_START_MINIMUM.md) |
| Windows: Stack hoch           | `pnpm dev:up` oder `pwsh scripts/dev_up.ps1`            |
| Staged Bootstrap (local)      | `pnpm bootstrap:local`                                  |
| Optional: Smoke nach Start    | `pwsh scripts/dev_up.ps1 -Smoke` (ruft `rc_health` auf) |
| Status                        | `pwsh scripts/dev_status.ps1`                           |
| Logs                          | `pwsh scripts/dev_logs.ps1`                             |
| Stop                          | `pwsh scripts/dev_down.ps1`                             |

Produktion / Single-Host: [`docs/Deploy.md`](Deploy.md), [`docs/operator_urls_and_secrets.md`](operator_urls_and_secrets.md).

## 2. Gesundheit & Release-Gate

**Pflicht nach Deploy / dev:up:** Ein Befehl muss grün sein oder mit **Exit ≠ 0** und klarer Diagnose enden:

| Prüfung                                                     | Befehl / Pfad                                                                                                                                                                                                                          |
| ----------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Smoke (kanonisch, Edge + /v1/system/health + Lesepfade)** | **`pnpm smoke`** oder `pnpm rc:health` (Windows: `scripts/rc_health.ps1` → `scripts/rc_health_runner.py` + `rc_health_edge.py`). Linux/macOS/CI: **`bash scripts/rc_health.sh`** bzw. `python3 scripts/rc_health_runner.py .env.local` |
| Shell-Health (Container / curl)                             | `bash scripts/healthcheck.sh` — oft zuerst grün, bevor `smoke` sinnvoll ist                                                                                                                                                            |
| Ein-Klick inkl. Smoke                                       | `pwsh scripts/dev_up.ps1 -Smoke` (nach Compose-Health: `rc_health`)                                                                                                                                                                    |
| Gateway-Readiness                                           | `GET /v1/deploy/edge-readiness`                                                                                                                                                                                                        |

Bei Fehlern zeigt `rc_health_edge` am Ende einen Block **„SMOKE / rc_health — DIAGNOSE“** (URLs, JWT-Hinweis, Logs).

## 3. Welcher Key wofür?

Zentrale Tabelle: [`docs/SECRETS_MATRIX.md`](SECRETS_MATRIX.md).  
Validierung vor Compose: `python tools/validate_env_profile.py --env-file .env.local --profile local`.

**Häufige Stolpersteine**

- Dashboard-Server → Gateway: `DASHBOARD_GATEWAY_AUTHORIZATION` muss zum Gateway-JWT-Setup passen ([`docs/Deploy.md`](Deploy.md)).
- Service-zu-Service: `INTERNAL_API_KEY` und Header `X-Internal-Service-Key` ([`shared/python/src/shared_py/service_auth.py`](../shared/python/src/shared_py/service_auth.py)); in `PRODUCTION=true` ohne gesetzten Key antworten geschützte Pfade mit **503** (`INTERNAL_AUTH_MISCONFIGURED`).

## 4. Logs, Metriken, Alerts

- Observability-Überblick: [`docs/observability.md`](observability.md)
- Runbooks zu Prometheus-Alerts: [`docs/monitoring_runbook.md`](monitoring_runbook.md)
- Anbieter-Fehlerbilder (Bitget/LLM, ohne Secrets in Logs): [`docs/PROVIDER_ERROR_SURFACES.md`](PROVIDER_ERROR_SURFACES.md)

## 5. Eskalation & tiefere Doku

**On-Call / Verantwortliche** sind organisationsspezifisch: Rollen und externe Abhängigkeiten stehen in [`docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md`](EXTERNAL_GO_LIVE_DEPENDENCIES.md) (Abschnitt Eskalation/On-Call, falls befüllt). Technische nächste Schritte bei Ausfall: [`docs/recovery_runbook.md`](recovery_runbook.md) → [`docs/emergency_runbook.md`](emergency_runbook.md).

| Thema                                  | Dokument                                                                                               |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Betreiberhandbuch (Proxy, TLS, Backup) | [`docs/OPERATOR_HANDBOOK.md`](OPERATOR_HANDBOOK.md)                                                    |
| Launch-Paket / Index                   | [`docs/LAUNCH_PACKAGE.md`](LAUNCH_PACKAGE.md)                                                          |
| Recovery / Notfall                     | [`docs/recovery_runbook.md`](recovery_runbook.md), [`docs/emergency_runbook.md`](emergency_runbook.md) |
| Sicherheit (Light)                     | [`docs/SECURITY_THREAT_MODEL_LIGHT.md`](SECURITY_THREAT_MODEL_LIGHT.md)                                |
| Supply-Chain / CI-Audits               | [`docs/CI_AUDIT_POLICY.md`](CI_AUDIT_POLICY.md)                                                        |

## 6. CI-Qualität (für Releases)

- Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) — u. a. Coverage-Gates, Compose-Healthcheck, `pnpm audit` (high+).
