# No-Go Rules fuer Echtgeld-Live

Diese Regeln sind harte Blocker. Wenn eine Regel verletzt ist oder Evidence
fehlt, darf `bitget-btc-ai` keinen echten Echtgeld-Live-Betrieb aufnehmen.
Keine Ausnahme darf im Code versteckt werden. Ausnahmen brauchen dokumentierten
externen Signoff und duerfen Fail-closed nicht schwaechen.

Die Produktentscheidung ist privat: einziger Nutzer ist Philipp Crljic. No-Go-
Regeln duerfen deshalb nicht ueber Billing-, Customer- oder Sales-Flows
aufgeweicht werden. Solche Flows sind kein Produktziel.

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
7. Kein Echtgeld-Live, wenn Bitget-API-Keys, private Betreiber-Secrets oder
   Legacy-Kunden-API-Key-Pfade im Browser erscheinen koennten.
8. Kein Echtgeld-Live, wenn keine Rollback-Revision dokumentiert wurde.
9. Kein Echtgeld-Live, wenn Alerting nicht zu einem echten Kanal fuehrt.
10. Kein Echtgeld-Live, wenn Legacy-Kunden-/Tenant-Pfade noch aktiv,
    unklar oder nicht vom privaten Owner-Scope getrennt sind.
11. Kein Echtgeld-Live, wenn keine Compliance-/Legal-Freigabe dokumentiert ist.
12. Kein Echtgeld-Live, wenn kein Kill-Switch-Drill dokumentiert ist.
13. Kein Echtgeld-Live, wenn kein Emergency-Flatten-Drill dokumentiert ist.
14. Kein Echtgeld-Live, wenn keine klare private Risiko-, Haftungs- und
    Owner-Freigabelogik fuer Philipp existiert.
15. Kein Echtgeld-Live, wenn `EXECUTION_MODE=live`,
    `LIVE_BROKER_ENABLED=true` oder `LIVE_TRADE_ENABLE=true` in einem Default-,
    Test- oder Beispielprofil echte Orders beguenstigt.
16. Kein Echtgeld-Live, wenn Exchange-Health oder Exchange-Truth fehlt.
17. Kein Echtgeld-Live, wenn Reconcile-Divergenz offen ist.
18. Kein Echtgeld-Live, wenn Safety-Latch aktiv oder ungeklaert ist.
19. Kein Echtgeld-Live, wenn Kill-Switch aktiv oder ungeklaert ist.
20. Kein Echtgeld-Live, wenn Risk-Governor-Timeouts, Provider-Fehler oder stale
    Daten als Freigabe interpretiert werden.
21. Kein Echtgeld-Live ohne Asset-Freigabe fuer das konkrete Bitget-Instrument.
22. Kein Echtgeld-Live ohne Bitget Readiness fuer Instrument, Marktmodus,
    Precision, API-Status und Exchange-Health.
23. Kein Echtgeld-Live ohne frische Datenqualitaet.
24. Kein Echtgeld-Live ohne Liquiditaetspruefung.
25. Kein Echtgeld-Live ohne Risk-Governor-Freigabe.
26. Kein Echtgeld-Live ohne Operator-/Owner-Freigabe durch Philipp.
27. Kein Echtgeld-Live bei Kill-Switch oder Safety-Latch.
28. Kein Echtgeld-Live bei Reconcile-Fail.
29. Kein Echtgeld-Live bei ungeklaertem Exchange-Order-State.
30. Kein Echtgeld-Live bei fehlendem Restore-/Shadow-/Safety-Evidence fuer
    echte Produktionsfreigabe.
31. Keine englischen UI-Texte in der finalen Anwendung.
32. Keine Billing-, Customer-, Sales-, Payment- oder Subscription-Flows als
    Produktziel.
33. Kein Echtgeld-Live ohne dokumentierte Bitget-Exchange-Readiness pro Asset.
34. Kein Echtgeld-Live, wenn Legacy-Commercial-, Billing-, Customer- oder
    Tenant-Abhaengigkeiten den Live-Pfad unklar machen.
35. Kein Echtgeld-Live, wenn Audit-Trails fuer Operator-Release, Risk-Entscheid
    oder Order-Lifecycle fehlen.
36. Kein Echtgeld-Live, wenn reale API-Keys mehr Rechte haben als dokumentiert
    und freigegeben.
37. Kein Echtgeld-Live, wenn ENV-Profile nicht mit Validatoren geprueft wurden.
38. Kein Echtgeld-Live, wenn offene P0/P1-Blocker in Release-/Freeze-Doku
    existieren.
39. Kein Echtgeld-Live, wenn Secret Rotation, Expiry-Tracking, Owner,
    Environment-Trennung oder Credential-Hygiene-Evidence fehlt.
40. Keine oeffentliche Launch-, Marketing- oder Verkaufsfreigabe als Ziel fuer
    dieses private System.
41. Kein Echtgeld-Live, wenn Bitget Readiness keine aktuelle Read-only-Evidence
    fuer API-Version, Permissions, Server-Time, Rate-Limits und Instrument
    Discovery hat.
42. Kein Echtgeld-Live, wenn Bitget-Keys Withdrawal-Rechte besitzen oder die
    Permission-Lage unklar ist.
43. Kein Echtgeld-Live, wenn Bitget API-Version unklar ist oder V1-Pfade fuer
    Exchange-Readiness genutzt werden.
44. Kein Echtgeld-Live ohne vollstaendigen Instrumentkontext (ProductType,
    MarginCoin, Tick Size, Lot Size, MinQty, MinNotional, Precision und frische
    Metadaten).
45. Kein Echtgeld-Live bei stale/duennem Orderbook, zu hohem Spread, zu hoher
    Slippage oder unklarer Liquiditaets-Tier-Lage.
46. Kein Echtgeld-Live bei unknown oder high-risk Asset-Tier-Lage (insbesondere
    Tier D/Tier E) ohne explizite, verifizierte Owner-Freigabe.
47. Kein Echtgeld-Live bei unsicherer Positionsgroesse, unklarer Equity,
    ueberschrittenen Margin-/Loss-/Drawdown-Limits oder risk-erhoehendem
    Precision-Rounding.
48. Kein Echtgeld-Live bei unklarem Portfolio-Risiko, stale/missing Portfolio-
    Snapshot, ueberhoher Korrelation, Richtungskonzentration oder Exposure-
    Ueberschreitung durch offene/pending Positionen.
49. Kein Echtgeld-Live ohne gueltige Strategie-/Signal-Evidence pro Asset oder
    Asset-Klasse (inklusive Strategy-Version, Scope-Match, Shadow-Evidence und
    nicht abgelaufenem Status).
50. Kein Echtgeld-Live ohne vollstaendigen Live-Broker-Preflight vor jedem
    Opening-Submit (fehlende/unknown/stale Gates, fehlende Idempotency oder
    fehlender Audit-Context blockieren zwingend).
51. Kein Echtgeld-Live bei Reconcile-Unklarheit, Exchange-Truth-Drift,
    stale Reconcile-Zustand oder unbekanntem Order-State pro Asset/Position.
52. Kein Echtgeld-Live bei unknown submit state, Duplicate-Order-Risiko,
    Retry ohne Reconcile oder unsicherem Exit-/Emergency-Flatten-Verhalten.
53. Kein Echtgeld-Live ohne maschinenlesbare Owner-Freigabe
    (`reports/owner_private_live_release.json`, gitignored) mit gueltiger
    Struktur; die Datei darf niemals ins Repository committet werden.

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
- lokale maschinelle Owner-Freigabe (`reports/owner_private_live_release.json`,
  nicht im Git-Index; Template unter `docs/production_10_10/`)
- Risk-Governance-Signoff
- Asset-, Datenqualitaets-, Liquiditaets- und Owner-Freigabe
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
