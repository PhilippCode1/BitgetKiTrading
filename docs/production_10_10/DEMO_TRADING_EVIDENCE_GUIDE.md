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

## Fehler 40774 loesen

Wenn Bitget bei Demo-Order `code=40774` meldet, passen Position-Mode im Konto und Order-Payload nicht zusammen.

Pruefe im Bitget-Demo-Futures-Fenster, ob das Konto im One-way- oder Hedge-Modus steht.

Wenn One-way:

```env
DEMO_POSITION_MODE=one_way
DEMO_TRADE_SIDE=
DEMO_POSITION_SIDE=
```

Wenn Hedge:

```env
DEMO_POSITION_MODE=hedge
DEMO_TRADE_SIDE=open
DEMO_POSITION_SIDE=long
```

`DEMO_POSITION_SIDE` kann je nach API-Pfad auch leer bleiben.

Danach immer zuerst `demo-order-dry-run` ausfuehren und erst dann den echten Demo-Order-Smoke.

## Demo-Position pruefen und schliessen

Nach erfolgreichem Demo-Smoke kann eine kleine Demo-Position offen bleiben. Das ist normal und muss sauber reconciled werden.

1) Zuerst readonly laufen lassen (liest nur, sendet keine Order):

```bash
python scripts/demo_reconcile_evidence_report.py \
  --env-file .env.demo \
  --mode readonly \
  --output-md reports/demo_reconcile_evidence.md \
  --output-json reports/demo_reconcile_evidence.json \
  --json
```

2) Danach close-dry-run laufen lassen (bereitet Close nur vor, sendet keine Order):

```bash
python scripts/demo_reconcile_evidence_report.py \
  --env-file .env.demo \
  --mode close-dry-run \
  --output-md reports/demo_reconcile_evidence.md \
  --output-json reports/demo_reconcile_evidence.json \
  --json
```

3) Erst dann close-smoke mit Sicherheitsflag nutzen:

```bash
python scripts/demo_reconcile_evidence_report.py \
  --env-file .env.demo \
  --mode close-smoke \
  --i-understand-this-closes-demo-position \
  --output-md reports/demo_reconcile_evidence.md \
  --output-json reports/demo_reconcile_evidence.json \
  --json
```

4) Danach readonly erneut starten und pruefen, ob Position/Orders wirklich weg sind.

Wichtig: Das schaltet kein echtes Live frei. `live_trading_allowed=false` und `private_live_allowed=false` bleiben bestehen.

## Fehler 22002 beim Schliessen

Wenn Bitget beim Schliessen `22002` meldet (`No position to close`), passt die Close-Seite oft nicht zur offenen Hedge-Position oder die Position ist schon zu.

Regel in Hedge Mode:

- Long schliessen: `side=buy`, `tradeSide=close`
- Short schliessen: `side=sell`, `tradeSide=close`

Wenn `side` falsch ist, meldet Bitget haeufig `No position to close`.

Nach einem Fix immer erst `close-dry-run` ausfuehren und erst danach `close-smoke`.

## Demo-Lifecycle verifiziert

Der Demo-Lifecycle ist geschafft, wenn alle Schritte in Reihenfolge nachweisbar sind:

- Demo-Order wurde geoeffnet (`DEMO_VERIFIED`)
- Position wurde im Reconcile erkannt
- Position wurde erfolgreich geschlossen (`CLOSE_VERIFIED`)
- Finaler Reconcile ist `CLEAN`

Das ist ein echter Fortschritt, weil der komplette Demo-Kreislauf inkl. kontrolliertem Exit bewiesen ist.

Trotzdem ist das keine Echtgeld-Freigabe:

- `private_live_allowed` bleibt `false`
- `full_autonomous_live` bleibt `false`
- `live_verified` bleibt `false`

Naechste Schritte Richtung Shadow/Staging:

- Demo-Lifecycle-Report archivieren
- Shadow-Burn-in mit stabilen Daten und Alerts weiterfuehren
- Staging-Reconcile-/Safety-Drills mit externer Evidence aufbauen

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

## CI-geschuetzte Demo-ENV-Hygiene

Demo-ENV/Compose-Hygiene ist zusaetzlich als CI-Gate abgesichert:

- Job: `demo-env-compose-safety` in `.github/workflows/ci.yml`
- Script: `scripts/ci_demo_env_compose_gate.py`
- Reports: `reports/ci_demo_env_compose_gate.md` und `.json`

Der Gate-Job prueft mindestens:

- `.env.demo.example` existiert und ist vollstaendig fuer Compose-Basisvariablen.
- `.env.demo` ist nicht im Git-Index (darf nie committed werden).
- Demo-Safety-Flags bleiben fail-closed:
  - `LIVE_TRADE_ENABLE=false`
  - `DEMO_ORDER_SUBMIT_ENABLE=false`
  - `DEMO_CLOSE_POSITION_ENABLE=false`
- Demo-Profil enthaelt keine Live-Key-Werte.
- `docker compose --env-file .env.demo.example config --services` laeuft ohne fehlende Variablen.

Wichtig: Demo-Evidence (auch `demo_lifecycle_verified`) ist weiterhin kein Live-Go. `private_live_allowed` und `full_autonomous_live` bleiben blockiert.
