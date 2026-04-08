# Ausfuehrungsmodi: Paper, Shadow, Live (systemweit)

Dieses Dokument ist die **Referenz** fuer Prompt 17. Die technische Quelle der Wahrheit fuer abgeleitete Flags ist
`config/execution_runtime.build_execution_runtime_snapshot` bzw. `BaseServiceSettings.execution_runtime_snapshot()`.

## Begriffe

| Begriff                 | Bedeutung                                                                                                                                                                                                                                |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **primary_mode**        | `EXECUTION_MODE`: `paper` \| `shadow` \| `live`                                                                                                                                                                                          |
| **strategy_release**    | `STRATEGY_EXEC_MODE`: `manual` (nur Kandidaten/Journal) \| `auto` (automatisierte Handelsaktionen dort erlaubt, wo die Fachlogik es zulaesst)                                                                                            |
| **Shadow**              | Echte Signale, Markt-/Account-Daten, Risk- und Reconcile-Kontext; **keine** Exchange-Order-Submits durch den Live-Broker                                                                                                                 |
| **Live (Vollfreigabe)** | Zusatz zu `EXECUTION_MODE=live`: `LIVE_TRADE_ENABLE=true`, `LIVE_BROKER_ENABLED=true`, und fuer **automatisierte** Exchange-Orders zusaetzlich `STRATEGY_EXEC_MODE=auto` plus alle Laufzeit-Gates (Truth, Drift, Health, Kill-Switch, …) |

Paper- und Live-Pfad im **Live-Broker** nutzen dieselbe Entscheidungskette (`LiveExecutionService._decide`): Risk-Signal, Exit-Preview, Online-Drift, Shadow-Match-Gate, Live-Gates. Unterschied: bei Paper verarbeitet der Live-Broker **keine** Signale (`paper_path_active`); Simulation laeuft ueber **paper-broker** mit gemeinsamen Risk-ENV aus `BaseServiceSettings`.

## Erforderliche ENV-Kombinationen

| Modus                   | EXECUTION_MODE | SHADOW_TRADE_ENABLE  | LIVE_TRADE_ENABLE | LIVE_BROKER_ENABLED         |
| ----------------------- | -------------- | -------------------- | ----------------- | --------------------------- |
| **paper**               | `paper`        | `false`              | `false`           | beliebig (oft `false`)      |
| **shadow**              | `shadow`       | **`true` (Pflicht)** | `false`           | `true` in Prod fuer WS/REST |
| **live (konfiguriert)** | `live`         | `false`              | `true`            | **`true` (Pflicht)**        |

Validatoren in `config/settings.py` lehnen widerspruechliche Kombinationen ab (z. B. `SHADOW_TRADE_ENABLE=true` ohne `EXECUTION_MODE=shadow`, `EXECUTION_MODE=shadow` ohne `SHADOW_TRADE_ENABLE=true`).

## Modusmatrix (erlaubt / unerlaubt)

Legende: **J** = Journal / Kandidat moeglich, **O** = Exchange-Order moeglich (nach Laufzeit-Gates), **—** = nicht anwendbar.

| Aktion                                       | paper | shadow                | live + LIVE_TRADE + Broker                 | live + STRATEGY manual |
| -------------------------------------------- | ----- | --------------------- | ------------------------------------------ | ---------------------- |
| Live-Broker: Signale konsumieren             | —     | J                     | J                                          | J                      |
| Live-Broker: Shadow-Entscheid journalisieren | —     | J                     | — (Pfad ist live)                          | —                      |
| Live-Broker: Live-Candidate ohne Order       | —     | —                     | J                                          | J                      |
| Live-Broker: Exchange Order Submit           | —     | **nein**              | nur wenn `STRATEGY_EXEC_MODE=auto` + Gates | **nein** (Firewall)    |
| Paper-Broker: simulierte Orders              | J     | — (Modus nicht paper) | —                                          | —                      |
| Private Exchange REST/WS (Datenplane)        | nein  | ja                    | ja                                         | ja                     |

## Guard-Rails

- **Live-Firewall bei manual:** `live_order_submission_enabled` aber `STRATEGY_EXEC_MODE=manual` → keine automatisierten Exchange-Orders; Kandidaten nur im Journal.
- **Truth-Gate (optional):** `LIVE_BROKER_BLOCK_LIVE_WITHOUT_EXCHANGE_TRUTH` blockt Live-Submit ohne frischen WS/REST-Catchup und gesunde Reconcile-Sicht.
- **Kill-Switch, Reconcile-Fail, Exchange-Health:** bleiben unabhaengig vom Modus wirksam.
- **Execution-Binding (Live-Broker, optional):** `LIVE_REQUIRE_EXECUTION_BINDING=true` verlangt fuer Opening-Orders ein `source_execution_decision_id`, das auf eine persistierte `live_candidate_recorded`-Decision zeigt (gleiches Symbol). Reduce-only, Emergency-Flatten (Safety-Bypass) und reine Cancels sind ausgenommen.
- **Operator-Release (optional):** `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true` verlangt zusaetzlich `POST /live-broker/executions/{id}/operator-release` (Internal Auth), bevor Opening-Orders akzeptiert werden.
- **Kein Demo-REST in Prod:** `BITGET_DEMO_ENABLED=true` zusammen mit `PRODUCTION=true` oder `APP_ENV=production` ist im `live-broker` ungueltig.

## Moduswechsel — Operator-Kommandos

Aenderungen sind **deploy-seitig** (ENV / Secret-Store / Orchestrierung). Kein Hot-Switch zur Laufzeit ohne Neustart der betroffenen Services.

### Zu **paper** (lokal / sicher)

```bash
# Beispiel: nur Illustration — Werte im eigenen Secret-Store pflegen
export EXECUTION_MODE=paper
export SHADOW_TRADE_ENABLE=false
export LIVE_TRADE_ENABLE=false
# optional
export LIVE_BROKER_ENABLED=false
```

### Zu **shadow** (Staging / Prod-nahe ohne echte Orders)

```bash
export EXECUTION_MODE=shadow
export SHADOW_TRADE_ENABLE=true
export LIVE_TRADE_ENABLE=false
export LIVE_BROKER_ENABLED=true
export STRATEGY_EXEC_MODE=manual   # empfohlen bis Go-Live-Review
export LIVE_REQUIRE_EXECUTION_BINDING=true
export LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true
export REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true
export RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7
```

### Zu **live** (nur nach Freigabeprotokoll)

```bash
export EXECUTION_MODE=live
export SHADOW_TRADE_ENABLE=false
export LIVE_BROKER_ENABLED=true
export LIVE_TRADE_ENABLE=true
# Startstufe: operator-gated mirror
export STRATEGY_EXEC_MODE=manual
export LIVE_REQUIRE_EXECUTION_BINDING=true
export LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true
export REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true
export RISK_GOVERNOR_LIVE_RAMP_MAX_LEVERAGE=7
# Erst nach dokumentierter Evidenz: automatische Exchange-Orders
# export STRATEGY_EXEC_MODE=auto
```

Anschliessend: betroffene Container/Prozesse neu starten (`docker compose up -d …`, Kubernetes `rollout restart`, siehe `docs/Deploy.md`).

## API-/Monitoring-Felder

- **Gateway** `GET /v1/system/health` → `execution.execution_runtime` (ab Schema v2 inkl. `execution_tier`, siehe `docs/execution_mode_tiers.md`)
- **live-broker** `/health`, `/ready` → `execution_runtime` bzw. in `checks`
- **paper-broker** `/health` → `execution_runtime`

Die Runtime-Sicht enthaelt jetzt zusaetzlich einen `configuration`-Block mit:

- Profil (`APP_ENV`, `PRODUCTION`, `API_AUTH_MODE`)
- Marktuniversum (`BITGET_UNIVERSE_*`)
- Feature-/Signal-Scope
- Live-Allowlisten
- Instrumentenkatalog-Policy (`INSTRUMENT_CATALOG_*`)

Weitere Betriebsdokumente: `docs/Deploy.md`, `docs/prod_runbook.md`, `docs/LaunchChecklist.md`, `docs/live_broker.md`, `docs/env_profiles.md`.
