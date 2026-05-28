# Release Evidence (L4/L5)

Dieses Verzeichnis enthält **externe, signierte oder operatorisch bestätigte**
Nachweise für Production-Readiness. Der Code allein reicht für „10/10 mit echtem
Geld" nicht aus.

## Marker-Format

Jede Markdown-Datei kann einen Marker enthalten, den
`tools/production_readiness_audit.py` auswertet (exakt eine Zeile, kein Codeblock):

```text
readiness_mark: L<n> category=<kategorie>
```

Beispiel-Format (nicht als echte Evidence committen — siehe README):

    readiness_mark: L[4|5] category=[kategorie_id]

Erlaubte Level: `L4`, `L5`. Kategorien müssen zum Audit passen, z. B.:

| category | Inhalt |
|---|---|
| `shadow_burn_in` | 14-Tage-Shadow-Zertifikat + Report-SHA256 |
| `disaster_recovery` | Externes DR-Restore-Audit |
| `security_audit` | Pen-Test / externes Security-Audit |
| `alert_routing` | Slack/PagerDuty-Produktionsnachweis |

## Beispiel-Shadow-Evidence (Platzhalter)

Datei `shadow_burn_in_YYYY-MM.md` anlegen **nach** echtem Burn-in — nicht vorab
mit PASS füllen. Siehe `docs/shadow_burn_in_ramp.md` und
`scripts/verify_shadow_burn_in.py`.

Pflichtzeile in der Evidence-Datei: `readiness_mark:` + Level `L4` oder `L5` +
`category=shadow_burn_in` (eine Zeile, exakt wie im Audit-Regex dokumentiert).

Weitere Felder:

## Wichtig

- **Keine Secrets** in diesen Dateien (API-Keys, DSNs, Tokens).
- Fixture-PASS zählt nicht als Live-Freigabe.
- `--strict` im Production-Readiness-Audit bleibt rot, bis echte L4/L5-Marker existieren.
