# Shadow Burn-in Certificate

## Warum Pflicht

Live-Trading darf erst starten, wenn Shadow ueber mindestens 72 Stunden stabile
Evidence liefert. Der Nachweis muss Multi-Asset-Datenqualitaet,
Reconcile-Failures, P0-Incidents und No-Trade-Gruende sichtbar machen.

## Sicherer Lauf

`scripts/verify_shadow_burn_in.py --dry-run` nutzt keine DB. Mit
`--input-json` kann ein Fixture ohne externe Systeme bewertet werden. Der echte
Run nutzt eine Runtime-Datenquelle und erzeugt einen archivierten Report.

## Keine echten Orders

Das Tool liest nur Shadow-/Audit-/Reconcile-Evidence oder Fixture-Daten. Es
sendet keine Orders.

## Reportfelder

Pflichtfelder sind Git-SHA, Ergebnis, beobachtete Stunden,
Multi-Asset-Datenqualitaet, Reconcile Failures, P0 Incidents, No-Trade-Gruende,
Blocker und Warnings.

## Externer Certificate-Contract

Der DB-/Fixture-Report ist nur ein Teil der Live-Evidence. Fuer private
Live-Freigabe muss zusaetzlich ein secret-freies Certificate-JSON gegen den
Contract geprueft werden:

```bash
python scripts/verify_shadow_burn_in.py \
  --certificate-json docs/production_10_10/shadow_burn_in_certificate.template.json \
  --strict \
  --output-md reports/shadow_burn_in_certificate.md \
  --output-json reports/shadow_burn_in_certificate.json
```

Das Repo-Template bleibt absichtlich `FAIL`, bis echte externe Evidence
vorliegt. Fuer Live muss mindestens belegt sein:

- 14 aufeinanderfolgende Kalendertage / mindestens 336 Stunden
- mindestens 3 Session-Cluster
- Stress-/Event-Tag dokumentiert
- `report_verdict=PASS` und `report_sha256`
- Git-SHA und Runtime-ENV-Snapshot-SHA256
- `EXECUTION_MODE=shadow`, `LIVE_TRADE_ENABLE=false`
- `SHADOW_TRADE_ENABLE=true`, `LIVE_BROKER_ENABLED=true`
- Shadow-vor-Live, Operator-Release und Execution-Binding aktiv
- maximaler Ramp-Hebel `<=7`
- beobachtete Symbole, Marktfamilien und Playbook-Familien
- mindestens je ein `candidate_for_live`, `shadow_only` und `do_not_trade`
- keine P0/P1-Incidents, Reconcile-Fails, Shadow-Live-Mismatches,
  kritischen Alerts, Data-/Liquidity-/Risk-Gate-Fails
- Audit-/Forensics-Stichprobe mit Referenz
- externer Review und Evidence-Referenz
- Owner-Signoff separat vorhanden

Felder mit Secret-Bezug wie `database_url`, `dsn`, `password`, `secret`,
`token`, `api_key` oder `private_key` duerfen keine echten Werte enthalten.

## No-Go-Regeln

Weniger als 72 Stunden, P0 Incident, Reconcile-Failure oder fehlende
Multi-Asset-Datenqualitaet blockieren Live.

## Philipp liest den Report

Philipp prueft `Ergebnis`, `Beobachtete Stunden`, Blocker und Warnings. Nur
`PASS` ohne ungeklärte Blocker kann als Burn-in-Evidence fuer Live gelten.
