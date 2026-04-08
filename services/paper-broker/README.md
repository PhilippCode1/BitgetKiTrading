# paper-broker

Paper-Trading-Simulation fuer **Bitget-Marktfamilien** (Spot/Margin/Futures), sobald der
`BitgetInstrumentCatalog` und Signal-Metadaten (`market_family`, `product_type`, …) passen:
Margin (isolated/crossed), Hebel,
Market-Fills mit **Fees** (Bitget-Formel), **Funding**-Buchungen, **Slippage** (Orderbuch /
SIM-Fallback), **Liquidation (Approx)**.

## Voraussetzungen

- Postgres mit Migrationen `110_paper_broker_core.sql`, `120_*`, `130_*`, `560_paper_broker_multi_asset_audit.sql` (`python infra/migrate.py`)
- Redis (Events)
- `shared/python/src` auf `PYTHONPATH` (oder Docker-Image)

## Konfiguration

Siehe `.env.example` (Abschnitt Paper Broker) und `docs/paper_broker.md`.

Globale Execution-Wahrheit:

- `EXECUTION_MODE=paper|shadow|live` waehlt den aktiven Trading-Pfad des Stacks.
- `STRATEGY_EXEC_MODE=manual|auto` steuert nur den lokalen Strategy-/Automation-Release.
- Der `paper-broker` fuehrt Signal-getriebene Auto-Opens nur bei `EXECUTION_MODE=paper` aus.
- In `shadow` oder `live` bleiben Risk-, Signal- und Strategy-Contracts identisch, aber der Paper-Pfad loest keine neuen Trades mehr aus.
- Mit `STRATEGY_REQUIRE_TELEGRAM=true` startet die Auto-Strategie keine neuen Trades, solange fuer `BILLING_PREPAID_TENANT_ID` kein Eintrag in `app.customer_telegram_binding` existiert (Kunden-Onboarding).

Leverage-Allocator (Prompt 21):

- Signal-getriebene Auto-Opens uebernehmen zuerst den signal-seitigen
  `recommended_leverage` / `allowed_leverage`.
- Vor dem eigentlichen Open wird daraus ein finaler Integer-Hebel 7..75
  berechnet. Die finalen Caps sind `exchange_cap`, `model_cap`,
  `liquidation_buffer_cap`, `stop_distance_cap`, `margin_usage_cap` und
  `drawdown_cap`.
- Faellt der finale `allowed_leverage` unter 7, blockt der `paper-broker` den
  Trade deterministisch und schreibt den Blockgrund als Strategy-Event.
- Der finale Allocator-Trace wird in `paper.positions.meta.leverage_allocator`
  sowie im `trade_opened`-Trace gespeichert und ist damit fuer Replay,
  Dashboard und Operator-Audit sichtbar.

Gemeinsame Risk-Engine (Prompt 22):

- Vor Auto-Open und nochmals direkt vor `open_position()` verwendet der
  `paper-broker` jetzt denselben Shared-Risk-Core wie der `live-broker`.
- Die gemeinsamen Hard-Gates laufen ueber `RISK_MIN_*`,
  `RISK_MAX_POSITION_RISK_PCT`, `RISK_MAX_ACCOUNT_MARGIN_USAGE`,
  `RISK_MAX_ACCOUNT_DRAWDOWN_PCT`, `RISK_MAX_DAILY_DRAWDOWN_PCT`,
  `RISK_MAX_WEEKLY_DRAWDOWN_PCT`, `RISK_MAX_DAILY_LOSS_USDT`,
  `RISK_MAX_POSITION_NOTIONAL_USDT` und `RISK_MAX_CONCURRENT_POSITIONS`.
- Drawdown, Margin-Usage und Total-Equity werden fuer Paper nicht mehr nur aus
  `paper.accounts.equity`, sondern aus freier Equity plus offener Margin
  abgeleitet.
- Equity-Aenderungen aus Open, Reduce/Close, Liquidation und Funding werden als
  `paper.position_events` mitgeschrieben, damit Tages- und Wochen-Drawdown
  deterministisch aus dem vorhandenen Audit-Pfad berechnet werden koennen.
- Der finale Shared-Risk-Entscheid wird in `paper.positions.meta.risk_engine`,
  im `trade_opened`-Trace und in `AUTO_BLOCKED`-Strategy-Events abgelegt.

Gemeinsame Exit-Engine (Prompt 23):

- Stop-Loss, Take-Profit, Partial-Exit, Break-Even und Runner/Trailing laufen
  jetzt ueber einen gemeinsamen Shared-Exit-Core statt ueber separate
  Paper-/Live-Sonderregeln.
- `paper-broker` persistiert die Shared-Exit-Semantik direkt in
  `stop_plan_json` / `tp_plan_json` (`policy_version`, `break_even`,
  `runner.trail_offset`, `execution_state`).
- Break-Even nach TP1 und Runner-Arming/Trail verwenden dieselbe fachliche
  Zustandsmaschine wie `live-broker`; die Audit-Spur bleibt in
  `paper.position_events` (`TP_HIT`, `PLAN_UPDATED`, `TRAILING_UPDATE`,
  `RUNNER_TRAIL_HIT`, `SL_HIT`) sichtbar.
- `plan_auto` und `plan_override` validieren Exit-Parameter jetzt explizit gegen
  Shared-Risk-/Leverage-Kontext, damit kein Stop-/TP-Override die harte
  Risiko- oder Leverage-Policy unterlaeuft.

## Start (lokal)

```bash
cd services/paper-broker
pip install -e .
set PYTHONPATH=..\..\shared\python\src
set DATABASE_URL=postgresql://...
set REDIS_URL=redis://...
set PAPER_SIM_MODE=true
python -m paper_broker.main
```

Port: `PAPER_BROKER_PORT` (Default **8085**).

## Docker Compose

```bash
docker compose up -d --build paper-broker
curl -s http://localhost:8085/health
```

## Tests

```bash
pytest -q tests/paper_broker
```

## Smoke

```bash
python tools/paper_broker_smoke_test.py
```
