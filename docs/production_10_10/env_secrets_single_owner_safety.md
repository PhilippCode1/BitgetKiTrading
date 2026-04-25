# ENV, Secrets und Single-Owner-Safety

## 1) Zielbild

`bitget-btc-ai` wird privat von Philipp Crljic betrieben. ENV-Profile muessen
Live-Trading fail-closed halten, Secrets schuetzen und keine Billing-/Customer-
oder SaaS-Verkaufsplattform erzwingen.

## 2) Profile

- `local`: Entwicklung/Paper, Fake-Provider und Demo duerfen genutzt werden.
- `shadow`: echte Daten und Shadow-Simulation, keine echten Order-Submits.
- `production`: Production-Umgebung; Live nur mit vollstaendiger Gate-Kette.

## 3) Single-Owner-Scope

Philipp ist alleiniger Admin, Owner und Operator. Es gibt keine Kunden,
Mandanten, Abos, Preise, Payment-Flows oder Sales-Ziele als Produktpflicht.

## 4) Keine Billing-/Customer-Secrets

Billing-/Payment-/Customer-Variablen sind fuer diese private Version nicht
pflichtig. Falls alte Payment-Mocks in Production aktiv sind, werden sie als
Risiko markiert, aber nicht als Pflichtpfad ausgebaut.

## 5) Bitget-Secrets

Bitget Live- und Demo-Credentials duerfen nicht gemischt werden. Live-Credentials
kommen aus dem Secret Store und duerfen nie als `NEXT_PUBLIC_*` erscheinen.

## 6) OpenAI/LLM-Secrets

`LLM_USE_FAKE_PROVIDER=true` ist nur local/test erlaubt. Shadow/Production
muessen echte Providerpfade verwenden oder fail-closed blockieren.

## 7) Telegram/Alert-Secrets

Alert-/Telegram-Secrets bleiben serverseitig. Browser-ENV darf keine Tokens
enthalten.

## 8) DB/Redis-Secrets

DB-/Redis-URLs und Passwoerter sind Runtime-Secrets. Templates duerfen
Platzhalter enthalten; Runtime-Checks duerfen Platzhalter nicht akzeptieren.

## 9) Browser-ENV-Regeln

`NEXT_PUBLIC_*` darf keine Namen oder Werte fuer Secrets enthalten:
OpenAI, Bitget, JWT, Token, Password, Passphrase, API-Key, Stripe, Telegram und
interne Gateway-Keys sind verboten.

## 10) Live-Gates

`LIVE_TRADE_ENABLE=true` ist nur erlaubt mit:

- `EXECUTION_MODE=live`
- `LIVE_BROKER_ENABLED=true`
- Owner-/Operator-Freigabe durch Philipp
- Shadow-Match, falls Live-Mirror
- Exchange-Health
- Asset-Live-Eligibility
- Risk-Governor
- Kill-Switch/Safety-Latch-Unterstuetzung

## 11) Secret-Rotation

Rotation bleibt externer Betriebsnachweis: Secret Store, Rotation-Drill,
Widerruf alter Tokens und Nachweis, dass Browser/Logs keine Secrets enthalten.

## 12) No-Go-Regeln

- Kein Production-DEBUG.
- Kein Fake-Provider in Shadow/Production.
- Kein Bitget-Demo in Production.
- Kein Live ohne Gates.
- Keine Demo-/Live-Key-Mischung.
- Keine echten Secrets im Repo, Browser oder Logs.
- Keine Billing-/Customer-Pflicht fuer private Owner-Version.

## 13) Tests

```bash
python tools/check_env_single_owner_safety.py --env-file .env.production.example --profile production --template
python tools/check_env_single_owner_safety.py --env-file .env.shadow.example --profile shadow --template
python tools/check_env_single_owner_safety.py --env-file .env.local.example --profile local --template
pytest tests/tools/test_check_env_single_owner_safety.py -q
pytest tests/security/test_env_single_owner_safety.py -q
```
