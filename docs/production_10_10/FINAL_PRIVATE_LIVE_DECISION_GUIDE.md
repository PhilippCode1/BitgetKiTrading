# Final Private Live Decision Guide

## Was geprueft wurde

Der finale Go/No-Go-Check aggregiert Evidence-Matrix, Scorecard, Reports, Owner-Release
und Modusentscheidungen mit fail-closed Default.

## Was `verified` bedeutet

`verified` bedeutet: reale Runtime-/Betriebs-Evidence liegt vor, inklusive Owner-/Operator-
Pruefung, und ist maschinell nachvollziehbar.

## Was `implemented` bedeutet

`implemented` bedeutet: Code/Tests/Docs vorhanden, aber keine vollstaendige externe
Runtime-Abnahme. `implemented` ist **nicht** live-freigegeben.

## Welche externe Evidence Philipp liefern muss

- Staging/Shadow Runtime-Reports fuer offene P0/P1-Kategorien
- Alert-Zustellnachweis + SLO-Baseline
- Restore/DR/Shadow-Burn-in Echtlauf
- Owner-Signoff mit Referenz

## Wie Owner-Signoff funktioniert

Template: `docs/production_10_10/owner_private_live_release.template.json`  
Echte Datei: `reports/owner_private_live_release.json` (gitignored)

`owner_decision` muss explizit `GO` sein, sonst bleibt private live blockiert.

## Warum `private_live_allowed` NO_GO bleibt

Sobald ein P0/P1-Blocker offen ist oder externe Evidence fehlt, bleibt
`private_live_allowed=NO_GO`.

## Mindestbedingungen fuer erste private Live-Stufe

- alle relevanten P0/P1-Live-Blocker `verified`
- dokumentierter Scope (Assets/Families)
- initiales Leverage-Limit (standard 7x)
- Owner-Signoff vorhanden

## Warum full autonomous live spaeter kommt

`full_autonomous_live` braucht lange echte Live-Historie, stabile Runtime-Evidence,
forensische Abdeckung und explizite spaetere Owner-Freigabe; default bleibt `NO_GO`.

## Zwingende Schritte vor Echtgeld

1. Offene P0/P1 auf `verified` bringen.
2. Externe Runtime-/Drill-Evidence archivieren.
3. Owner-Release lokal gitignored einspielen.
4. Final-Go/No-Go erneut ausfuehren.

## Finale Pruefkommandos

```bash
python tools/check_10_10_evidence.py --check-report docs/production_10_10/evidence_status_report.md
python scripts/production_readiness_scorecard.py --output-md docs/production_10_10/production_readiness_scorecard.md
python scripts/final_go_no_go_report.py --output-md reports/final_go_no_go_report.md --output-json reports/final_go_no_go_report.json
python tools/check_release_approval_gates.py
```
