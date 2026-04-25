# No-Go Rules fuer Echtgeld-Live

Diese Regeln sind harte Blocker. Wenn eine Regel verletzt ist oder Evidence
fehlt, darf `bitget-btc-ai` keinen echten Echtgeld-Live-Betrieb aufnehmen.
Keine Ausnahme darf im Code versteckt werden. Ausnahmen brauchen dokumentierten
externen Signoff und duerfen Fail-closed nicht schwaechen.

## Harte Blocker

1. Kein Echtgeld-Live, wenn kein Shadow-Burn-in-Report existiert.
2. Kein Echtgeld-Live, wenn kein Restore-Test dokumentiert ist.
3. Kein Echtgeld-Live, wenn Branch-Protection nicht dokumentiert und extern
   gesetzt ist.
4. Kein Echtgeld-Live, wenn echte Secrets in `.env`, Logs, Browser,
   Testfixtures oder Doku auftauchen.
5. Kein Echtgeld-Live, wenn `LIVE_TRADE_ENABLE=true` ohne Operator-Release
   moeglich ist.
6. Kein Echtgeld-Live, wenn Redis-Ausfall zu unsicherem Order-Submit fuehren
   kann.
7. Kein Echtgeld-Live, wenn Kunden-API-Keys im Browser erscheinen koennten.
8. Kein Echtgeld-Live, wenn keine Rollback-Revision dokumentiert wurde.
9. Kein Echtgeld-Live, wenn Alerting nicht zu einem echten Kanal fuehrt.
10. Kein Echtgeld-Live, wenn keine klare Kunden-/Tenant-Isolation besteht.
11. Kein Echtgeld-Live, wenn keine Compliance-/Legal-Freigabe dokumentiert ist.
12. Kein Echtgeld-Live, wenn kein Kill-Switch-Drill dokumentiert ist.
13. Kein Echtgeld-Live, wenn kein Emergency-Flatten-Drill dokumentiert ist.
14. Kein Echtgeld-Live, wenn keine klare Haftungs- und Risikohinweis-Logik fuer
    Kunden existiert.
15. Kein Echtgeld-Live, wenn `EXECUTION_MODE=live`,
    `LIVE_BROKER_ENABLED=true` oder `LIVE_TRADE_ENABLE=true` in einem Default-,
    Test- oder Beispielprofil echte Orders beguenstigt.
16. Kein Echtgeld-Live, wenn Exchange-Health oder Exchange-Truth fehlt.
17. Kein Echtgeld-Live, wenn Reconcile-Divergenz offen ist.
18. Kein Echtgeld-Live, wenn Safety-Latch aktiv oder ungeklaert ist.
19. Kein Echtgeld-Live, wenn Kill-Switch aktiv oder ungeklaert ist.
20. Kein Echtgeld-Live, wenn Risk-Governor-Timeouts, Provider-Fehler oder stale
    Daten als Freigabe interpretiert werden.
21. Kein Echtgeld-Live, wenn Commercial-, Billing- oder Tenant-Gates fehlen.
22. Kein Echtgeld-Live, wenn Audit-Trails fuer Operator-Release, Risk-Entscheid
    oder Order-Lifecycle fehlen.
23. Kein Echtgeld-Live, wenn reale API-Keys mehr Rechte haben als dokumentiert
    und freigegeben.
24. Kein Echtgeld-Live, wenn ENV-Profile nicht mit Validatoren geprueft wurden.
25. Kein Echtgeld-Live, wenn offene P0/P1-Blocker in Release-/Freeze-Doku
    existieren.
26. Kein Echtgeld-Live, wenn Secret Rotation, Expiry-Tracking, Owner,
    Environment-Trennung oder Credential-Hygiene-Evidence fehlt.

## Evidence-Anforderungen pro Freigabe

Ein Live-Go/No-Go-Paket muss mindestens enthalten:

- Git-SHA und Release-Version
- ausgefuehrte Release-Gates mit Exit-Code
- Shadow-Burn-in-Report mit PASS und SHA256
- Restore-Drill-Report mit RTO/RPO und PASS
- Alert-Drill mit echtem Zustellnachweis
- Kill-Switch-Drill
- Emergency-Flatten-Drill
- Branch-Protection-Nachweis aus GitHub oder Org-Export
- Secret-Scanner-/Vault-/KMS-Nachweis
- Secret Rotation Report mit Owner, Environment, Ablaufstatus und Revoke-Nachweis
- Operator-Approval-Protokoll
- Risk-Governance-Signoff
- Tenant-/Commercial-/Billing-Signoff
- Compliance-/Legal-Signoff
- Rollback-Revision und Rollback-Plan

Fehlt ein Element, ist der Live-Status `external_required` oder `missing`, nie
`verified`.

## Codex-Verhalten bei No-Go-Treffern

Codex muss:

1. die Aenderung stoppen oder fail-closed absichern,
2. den No-Go-Treffer in der Abschlussmeldung nennen,
3. betroffene Dateien und Tests dokumentieren,
4. keine Live-Freigabe behaupten,
5. den naechsten konkreten Evidence-Schritt nennen.
