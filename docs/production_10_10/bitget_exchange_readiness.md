# Bitget Exchange Readiness

## 1) Zielbild

Bitget Readiness beweist vor jedem Live-Go, dass Public API, private
Read-only-API, API-Versionen, Instrument Discovery, ProductType/MarginCoin,
Permissions, Server-Time und Rate-Limits verstanden sind. Ohne positive
Readiness bleibt Live-Write blockiert.

## 2) Read-only vs Write

`scripts/bitget_readiness_check.py` nutzt nur sichere Read-only-Pruefungen.
Das Skript darf keine Order senden, ersetzen, canceln oder submitten. Der
Standard ist `dry-run`; `readonly` und `demo-safe` duerfen nur GET-/Read-Pfade
nutzen. `Live-Write erlaubt?` ist standardmaessig `false`.

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
python scripts/bitget_readiness_check.py --env-file .env.production.example --mode dry-run
python tools/check_bitget_exchange_readiness.py --strict
pytest tests/scripts/test_bitget_readiness_check.py -q
pytest tests/security/test_bitget_exchange_readiness_contracts.py -q
pytest tests/tools/test_check_bitget_exchange_readiness.py -q
```

Echte Bitget-Readiness bleibt externe Runtime-Evidence und darf keine Secrets
enthalten:

```bash
python scripts/bitget_readiness_check.py --env-file .env.production --mode readonly --output-md reports/bitget_readiness.md
```
