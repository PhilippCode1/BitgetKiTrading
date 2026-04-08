# Ausfuehrungslagen: local, paper, exchange_sandbox, shadow, live

Ziel: **keine gefaehrlichen Mischzustaende** zwischen Simulation, Bitget-Demo (PAPI), Shadow und Echtgeld-Live.

## Begriffe

| Begriff              | Quelle im Code                                       | Bedeutung                                                                             |
| -------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------- |
| **deployment**       | `execution_tier.deployment`                          | `local`, `development`, `non_production`, `production` (aus `APP_ENV` / `PRODUCTION`) |
| **trading_plane**    | `execution_tier.trading_plane`                       | `paper`, `exchange_sandbox`, `shadow`, `live`                                         |
| **exchange_sandbox** | `BITGET_DEMO_ENABLED=true`                           | Bitget Paper-Trading / Demo-REST+WS; **nie** zusammen mit `EXECUTION_MODE=live`       |
| **paper**            | `EXECUTION_MODE=paper` ohne Demo-Flag                | Primaer paper-broker Simulation; kein Bitget-Datenpfad zwingend                       |
| **shadow**           | `EXECUTION_MODE=shadow` + `SHADOW_TRADE_ENABLE=true` | Echte Markt-/Account-Sicht, **keine** Live-Exchange-Orders                            |
| **live**             | `EXECUTION_MODE=live` + Broker + `LIVE_TRADE_ENABLE` | Echtgeld-Pfad; weitere Gates siehe unten                                              |

Die Payload liegt unter `GET /v1/system/health` → `execution.execution_runtime.execution_tier` und im Snapshot-Feld `execution_tier` innerhalb von `execution_runtime` (Schema `execution_runtime.schema_version` ≥ 2).

## Harte Regeln (Fail-Fast)

1. **`EXECUTION_MODE=live` + `BITGET_DEMO_ENABLED=true`** — **verboten** (`BaseServiceSettings._prod_safety`), in **allen** Umgebungen.
2. **`BITGET_DEMO_ENABLED=true`** — verlangt gesetzte **`BITGET_DEMO_API_*`** Credentials (`BitgetSettings._validate_demo_mode`). Ohne Demo-Keys kein Exchange-Sandbox-Betrieb.
3. **Production + `BITGET_DEMO_ENABLED=true`** — weiterhin unzulaessig (bestehende Prod-Policy).
4. **Gateway `EXECUTION_LIVE_STRICT_PREREQUISITES=true`** bei **Production** und aktivem Live-Handel (`EXECUTION_MODE=live`, `LIVE_TRADE_ENABLE=true`, `LIVE_BROKER_ENABLED=true`) verlangt:
   - `COMMERCIAL_ENABLED=true`
   - `COMMERCIAL_TELEGRAM_REQUIRED_FOR_CONSOLE=true`
   - `TELEGRAM_BOT_USERNAME` (nicht leer)
   - `COMMERCIAL_METER_SECRET` mit Mindestlaenge (Billing/Metering D2D)
   - `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true` (auditierte Operator-Freigabe fuer Live-Opens; wirkt im Live-Broker)

`LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN` ist in **`BaseServiceSettings`** definiert (ein ENV fuer Gateway und Live-Broker).

## Standard und empfohlene Stufen

- **Standard / sicher:** `EXECUTION_MODE=paper` (Projekt-Default), `LIVE_TRADE_ENABLE=false`, `SHADOW_TRADE_ENABLE=false`.
- **Exchange-Sandbox:** `BITGET_DEMO_ENABLED=true` + vollstaendige Demo-API-Keys; **nicht** `EXECUTION_MODE=live`.
- **Shadow / Staging:** `EXECUTION_MODE=shadow`, `SHADOW_TRADE_ENABLE=true`, `LIVE_TRADE_ENABLE=false`, typisch `LIVE_BROKER_ENABLED=true` fuer private Daten.
- **Live:** `EXECUTION_MODE=live`, `LIVE_BROKER_ENABLED=true`, `LIVE_TRADE_ENABLE=true`, `BITGET_DEMO_ENABLED=false`, Production optional mit `EXECUTION_LIVE_STRICT_PREREQUISITES=true`.

## UI

- Operator-Console: Band **`ConsoleExecutionModeRibbon`** (Server-Render aus System-Health).
- Health-Seite: Zusaetzliche Zeilen in **Execution Controls** (`HealthGrid`).

Moduswechsel erfolgt **nur** per Deploy/ENV (kein stiller Laufzeitwechsel).

## Verwandte Dokumente

- `docs/execution_modes.md` — Modusmatrix und Operator-ENV-Beispiele
- `docs/live_broker.md` — Live-Broker-Gates und Operator-Release
- `docs/Deploy.md` — Rollout
