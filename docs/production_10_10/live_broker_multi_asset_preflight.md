# Live-Broker Multi-Asset Preflight

## Warum das letzte Sicherheitsgate

Der Live-Broker ist die letzte technische Instanz vor einem echten Order-Submit.
Er darf nie nur einem Signal, UI-Flag oder Einzelgate vertrauen.

## Pflicht-Gates vor jedem Opening-Submit

1. Execution mode live.
2. `LIVE_TRADE_ENABLE=true`.
3. Owner-Freigabe Philipp vorhanden.
4. Asset im Katalog.
5. Asset nicht delisted/suspended/unknown.
6. Asset `live_allowed`.
7. Instrument-Order-Contract vollstaendig.
8. Metadaten frisch.
9. Datenqualitaet livefaehig.
10. Liquiditaet ausreichend.
11. Slippage unter Schwelle.
12. Risk-Tier livefaehig.
13. Order-Sizing sicher.
14. Portfolio-Risk sicher.
15. Strategy-Evidence passend.
16. Bitget-Readiness ok.
17. Reconcile ok.
18. Kill-Switch inaktiv.
19. Safety-Latch inaktiv.
20. Kein unknown order state.
21. Kein stale account snapshot.
22. Idempotency-Key vorhanden.
23. Audit-Context vorhanden.

## Harte Regeln

- Fehlendes/unknown/stale Pflichtgate blockiert.
- Warning blockiert standardmaessig, ausser explizit als erlaubte Warning konfiguriert.
- Preflight-PASS bedeutet nur: Submit darf versucht werden.
- Preflight muss auditierbar sein.
- Keine Secrets in Preflight-Logs.

## Blockgruende und Audit

Die Preflight-Entscheidung liefert:

- `blocking_reasons`
- `warning_reasons`
- `missing_gates`
- `checked_at`
- auditfaehiges Payload ohne Secret-Daten

## Main-Console Anzeige

Pro Live-Kandidat muss spaeter sichtbar sein:

- Preflight-Status
- fehlende Gates
- blockierende Gruende
- Warning-Gruende
- letzter Aktualisierungszeitpunkt
- deutscher Hinweis: "nicht handelbar, weil ..."

## Teststrategie

- Security-Tests fuer harte Blockaden.
- Contract-Tests fuer gruenen Preflight-Pfad ohne echten Submit.
- Checker-Tests fuer Doku-/Test-/No-Go-Konsistenz.

## Externer Fail-Closed-Contract

Die synthetische Preflight-Matrix ist Code-Evidence, aber keine Live-Freigabe.
Fuer private Live-Evidence muss ein echter Staging-/Shadow-Drill als
secret-freies JSON gegen den Contract geprueft werden:

```bash
python tools/check_live_broker_preflight.py \
  --evidence-json docs/production_10_10/live_broker_fail_closed_evidence.template.json \
  --strict \
  --write-report reports/live_broker_fail_closed_evidence.md \
  --output-json reports/live_broker_fail_closed_evidence.json
```

Das Repo-Template bleibt absichtlich `FAIL`, bis echte Evidence vorliegt. Fuer
Live muss mindestens belegt sein:

- Preflight-Matrix `PASS` und alle Pflicht-Blockgruende abgedeckt
- Providerfehler blockieren Submit
- fehlendes Redis blockiert Live
- fehlende DB blockiert Live
- fehlende Exchange-Truth blockiert Submit
- Public-/Private-API-Timeouts blockieren Submit
- stale Market Data blockiert Submit
- unknown Instrument blockiert Submit
- fehlender Risk-Kontext blockiert Submit
- fehlende Operator-Freigabe blockiert Submit
- fehlender Shadow-Match blockiert Submit
- Reconcile-Fail blockiert Submit
- Kill-Switch und Safety-Latch blockieren Submit
- fehlende Idempotency und fehlender Audit-Context blockieren Submit
- Warnings blockieren standardmaessig Live
- All-green-Kontrollfall sendet keine echte Exchange-Order
- Audit-Trail, Alert-Zustellung und Main-Console-Gate-State verifiziert
- `live_write_allowed_during_drill=false`
- `real_exchange_order_sent=false`
- Owner-Signoff separat vorhanden

Felder mit Secret-Bezug wie `database_url`, `redis_url`, `authorization`,
`token`, `secret`, `password` oder `api_key` duerfen keine echten Werte
enthalten.

## No-Go

Ohne vollstaendigen Multi-Asset-Preflight kein Live-Opening.
