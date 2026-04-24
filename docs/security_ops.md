# Sicherheit — Ops-Pfad (Prompt 33)

Dieses Dokument fasst **Sicherheitsentscheidungen** und den **Betriebsablauf** zusammen. Es ersetzt keine Threat-Modeling- oder Pen-Test-Dokumentation.

## 1. Netzwerk und Docker Compose

| Massnahme         | Details                                                                                                                                                                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Internes Netz** | Services sprechen untereinander nur über `bitget_ai_net`. Postgres/Redis haben im **Basis-Compose** keinen Host-Port.                                                                                                                              |
| **Edge-Bind**     | `api-gateway`, `dashboard`, Prometheus und Grafana publizieren standardmässig auf **`127.0.0.1`** (`COMPOSE_EDGE_BIND`, Default in `docker-compose.yml`). Remote-Zugriff nur über Reverse-Proxy/Firewall oder bewusst `COMPOSE_EDGE_BIND=0.0.0.0`. |
| **Dev-Overlay**   | `docker-compose.local-publish.yml` bindet Debug-Ports ebenfalls standardmässig an **`127.0.0.1`** (`COMPOSE_LOCAL_PUBLISH_BIND`).                                                                                                                  |

Siehe auch `docs/compose_runtime.md`.

## 2. Secrets und Frontend

| Regel                                | Umsetzung                                                                                                                    |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------- |
| **Keine Secrets in `NEXT_PUBLIC_*`** | Nur nicht-sensible Konfiguration im Browser; `DASHBOARD_GATEWAY_AUTHORIZATION` nur **Server-ENV** (Next Route Handlers).     |
| **Gateway**                          | `GATEWAY_JWT_SECRET`, `GATEWAY_INTERNAL_API_KEY`, `ADMIN_TOKEN` nur aus Secret-Store / ENV-Dateien mit restriktiven Rechten. |
| **CORS**                             | `CORS_ALLOW_ORIGINS` in Produktion explizit auf die **Dashboard-Origin(s)** setzen, nicht `*`.                               |
| **Build**                            | Keine `--build-arg` für API-Keys im Dashboard-Dockerfile; Images ohne eingebettete Tokens bauen.                             |

## 3. API-Gateway (HTTP)

- **Security-Header** (alle Antworten): `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`.
- **HSTS**: nur wenn TLS am Browser ankommt — `GATEWAY_SEND_HSTS=true` setzen (typisch hinter TLS-Terminierung).
- **Rate-Limits**: `GatewayRateLimitMiddleware` (öffentlich / sensibel / Admin-Mutation).
- **SSE-Cookie**: `HttpOnly`; `Secure` über `GATEWAY_SSE_COOKIE_SECURE` oder `PRODUCTION`; `SameSite` über `GATEWAY_SSE_COOKIE_SAMESITE` (`none` nur mit `Secure=true`).

Implementierung: `services/api-gateway/src/api_gateway/security_headers.py`, `routes_auth.py`, `config/gateway_settings.py`.

## 4. Dashboard (Next.js)

- **`X-Powered-By` deaktiviert** (`poweredByHeader: false`).
- **Header**: `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, **CSP** mit `connect-src` inkl. konfigurierter API-Origin (`NEXT_PUBLIC_API_BASE_URL` zur Build-Zeit).
- **Log-Scrubbing**: `redactForLog` in `apps/dashboard/src/lib/server-logger.ts` für strukturierte Logs (Schlüssel wie `authorization`, `cookie`, `token`).

**CSRF**: Admin-Mutationen laufen über **serverseitige** Route Handlers mit festem Gateway-Auth-Header — kein Browser-direkter `Authorization`-Header gegen das Gateway für diese Pfade. Bei zukünftigen **Cookie-basierten** Formularen zusätzlich CSRF-Token einführen.

## 5. Reverse-Proxy und TLS (Empfehlung)

Produktion: TLS am **Edge** (z. B. Nginx, Caddy, Cloud-Load-Balancer), Upstream nur im privaten Netz auf `127.0.0.1:8000` / `:3000`.

Beispiel-Konfiguration (anpassen): `infra/reverse-proxy/nginx-edge.conf.example`.

- `proxy_set_header X-Forwarded-Proto https` für korrekte Secure-/Redirect-Logik downstream.
- Optional: `GATEWAY_SEND_HSTS=true` **und** HSTS am Proxy (eine Quelle vermeiden — typisch nur am Proxy).

## 6. Supply Chain und Container

| Kontrolle             | Ort                                                                                                                                                                                                                               |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Lockfiles**         | `pnpm-lock.yaml`, gepinnte Python-Deps in `requirements-dev.txt` / Service-`pyproject.toml`.                                                                                                                                      |
| **CI**                | `pnpm audit --audit-level=high` (blocking) und `python tools/pip_audit_supply_chain_gate.py` (Dev- + Runtime-Requirements, blocking). Zusätzlich `tools/check_production_env_template_security.py` für Prod-/Shadow-ENV-Vorlagen. |
| **API-Gateway-Image** | Non-Root-User `modul_mate` (UID 10001), `python:3.11-slim-bookworm`, Multi-Stage-Build (Wheel/venv im Builder, Runtime ohne Compiler), `HEALTHCHECK` → `GET /health`, `CMD` als `python -m`. |
| **Dashboard-Image**   | Nutzer `modul_mate` (UID 10001), Alpine-Runtime, Multi-Stage-Build, `HEALTHCHECK` → `GET /api/health`.                                                                                     |

Weitere Python-Services: einheitlich Multi-Stage, `modul_mate`, interne Readiness-`HEALTHCHECK` pro Service.

## 7. Security-Smokes (manuell / CI)

1. `curl -sI http://127.0.0.1:8000/health` — erwartet Security-Header (ohne HSTS wenn `GATEWAY_SEND_HSTS=false`).
2. `curl -sI http://127.0.0.1:3000/` — Dashboard-Header inkl. CSP.
3. `docker compose ... config` — prüfen, dass published Ports nur gewünschte Binds zeigen.
4. Nach Deployment: keine `NEXT_PUBLIC_*` Variablen im Browser-Quelltext mit langen Geheimnissen (DevTools → Sources).

## 8. Go/No-Go Checkliste (kurz)

- [ ] `COMPOSE_EDGE_BIND` und `CORS_ALLOW_ORIGINS` für die echte Dashboard-URL gesetzt.
- [ ] `DASHBOARD_GATEWAY_AUTHORIZATION` / Gateway-Secrets nicht in Logs oder Images.
- [ ] TLS und HSTS-Konsistenz (Proxy vs. `GATEWAY_SEND_HSTS`).
- [ ] `GATEWAY_ENFORCE_SENSITIVE_AUTH=true` in Produktion mit JWT/Internal-Key.

Querverweise: `docs/env_profiles.md`, `docs/monitoring_runbook.md`, `docs/dashboard_operator_console.md`.
