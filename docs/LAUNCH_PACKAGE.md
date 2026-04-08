# Launch-Paket — sauberer Produktbetrieb

**Zweck:** Ein Index fuer **Single-Host-/URL-Betrieb**, **ehrliche Produkt- und Preislogik** und **klare externe Abhaengigkeiten**. Keine finale Betriebsabnahme ersetzt dieses Paket — es strukturiert, was im Repo belegt ist und was ausserhalb liegt.

**Operativer Ersteinstieg (Start, Stop, Health, Logs, Keys, Eskalation):** [`docs/OPS_QUICKSTART.md`](OPS_QUICKSTART.md).

## Inhalt (kanonische Dateien)

| Thema                                                                                             | Dokument                                                                        |
| ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **Ops-Quickstart** (Start, Health, Keys, Eskalation — ein Einstieg)                               | `docs/OPS_QUICKSTART.md`                                                        |
| **Betreiberhandbuch** (Proxy, TLS, Health, Cookies, CORS/CSP, Backup, Eskalation)                 | `docs/OPERATOR_HANDBOOK.md`                                                     |
| **Externe Go-Live-Abhaengigkeiten** (Secrets, Domain, TLS, WAF, Recht, Kapital, On-Call, Backups) | `docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md`                                         |
| **Plaene, Entitlements, Metering, Caps, Upgrade/Downgrade**                                       | `docs/PRODUCT_PLANS_AND_USAGE.md`                                               |
| **Kommerzielle Integritaet** (Ledger, keine versteckten Multiplikatoren)                          | `docs/commercial_transparency.md`                                               |
| **URLs & Secrets**                                                                                | `docs/operator_urls_and_secrets.md`                                             |
| **Reverse-Proxy-Vorlagen**                                                                        | `infra/reverse-proxy/README.md`, `nginx.single-host.conf`                       |
| **Freigabeleiter & CI-Gates**                                                                     | `docs/LAUNCH_DOSSIER.md`, `docs/ci_release_gates.md`                            |
| **Operator-Onboarding**                                                                           | `docs/operator_onboarding_checklist.md`                                         |
| **Recovery / Notfall**                                                                            | `docs/recovery_runbook.md`, `docs/emergency_runbook.md`, `docs/prod_runbook.md` |

## Produktpositionierung (ohne ueberhoehte Claims)

Das Produkt wird **verkaufsfaehig** durch:

- **Transparenz:** nachvollziehbare Signale, Gates, Journale, Usage-Ledger (List-USD), dokumentierte Caps.
- **Sicherheit:** erzwungenes sensibles Gateway-Auth in Prod, Rate-Limits, Audit, manuelle Aktions-Tokens fuer Hochrisiko-Pfade.
- **Stabilitaet:** definierte Health-/Readiness-Pfade, Stack-Readiness, Reconcile-/Recovery-Doku — ohne Garantie fuer fehlerfreien Dauerbetrieb ohne Betriebspflege.
- **Ehrlichkeit:** `do_not_trade` und No-Trade-Spikes sind **legitime** Zustaende; es gibt **keine** zugesicherte Ueberrendite, keinen garantierten Gewinn und keine „beste Strategie der Welt“.

Alles, was wie eine **Performance- oder Gewinngarantie** klingt, ist **kein** Bestandteil der Produktwahrheit dieses Repos.

## Schnellpfad nach dem Deploy

1. `docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md` abarbeiten (extern).
2. ENV laut `docs/Deploy.md` / `.env.production.example` und `docs/operator_urls_and_secrets.md`.
3. TLS + Reverse-Proxy: `infra/reverse-proxy/`.
4. `curl` / `scripts/healthcheck.sh` und `GET /v1/deploy/edge-readiness` (siehe Handbuch).
5. `docs/operator_onboarding_checklist.md` fuer das Team.
