# Demo-Trading-Evidence-Guide

Dieser Guide beschreibt den sicheren Demo-Geld-Betrieb. Demo-Geld ist der naechste Beweisschritt, aber keine Echtgeld-Freigabe.

## Ziel

Mit Bitget-Demo-Geld soll geprueft werden:

- Demo-ENV ist korrekt gesetzt.
- Demo-Keys sind vorhanden, aber nie im Repo sichtbar.
- `LIVE_TRADE_ENABLE=false` bleibt hart gesetzt.
- `BITGET_DEMO_ENABLED=true` ist aktiv.
- REST-Demo nutzt den Header `paptrading: 1`.
- Private Demo-Read-only kann geprueft werden.
- Demo-Order-Dry-run kann ein Payload pruefen, ohne Order zu senden.
- Ein echter Demo-Order-Smoke ist nur mit bewusstem Sicherheitsflag moeglich.

## Wichtige Grenze

Demo-Erfolg bedeutet nicht automatisch `private_live_allowed`.

Demo kann `DEMO_READY` oder `DEMO_VERIFIED` liefern. Echtes Live bleibt trotzdem blockiert, bis separate Live-, Shadow-, Restore-, Alert-, Reconcile-, Safety- und Owner-Evidence vorhanden ist.

## Dateien

- Vorlage: `.env.demo.example`
- Lokale Datei: `.env.demo`
- Readiness-Report: `reports/bitget_demo_readiness.md` und `.json`
- Gesamt-Demo-Report: `reports/demo_trading_evidence.md` und `.json`

`.env.demo` darf niemals committed werden.

## Schritt 1: Vorlage kopieren

```bash
cp .env.demo.example .env.demo
```

Wenn `.env.demo` bereits existiert, nicht ueberschreiben. Vergleiche die Vorlage und ergaenze fehlende Werte manuell.

## Schritt 2: Demo-Keys lokal eintragen

Trage in `.env.demo` ein:

```env
BITGET_DEMO_API_KEY=...
BITGET_DEMO_API_SECRET=...
BITGET_DEMO_API_PASSPHRASE=...
```

Nicht eintragen oder leer lassen:

```env
BITGET_API_KEY=
BITGET_API_SECRET=
BITGET_API_PASSPHRASE=
```

## Schritt 3: Readiness ohne Order testen

```bash
python scripts/bitget_demo_readiness.py \
  --env-file .env.demo \
  --mode readonly \
  --output-md reports/bitget_demo_readiness.md \
  --output-json reports/bitget_demo_readiness.json \
  --json
```

Erwartung: `PASS` oder `PASS_WITH_WARNINGS`. Bei `FAIL` zuerst Blocker beheben.

## Schritt 4: Private Demo-Read-only testen

```bash
python scripts/bitget_demo_readiness.py \
  --env-file .env.demo \
  --mode private-readonly \
  --output-md reports/bitget_demo_readiness.md \
  --output-json reports/bitget_demo_readiness.json \
  --json
```

Dieser Schritt nutzt private Demo-Endpunkte, aber sendet keine Order.

## Schritt 5: Demo-Order-Dry-run

```bash
python scripts/bitget_demo_readiness.py \
  --env-file .env.demo \
  --mode demo-order-dry-run \
  --output-md reports/bitget_demo_readiness.md \
  --output-json reports/bitget_demo_readiness.json \
  --json
```

Dieser Schritt prueft das Orderpayload, sendet aber keine Order.

## Schritt 6: Gesamt-Demo-Evidence-Report

```bash
python scripts/demo_trading_evidence_report.py \
  --env-file .env.demo \
  --private-readonly \
  --order-dry-run \
  --output-md reports/demo_trading_evidence.md \
  --output-json reports/demo_trading_evidence.json \
  --json
```

Erwartung: `DEMO_READY`, wenn Readiness und private Demo-Read-only funktionieren.

## Schritt 7: Echter Demo-Order-Smoke

Nur ausfuehren, wenn bewusst Demo-Geld genutzt werden soll.

Vorher in `.env.demo` setzen:

```env
DEMO_ORDER_SUBMIT_ENABLE=true
```

Dann:

```bash
python scripts/demo_trading_evidence_report.py \
  --env-file .env.demo \
  --private-readonly \
  --order-dry-run \
  --demo-order-smoke \
  --i-understand-this-uses-demo-money \
  --output-md reports/demo_trading_evidence.md \
  --output-json reports/demo_trading_evidence.json \
  --json
```

Erwartung: `DEMO_VERIFIED`, wenn private Demo-Read-only und die bewusste Demo-Order erfolgreich waren.

## Schritt 8: Stack starten

```bash
docker compose --env-file .env.demo up --build
```

In einem zweiten Terminal:

```bash
python scripts/demo_stack_healthcheck.py \
  --env-file .env.demo \
  --dashboard-url http://localhost:3000 \
  --base-url http://localhost:8000 \
  --output-md reports/demo_stack_healthcheck.md \
  --json
```

## Schritt 9: Stress-Smoke ohne Demo-Order

```bash
python scripts/demo_stress_smoke.py \
  --base-url http://localhost:8000 \
  --dashboard-url http://localhost:3000 \
  --duration-sec 60 \
  --output-md reports/demo_stress_smoke.md \
  --json
```

## Schritt 10: Stress-Smoke mit bewusstem Demo-Submit

Nur wenn die API-Route spaeter Demo-Submit sicher freigibt:

```bash
python scripts/demo_stress_smoke.py \
  --base-url http://localhost:8000 \
  --dashboard-url http://localhost:3000 \
  --duration-sec 60 \
  --include-demo-order-preview \
  --include-demo-order-submit \
  --i-understand-this-uses-demo-money \
  --output-md reports/demo_stress_smoke.md \
  --json
```

## Reports fuer Philipp / Review

Zur Bewertung niemals Secrets posten. Nur diese redacted Reports teilen:

- `reports/bitget_demo_readiness.md`
- `reports/demo_trading_evidence.md`
- `reports/demo_stack_healthcheck.md`
- `reports/demo_stress_smoke.md`

## Harte Regeln

- Kein `LIVE_TRADE_ENABLE=true` im Demo-Profil.
- Keine Live-Keys im Demo-Profil.
- Kein Owner-Signoff durch Demo.
- Kein `private_live_allowed` durch Demo.
- Demo ist ein wichtiger Beweis, aber nicht die Echtgeld-Freigabe.
