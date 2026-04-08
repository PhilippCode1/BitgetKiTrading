# Produktions-Runbook (Ops)

Kurzreferenz fuer Betrieb nach Deploy. **Freigabeleiter, Cutover, Notfall, externe Blocker:** **`docs/LAUNCH_DOSSIER.md`**. Checkliste (Checkboxen): **`docs/LaunchChecklist.md`**. Shadow-/Ramp-Plan: **`docs/shadow_burn_in_ramp.md`**. Detaillierte Monitoring-Schritte: **`docs/monitoring_runbook.md`**, Metriken/Alerts: **`docs/observability.md`**, Deploy: **`docs/Deploy.md`**.

## Modi paper / shadow / live

| Modus      | Ziel                                  | Vor Bedarf pruefen                                                                     |
| ---------- | ------------------------------------- | -------------------------------------------------------------------------------------- |
| **paper**  | Entwicklung, keine Live-Orders        | `EXECUTION_MODE=paper`, `LIVE_TRADE_ENABLE=false`                                      |
| **shadow** | Produktionsnaehe ohne Exchange-Submit | `EXECUTION_MODE=shadow`, `SHADOW_TRADE_ENABLE=true`, `LIVE_TRADE_ENABLE=false`         |
| **live**   | Echte Orders                          | `EXECUTION_MODE=live`, `LIVE_TRADE_ENABLE=true`, Live-Broker enabled, Risk/Gates gruen |

Wechsel **immer** nur nach `docs/LaunchChecklist.md` und mit dokumentierter Freigabe (Change-Ticket / internes Protokoll — operativ bei euch pflegen).

## Erst-Burn-in Hebel

- Empfohlene konservative Erstkonfiguration: **`RISK_ALLOWED_LEVERAGE_MAX=7`** (zusammen mit `RISK_ALLOWED_LEVERAGE_MIN=7`, `RISK_REQUIRE_7X_APPROVAL=true`). Erhoehung bis **75** nur nach Evidenz und expliziter Freigabe.
- Zusaetzlich fuer den Live-Ramp: **`RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7`** und `STRATEGY_EXEC_MODE=manual`, bis die Startkohorte stabil ist.

## Echtgeld-Ramp statt Vollfreigabe

- Erste Echtgeldstufe = **operator-gated mirror**, nicht Vollautonomie.
- Pflichtgates: `LIVE_REQUIRE_EXECUTION_BINDING=true`, `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true`, `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true`.
- Startkohorte und No-Go-Bedingungen sind in `docs/shadow_burn_in_ramp.md` verbindlich beschrieben.

## Taegliche Checks

1. `bash scripts/healthcheck.sh` (mit gesetzten `*_URL` aus dem Profil).
2. Gateway: `GET /v1/system/health` — Freshness, Execution-Flags, Live-Broker-Ops.
3. Offene Alerts: `GET /v1/monitor/alerts/open` (Gateway, authentifiziert) oder DB `ops.alerts`.
4. Grafana-Dashboard **Bitget BTC AI — Trading & Ops** (wenn Observability-Profil aktiv).

## Eskalation nach Schweregrad

1. **Kill-Switch aktiv** (`live.kill_switch_events`, Alert `KillSwitchActive`) — sofort Trading-Stopp pruefen, Ursache in Audit/Logs; kein Resume ohne Freigabe.
2. **Reconcile fail / hohes Drift** — Exchange-Connectivity, Private-WS, Schema-Mismatches; siehe Live-Broker-Logs und `docs/live_broker.md`.
3. **Datenstaleness** — Pipeline von `market-stream` bis `signal-engine`; Redis-Stream-Lag.
4. **Online-Drift hard_block** — Learning/Registry; ggf. Champion-Rollback laut `docs/model_registry_v2.md`.
5. **Ramp-Fallback** — bei Route-Instabilitaet, hoher Stop-Fragilitaet, Shadow-Live-Divergenz oder Telegram-/Auth-Anomalien sofort zurueck auf `EXECUTION_MODE=shadow`, `LIVE_TRADE_ENABLE=false`.

## Rollback (Anwendung)

1. Vorheriges Image-Tag / Compose-Revision festhalten.
2. `docker compose up -d` mit bekannter guter Revision oder Image-Digest.
3. DB: nur kompatible Migrationen rueckgaengig machen; sonst Restore aus Backup.

## Secrets und Zugang

- Keine Secrets im Git; Rotation bei Leck.
- Gateway sensible Routen: JWT / interner Key / Legacy nur non-Prod — **`docs/api_gateway_security.md`**.
- Dashboard Admin im Produktionsproxy: `DASHBOARD_GATEWAY_AUTHORIZATION` serverseitig — **`docs/dashboard_operator.md`**.

## Ansprechpartner / Eskalationskette

Operativ im Unternehmen hinterlegen (On-Call, Trading-Owner, Infra); nicht im Repo committen.
