# Private Bitget Credential Safety (Philipp, Single-Owner)

## Ziel

Dieses Dokument beschreibt die verbindliche Credential-Sicherheitslogik fuer
Philipps private Bitget-Anbindung. Es gibt keine Kunden-Keys, keine
Mandantenstruktur und keine Billing-Abhaengigkeit. Alle Flows sind fail-closed.

## Credential-Statusmodell

- `missing`
- `placeholder`
- `configured_redacted`
- `demo_only`
- `readonly_verified`
- `trading_permission_detected`
- `withdrawal_permission_detected`
- `invalid`
- `expired_or_revoked`
- `rotation_required`
- `live_write_blocked`
- `live_write_eligible_after_all_gates`

## Harte Sicherheitsregeln

1. API-Key, Secret und Passphrase sind server-only und duerfen nie im Browser erscheinen.
2. Logs/Reports zeigen nur redacted/masked Hinweise.
3. Withdrawal-Permission ist P0 No-Go und blockiert Live sofort.
4. Trading-Permission alleine ist keine Live-Freigabe.
5. Read-only-Checks duerfen nie Orders senden.
6. Demo- und Live-Credentials duerfen nicht vermischt werden.
7. Placeholder-Werte sind nie runtime-gueltig.
8. `BITGET_DEMO_ENABLED=true` in Production ist kein echter Live-Betrieb.
9. Revoke/Expired blockiert Live.
10. Bei Unsicherheit: blockieren, `do_not_trade`, kein Live-Opening.

## Rotation und Revoke

### Rotation (planbar)

1. Neue Bitget-Credentials im Secret-Store hinterlegen (server-only).
2. Runtime mit read-only Diagnostik pruefen (keine Orders).
3. Alte Credentials deaktivieren.
4. Reconcile + Health + Main-Console kontrollieren.
5. Rotation-Evidence in Runbook/Report dokumentieren.

### Revoke/Incident

1. Sofortiges Blockieren aller Live-Write-Pfade.
2. Credential widerrufen/ersetzen.
3. Secret-Leak-Indikatoren pruefen und Logs redigieren.
4. Read-only-Check + Reconcile + Safety-Latch-Status verifizieren.

## Main-Console-Modul: Bitget-Verbindung

Die Main Console zeigt im Modul `Bitget-Verbindung`:

- Credential-Status (redacted)
- Demo/Live-Modus
- Read-only geprueft (ja/nein)
- Trading-Permission erkannt (ja/nein)
- Withdrawal-Permission erkannt/unklar
- Live-Write blockiert oder eligible nach allen Gates
- Letzte Pruefung
- Deutsche Blockgruende

## Externer Read-only-Pruefschritt

Die echte Bitget-Read-only-Verifikation muss extern gegen private read-only
Bitget-Endpunkte erfolgen. Das Script `scripts/private_bitget_credential_check.py`
fuehrt absichtlich keine Orders aus und bleibt im Runtime-Modus read-only.
