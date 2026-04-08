# Reverse-Proxy (Single-Host, TLS am Edge)

Generisch (nginx) — **keine** Cloud-Vendor-Annahmen. Der Upstream ist typischerweise `127.0.0.1:8000` (API-Gateway) und `127.0.0.1:3000` (Dashboard), wenn `docker compose` mit `COMPOSE_EDGE_BIND=127.0.0.1` laeuft.

## Pflicht-Header zum API-Gateway

- `X-Forwarded-Proto: https` — damit Cookies/Redirects konsistent bleiben.
- `X-Forwarded-Host` — optional, fuer Logging/Absolute-URLs.

ENV im Gateway: `APP_BASE_URL`, `FRONTEND_URL`, `CORS_ALLOW_ORIGINS` (https-Origins), bei TLS `GATEWAY_SEND_HSTS=true`, `GATEWAY_SSE_COOKIE_SECURE=true`.

## Beispielkonfiguration

Siehe `nginx.single-host.conf` — **Vorlage**: `server_name`, Zertifikatspfade und Upstreams anpassen.

## Readiness

Nach dem Start:

```bash
curl -sS "https://<ihre-api-domain>/v1/deploy/edge-readiness"
curl -sS "https://<ihre-api-domain>/ready"
```

Siehe `docs/operator_urls_and_secrets.md`.
