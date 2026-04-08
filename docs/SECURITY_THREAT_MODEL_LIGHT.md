# Threat Model (light) + Schlüssel-Rotation + Postgres-Backup

Kurzfassung für Betrieb und Reviews — kein Ersatz für externes Pentesting oder Compliance-Audits.

## STRIDE (oberflächlich)

| Kategorie                  | Relevante Flächen im Repo                                                     | Maßnahmen (Auszug)                                                                                                                     |
| -------------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| **Spoofing**               | Gateway JWT, `X-Gateway-Internal-Key`, `X-Internal-Service-Key`, Legacy-Admin | Starke Secrets, kein Commit in Git; Prod: sensibles Auth erzwingen ([`docs/api_gateway_security.md`](api_gateway_security.md))         |
| **Tampering**              | API-Mutationen, Live-Broker-Safety, Replay-Routen                             | Manual-Action-Token, Feature-Flags, interne Keys ([`docs/Deploy.md`](Deploy.md))                                                       |
| **Repudiation**            | Trading-/Audit-Events                                                         | Gateway-Audit, DB-Journale ([`docs/observability.md`](observability.md))                                                               |
| **Information disclosure** | Logs, Health-JSON, Fehlerantworten                                            | Keine API-Keys/Passwörter loggen; Prod: reduzierte Exception-Details ([`docs/PROVIDER_ERROR_SURFACES.md`](PROVIDER_ERROR_SURFACES.md)) |
| **Denial of service**      | Öffentliche Edge, Webhooks                                                    | Rate-Limits Gateway, Härtung Reverse-Proxy ([`infra/reverse-proxy/`](../infra/reverse-proxy/))                                         |
| **Elevation of privilege** | Rollen in JWT, interne Header                                                 | Rollen-CSV für internen Gateway-Key begrenzen; `INTERNAL_API_KEY` nur serverseitig                                                     |

## Rotation (empfohlene Praxis)

| Secret                                          | Häufigkeit (Richtwert)                              | Vorgehen                                                                                      |
| ----------------------------------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `GATEWAY_JWT_SECRET`                            | Bei Verdacht oder 90–180 Tage                       | Neu ausrollen, kurz überlappend alte Tokens ablaufen lassen; alle Operator-JWT neu ausstellen |
| `INTERNAL_API_KEY` / `GATEWAY_INTERNAL_API_KEY` | Mit Personalwechsel oder 90 Tage                    | Services + Gateway gleichzeitig aktualisieren; Aufrufer-Header anpassen                       |
| `DASHBOARD_GATEWAY_AUTHORIZATION`               | Immer wenn Gateway-JWT-Geheimnis wechselt           | Dashboard-ENV aktualisieren, Deploy neu                                                       |
| `ADMIN_TOKEN` (Legacy)                          | Minimieren; in Prod durch JWT/Internal-Key ersetzen | Nur in nicht-produktiven Profilen                                                             |

Nach Rotation: `pnpm rc:health` bzw. `scripts/healthcheck.sh` und kritische Operator-Flows manuell prüfen.

## Incident (light)

Mindestablauf bei **vermuteter Kompromittierung** oder schwerem Vorfall (ohne vollständiges IR-Playbook).

1. **Eingrenzen:** betroffene Systeme/Keys benennen; unnötige Exposition stoppen (z. B. rotierende Keys, betroffene Tokens ungültig machen).
2. **Evidenz:** Zeitpunkt, betroffene Accounts/Rollen, Logs (ohne Secrets kopieren); `X-Request-ID` aus Support-Anfragen mit Gateway-Logs korrelieren.
3. **Kommunikation:** On-Call / Verantwortliche laut [`docs/OPERATOR_HANDBOOK.md`](OPERATOR_HANDBOOK.md); bei Datenpannen rechtliche/organisatorische Eskalation nach interner Policy.
4. **Wiederherstellung:** nach [`docs/emergency_runbook.md`](emergency_runbook.md) / [`docs/recovery_runbook.md`](recovery_runbook.md); Trading-/Kill-Switch-Aspekte beachten.
5. **Nachbereitung:** kurzes Post-Mortem (Ursache, Maßnahme, Follow-up); fehlende Rotation oder Monitoring-Lücken in die Checkliste übernehmen.

## Postgres: Backup & Verantwortung

- **Wer:** Betriebsteam / On-Call gemäß [`docs/OPERATOR_HANDBOOK.md`](OPERATOR_HANDBOOK.md) und Hosting-Policy.
- **Was sichern:** Volumen oder `pg_dump` der produktiven Datenbank (Schema + Daten), getrennt von Anwendungsserver.
- **Minimalbefehl (Beispiel, im DB-Container oder mit Client):**

```bash
# Beispiel — DSN und Pfade anpassen
pg_dump "$DATABASE_URL" -Fc -f "backup_$(date -u +%Y%m%dT%H%MZ).dump"
```

- **Restore:** `pg_restore` gegen leere oder vorbereitete DB; vorher [`docs/recovery_runbook.md`](recovery_runbook.md) beachten.
- **Tests:** Wiederherstellung regelmäßig auf Staging ausprobieren (Zeit + Integrität).

## Checkliste (1 Seite)

- [ ] Keine Produktions-Secrets in Repo oder öffentlichen Tickets
- [ ] `PRODUCTION=true`: `INTERNAL_API_KEY` gesetzt und Caller senden `X-Internal-Service-Key`
- [ ] Gateway: sensibles Auth aktiv; JWT- und interne Keys aus Secret-Store
- [ ] Letzter Backup-Restore-Test dokumentiert
- [ ] Nach Secret-Rotation: Health/Smoke grün
- [ ] On-Call kennt Einstieg: [`docs/OPS_QUICKSTART.md`](OPS_QUICKSTART.md) + Notfall-Runbooks
