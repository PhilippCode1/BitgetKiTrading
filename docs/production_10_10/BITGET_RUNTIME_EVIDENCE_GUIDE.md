# BITGET Runtime Evidence Guide

## Ziel
Diese Anleitung beschreibt, wie Philipp runtime-nahe Bitget-Evidence erzeugt, ohne Secrets im Repo zu speichern und ohne automatische Live-Orders.

## 1) Benoetigte Keys
- **Demo Read-only:** `BITGET_DEMO_API_KEY`, `BITGET_DEMO_API_SECRET`, `BITGET_DEMO_API_PASSPHRASE`
- **Live Read-only:** `BITGET_API_KEY`, `BITGET_API_SECRET`, `BITGET_API_PASSPHRASE`
- Keine Keys in Markdown/JSON committen; nur redacted Felder verwenden.

## 2) Erlaubte Permissions
- `read_permission=true` ist Pflicht.
- `trade_permission` nur falls fachlich erforderlich und separat owner-reviewt.
- `withdrawal_permission=false` ist harte P0-Regel.

## 3) Warum Withdrawal verboten ist
- Withdrawal-Rechte erweitern den Schadenpfad ueber Trading hinaus.
- In diesem Projekt gilt: Trading-App darf keine Auszahlungsschluessel besitzen.

## 4) Demo-/Live-Trennung
- Demo und Live muessen getrennte Key-Saetze haben.
- Demo-Modi duerfen keine Live-Keys nutzen.
- Live-Modi duerfen keine Demo-Keys nutzen.
- Key-Mix fuehrt zu Fail-Closed.

## 5) Read-only pruefen
```bash
python scripts/bitget_readiness_check.py --env-file .env.production --mode public --output-md reports/bitget_runtime_readiness.md --output-json reports/bitget_runtime_readiness.json
python scripts/bitget_readiness_check.py --env-file .env.production --mode live-readonly --output-md reports/bitget_runtime_readiness.md --output-json reports/bitget_runtime_readiness.json
```

## 6) Demo pruefen
```bash
python scripts/bitget_readiness_check.py --env-file .env.shadow --mode demo-readonly --output-md reports/bitget_runtime_readiness.md --output-json reports/bitget_runtime_readiness.json
python scripts/bitget_readiness_check.py --env-file .env.shadow --mode demo-trade-smoke --i-understand-demo-order-smoke --output-md reports/bitget_runtime_readiness.md --output-json reports/bitget_runtime_readiness.json
```

## 7) Weitere Pflichtkommandos
```bash
python tools/check_bitget_key_permission_evidence.py --evidence-json docs/production_10_10/bitget_key_permission_evidence.template.json --output-md reports/bitget_key_permission_evidence.md --output-json reports/bitget_key_permission_evidence.json
python scripts/bitget_exchange_instrument_evidence_report.py --output-md reports/bitget_exchange_instrument_evidence.md --output-json reports/bitget_exchange_instrument_evidence.json
python scripts/refresh_bitget_asset_universe.py --input-json tests/fixtures/bitget_asset_universe_sample.json --output-json reports/bitget_asset_universe_sample.json --output-md reports/bitget_asset_universe_sample.md
```

## 8) Erwartete Reports
- `reports/bitget_runtime_readiness.md`
- `reports/bitget_runtime_readiness.json`
- `reports/bitget_key_permission_evidence.md`
- `reports/bitget_key_permission_evidence.json`
- `reports/bitget_exchange_instrument_evidence.md`
- `reports/bitget_exchange_instrument_evidence.json`

## 9) Was nicht committet werden darf
- `.env`, `.env.production`, `.env.shadow` mit echten Werten
- API-Keys, Secrets, Passphrases, Tokens
- Unredacted Account-IDs oder Key-IDs

## 10) Wann `bitget_exchange_readiness` auf `verified` darf
Nur wenn alle Punkte erfuellt sind:
- Runtime-Report mit echten read-only Daten vorhanden
- Instrument-Evidence mit realen Bitget-Metadaten vorhanden
- Key-Permission-Evidence inkl. IP-Allowlist und Account-Schutz vorhanden
- Owner-Review vorhanden
- `withdrawal_permission=false`
- Demo/Live Credential Isolation nachweisbar

## 11) Warum Live-Trading trotzdem nicht automatisch erlaubt ist
- `bitget_exchange_readiness` ist nur ein Gate in der Gesamt-Scorecard.
- Weitere harte Gates bleiben erforderlich: Risk, Reconcile, Safety-Latch, Kill-Switch, Owner-Go/No-Go, externe Evidence.
- `private_live_allowed` bleibt bis zur finalen Owner-Freigabe `NO_GO`.
