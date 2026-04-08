# Echte externe Go-Live-Abhaengigkeiten

Alles in dieser Liste liegt **ausserhalb** des Repos oder erfordert **organisatorische** Entscheidungen. Ohne diese Punkte haelt produktiver Betrieb **nicht** allein durch Codequalitaet zusammen.

## 1. Secrets und Identitaet

| Bereich           | Was fehlt typischerweise im Repo                                                                  |
| ----------------- | ------------------------------------------------------------------------------------------------- |
| Datenbank / Redis | Produktions-DSNs, Passwoerter, TLS-Clientzertifikate falls genutzt                                |
| Gateway           | `GATEWAY_JWT_SECRET` und/oder `GATEWAY_INTERNAL_API_KEY`, ggf. Metering `COMMERCIAL_METER_SECRET` |
| Exchange          | Bitget API Key/Secret/Passphrase (nur Laufzeit)                                                   |
| Telegram          | Bot-Token, Webhook-Secret, erlaubte Chat-IDs                                                      |
| LLM / News        | Provider-Keys nach aktivierten Pfaden                                                             |
| Rotation          | Prozess und Verantwortung (Vault/KMS/Secret Manager)                                              |

## 2. Domain, DNS, TLS

- Oeffentliche Hostnamen fuer API und Dashboard (oder bewusst ein Host mit Pfad — dann Doku und CORS anpassen).
- Zertifikate (Let’s Encrypt, interne PKI, Cloud-CA) und **Erneuerung**.
- **Kein** Commit von Private Keys ins Repo.

## 3. Edge: Reverse Proxy, WAF, DDoS

- Betrieb von **nginx** (Vorlage im Repo) oder vergleichbar; `X-Forwarded-Proto`, `X-Forwarded-Host` korrekt setzen.
- Optional: WAF, Rate-Limiting vor dem Gateway, IP-Allowlists fuer Admin — **Policy und Betrieb** liegen bei Infra.

## 4. Recht, Vertrag, Kapital

- Vertragsgrundlage mit Endkunden (AGB, Auftragsdatenverarbeitung, Risikoaufklaerung) — **Rechtsrolle**.
- **Kein** implizites „Anlageberatung“-Versprechen durch Marketingtexte; Produktpositionierung siehe `docs/LAUNCH_PACKAGE.md`.
- **Kapital- und Verlustgrenzen** am Exchange-Konto; Margin-Modus; erlaubte Produkte.

## 5. Betrieb: On-Call, Incidents, Support-Kanaele

| Thema                      | Hinweis                                                                                                                                 |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **On-Call / Paging**       | Alertmanager, Telefonkette, Eskalationsmatrix — **nicht** im Repo                                                                       |
| **Support fuer Endkunden** | E-Mail/Ticket-System (z. B. `SUPPORT_EMAIL`, `STATUS_PAGE_URL` als ENV-Platzhalter in `.env.production.example` — Werte nur ausserhalb) |
| **Statusseite**            | Oeffentliche oder interne Incident-Kommunikation                                                                                        |
| **SLA**                    | Vertraglich; technische SLOs siehe `docs/observability_slos.md` (Orientierung, keine Garantie)                                          |

## 6. Backups und Restore

- **Postgres:** regelmaessige Snapshots/PITR; **Restore-Probe** mindestens einmal dokumentiert durchfuehren.
- **Redis:** Persistenz-Modus und Obacht bei Eventbus — Recovery-Szenario dokumentieren (`docs/OPERATOR_HANDBOOK.md`).
- **Konfiguration:** Export sicherer ENV-Metadaten (ohne Secrets) in Secret-Store-Versionierung.

## 7. Monitoring und Audit ausserhalb des Stacks

- Zentrale Log-Sammlung (SIEM optional).
- Externe Uptime-Checks gegen `/health` bzw. `/ready` (API) und Dashboard `/api/health`.

## Checkliste (Kurz)

- [ ] Alle Secrets in Secret Store; Rotation geklaert
- [ ] DNS + TLS live
- [ ] `APP_BASE_URL`, `FRONTEND_URL`, `CORS_ALLOW_ORIGINS`, `NEXT_PUBLIC_*` auf Produktionswerte
- [ ] `GET /v1/deploy/edge-readiness` ohne kritische Findings
- [ ] Backup/Restore getestet
- [ ] On-Call und Incident-Kette benannt
- [ ] Support-Kontakt und (optional) Status-URL kommuniziert
