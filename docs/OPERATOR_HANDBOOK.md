# Betreiberhandbuch — Single-Host, URLs, Sicherheit am Edge

**Einstieg On-Call / lokaler Stack (Start, Stop, Health, Logs, Keys):** zuerst [`docs/OPS_QUICKSTART.md`](OPS_QUICKSTART.md). Dieses Handbuch vertieft Proxy, TLS, URLs und Edge-Sicherheit.

Ergaenzung zu `docs/prod_runbook.md`, `docs/operator_urls_and_secrets.md`, `infra/reverse-proxy/README.md`.

## 1. Architektur-Skizze (typisch)

```
Internet → TLS (nginx o.ä.) → 127.0.0.1:8000 (api-gateway)
                              → 127.0.0.1:3000 (dashboard)
         Postgres / Redis      (Compose intern oder verwalteter Dienst)
```

## 2. Domain- und URL-Variablen (Pflichtkonsistenz)

| Variable                   | Bedeutung                                                                         |
| -------------------------- | --------------------------------------------------------------------------------- |
| `APP_BASE_URL`             | Kanonische **https**-Basis des API-Gateways (ohne trailing slash-Path-Wildwuchs). |
| `FRONTEND_URL`             | Kanonische **https**-URL des Dashboards.                                          |
| `NEXT_PUBLIC_API_BASE_URL` | Gleiche API-Basis; **Build-Zeit** des Dashboard-Images.                           |
| `NEXT_PUBLIC_WS_BASE_URL`  | **wss://** zum API-Host fuer SSE.                                                 |
| `CORS_ALLOW_ORIGINS`       | Kommagetrennt; jede Browser-Origin des Dashboards muss exakt enthalten sein.      |

**Fehlerquelle:** Dashboard neu bauen, nachdem `NEXT_PUBLIC_*` geaendert wurde.

## 3. Reverse Proxy und TLS (Platzhalter)

- Vorlagen: `infra/reverse-proxy/nginx.single-host.conf` (zwei `server_name`, getrennte Zertifikate moeglich).
- **Immer** setzen: `X-Forwarded-Proto: https`, sinnvoll `X-Forwarded-Host`.
- Gateway: bei HTTPS `GATEWAY_SEND_HSTS=true`, `GATEWAY_SSE_COOKIE_SECURE=true`.

Siehe auch `GET /v1/deploy/edge-readiness` (ohne Auth).

## 4. Cookies und Sessions

- **JWT / Internal-Key:** Standard fuer API-Zugriff vom Dashboard ueber serverseitigen Proxy (`DASHBOARD_GATEWAY_AUTHORIZATION`); keine Long-Lived Secrets im Browser.
- **SSE-Session-Cookie:** Kurzlebig, signiert; `Secure` + passendes `SameSite` (`GATEWAY_SSE_COOKIE_*`).
- Siehe `docs/api_gateway_security.md`, `docs/security_ops.md`.

## 5. CORS und CSP

- **CORS:** nur explizite Origins; in Prod keine `*`.
- **CSP (API JSON):** `GATEWAY_CONTENT_SECURITY_POLICY` — restriktiv fuer JSON-API; leer = kein CSP-Header (falls Edge CSP uebernimmt, abstimmen).
- **Dashboard:** Next.js setzt eigene Security-Header; mit API-Origin `connect-src` abstimmen (`NEXT_PUBLIC_API_BASE_URL`).

## 6. Health, Readiness, Liveness (Matrix)

| Pfad                            | Dienst      | Zweck                                                                                                                                                                                                           |
| ------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /health`                   | api-gateway | **Liveness** — Prozess lebt (kein DB-Zwang).                                                                                                                                                                    |
| `GET /ready`                    | api-gateway | **Readiness** — Postgres, Redis, Schema/Migrationen, optional Peer-URLs (`READINESS_REQUIRE_URLS`). Payload enthaelt immer `checks` + `summary`; verbindlich ist `ready: true` nur bei allen Kern-Checks gruen. |
| `GET /v1/system/health`         | api-gateway | Aggregierter Ops-Status (Auth: Operator-Aggregat).                                                                                                                                                              |
| `GET /v1/deploy/edge-readiness` | api-gateway | TLS/CORS/Forward-Header-Checkliste.                                                                                                                                                                             |
| `GET /api/health`               | dashboard   | **Liveness** des Next-Servers (JSON `status: ok`).                                                                                                                                                              |

**Load Balancer:** typisch `GET /health` (API) und `GET /api/health` (Dashboard) — Timeouts groesser als SSE-Pfade nur am Upstream, nicht global absenken ohne Grund.

## 7. Backup und Restore (Hinweise)

| Komponente        | Mindestempfehlung                                                                                           |
| ----------------- | ----------------------------------------------------------------------------------------------------------- |
| **Postgres**      | Taegliche konsistente Backups; Restore-Runbook mit Test-Restore; Migrationen vor Restore-Version pruefen.   |
| **Redis**         | Persistenz-Strategie kennen; bei Eventbus-Verlust: Neuaufsetzung der Consumer-Offsets laut Betriebskonzept. |
| **Konfiguration** | Secret Store + Infrastructure-as-Code ausserhalb des App-Repos.                                             |

Detail: `docs/recovery_runbook.md`, `docs/db-schema.md` (Tabellenueberblick).

## 8. Incidents und Eskalation

1. **P0 Trading-Stopp pruefen:** Kill-Switch, Safety-Latch, `LIVE_TRADE_ENABLE` — `docs/emergency_runbook.md`.
2. **Forensik:** `execution_id`, Gateway-Audit, Live-Broker-Journal — `docs/live_broker.md`.
3. **Alerts:** Monitor-Engine / Telegram — `docs/monitoring_runbook.md`.
4. **Extern:** On-Call-Kette und Ticket-System (siehe `docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md`).

## 9. Verkaufsfaehige Qualitaet (keine Marketinggarantien)

- Transparenz bei **No-Trade** und **Abstention** ist Feature, kein Bug.
- **Performance** und **Gewinn** sind **nicht** zugesichert; Risiko liegt beim Kunden und der erlaubten Konfiguration.
