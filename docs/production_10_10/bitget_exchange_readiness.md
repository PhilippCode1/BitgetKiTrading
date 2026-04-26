# Bitget Exchange Readiness

## 1) Zielbild

Bitget Readiness beweist vor jedem Live-Go, dass Public API, private
Read-only-API, API-Versionen, Instrument Discovery, ProductType/MarginCoin,
Permissions, Server-Time und Rate-Limits verstanden sind. Ohne positive
Readiness bleibt Live-Write blockiert.

## 2) Read-only vs Write

`scripts/bitget_readiness_check.py` nutzt fail-closed Runtime-Modi:
`public`, `readonly`, `demo-readonly`, `demo-trade-smoke` (nur mit
`--i-understand-demo-order-smoke`) und `live-readonly`.
Live-Write bleibt standardmaessig `false`; automatisches Live-Trading ist verboten.

## 3) Demo vs Live

Demo- und Live-Credentials muessen isoliert sein. Eine Demo-/Live-Key-Mischung
ist `FAIL`. `demo-safe` ist nur mit klar aktivem Demo-Kontext erlaubt und bleibt
trotzdem read-only.

## 4) API-Versionen

Dokumentierte Zielpfade sind Bitget V2:

- `/api/v2/public/time`
- `/api/v2/spot/public/symbols`
- `/api/v2/mix/market/contracts`
- `/api/v2/spot/account/assets`
- `/api/v2/mix/account/accounts`

V1-Nutzung ist Risiko. Eine unklare API-Version blockiert Live, bis die Pfade
und Antwortvertraege verifiziert sind. V3/aktuelle Bitget-Pfade muessen vor
Migration separat dokumentiert und getestet werden.

## 5) Permissions

Permissions werden bewertet, soweit Bitget sie ueber private Read-only-Pfade
oder externe Key-Evidence sichtbar macht. Unklare Permission blockiert Live.
Trading-Permission wird nur passend zum geplanten Marktmodus bewertet und ist
keine automatische Live-Freigabe.

## 6) Withdrawal-Verbot

Withdrawal-Permission ist ein P0-Blocker. Ein Key mit Withdrawal-Rechten darf
nicht fuer diese private Trading-App verwendet werden.

## 6.1) Externe Key-Permission-Evidence

Echte Key-Permissions, IP-Allowlist und Account-Schutz duerfen nicht durch Repo-
Fixtures als `verified` gelten. Die technische Pruefstruktur liegt in
`tools/check_bitget_key_permission_evidence.py`; das Template liegt in
`docs/production_10_10/bitget_key_permission_evidence.template.json`.

Bis ein extern erzeugtes, secret-freies Evidence-JSON die folgenden Punkte
belegt, bleibt Live `NO_GO`:

- `withdrawal_permission=false`
- `read_permission=true`
- `trade_permission=true`
- `ip_allowlist_enabled=true`
- `account_protection_enabled=true`
- `api_version=v2`
- klarer `instrument_scope`
- externer `evidence_reference`
- Owner-Signoff separat vorhanden

Der Validator blockiert unredigierte Secret-Felder wie `api_key`, `api_secret`,
`passphrase`, `token` oder `password`. Solche Werte muessen immer
`[REDACTED]` oder `not_stored_in_repo` sein.

## 7) Server-Time

Server-Time-Skew wird gegen ein hartes Budget geprueft. Unbekannte oder zu
grosse Abweichung ist ein Live-Blocker, weil Signaturen und Exchange-Truth
sonst unzuverlaessig sind.

## 8) Rate-Limits

HTTP 429 wird als Rate-Limit klassifiziert. Rate-Limits sind kein Grund fuer
blindes Retry-Spamming und duerfen Live nicht entsperren.

## 9) Instrument Discovery

Die Instrumentenliste muss fuer Spot/Futures/Margin abrufbar oder als fehlende
Evidence markiert sein. ProductType und MarginCoin muessen zum Marktmodus
passen, z. B. `USDT-FUTURES` mit `USDT`.

## 10) Live-Gates

Bitget Readiness ist nur ein Gate. Live braucht weiterhin ENV-Gates,
Owner-/Operator-Freigabe durch Philipp, Shadow-Match, Exchange-Health,
Asset-Live-Eligibility, Risk-Governor, Kill-Switch, Safety-Latch, Reconcile und
Audit-Trail.

## 11) No-Go-Regeln

- Kein Readiness-Skript mit Submit/Cancel/Replace.
- Keine echten Secrets in Repo, Report, Browser oder Logs.
- Kein Live bei Withdrawal-Permission.
- Kein Live bei unklarer Permission.
- Kein Live bei unklarer Exchange-Truth.
- Kein Live bei unklarer API-Version.
- Kein Live bei fehlender Instrument Discovery.
- Kein Live bei Server-Time-Skew ausserhalb Budget.

## 12) Tests

```bash
python scripts/bitget_readiness_check.py --env-file .env.production.example --mode public --output-md reports/bitget_runtime_readiness.md --output-json reports/bitget_runtime_readiness.json
python scripts/bitget_readiness_check.py --env-file .env.shadow.example --mode demo-readonly --output-md reports/bitget_runtime_readiness.md --output-json reports/bitget_runtime_readiness.json
python tools/check_bitget_key_permission_evidence.py --evidence-json docs/production_10_10/bitget_key_permission_evidence.template.json --strict --output-md reports/bitget_key_permission_evidence.md --output-json reports/bitget_key_permission_evidence.json
python tools/check_bitget_exchange_readiness.py --strict
pytest tests/scripts/test_bitget_readiness_check.py -q
pytest tests/security/test_bitget_exchange_readiness_contracts.py -q
pytest tests/tools/test_check_bitget_exchange_readiness.py -q
```

Echte Bitget-Readiness bleibt externe Runtime-Evidence und darf keine Secrets
enthalten:

```bash
python scripts/bitget_readiness_check.py --env-file .env.production --mode live-readonly --output-md reports/bitget_runtime_readiness.md --output-json reports/bitget_runtime_readiness.json
```
