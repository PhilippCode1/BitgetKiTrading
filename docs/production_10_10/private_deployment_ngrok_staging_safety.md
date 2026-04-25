# Private Deployment, ngrok, Staging und oeffentlicher Zugriff

## Ziel

Die Anwendung bleibt private Single-Owner-Software fuer Philipp. Oeffentliche
Preview-URLs (z. B. ngrok) duerfen nie Sicherheitsregeln aufweichen:
fail-closed, keine Secret-Leaks, kein automatisches Live-Trading.

## Runtime-Profile

| Profil | erlaubte URLs | Auth-Anforderung | Debug | Fake Provider | LIVE_TRADE_ENABLE | Bitget Write | ngrok | Main-Console-Sicherheitsmodus |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `local_private` | localhost/127.0.0.1 | optional lokal, empfohlen serverseitig | ja (lokal) | ja | nein | nein | nein | lokale Entwicklung, Live blockiert |
| `local_ngrok_preview` | ngrok-URL fuer Dashboard/API | verpflichtend | nein | optional, aber klar markiert | nein (Blocker bei true) | nein | ja | ngrok-preview mit Auth und blockiertem Live-Write |
| `shadow_private` | private interne URL | verpflichtend | nein | nein | nein | nein | nein | Shadow aktiv, echte Write-Aktionen blockiert |
| `staging_private` | private staging-domain (https) | verpflichtend | nein | nein | nein (default) | nein | nur mit expliziter Gate-Policy | staging-like, produktionsnahe Sicherheitsregeln |
| `production_private` | private production-domain (https) | verpflichtend | nein | nein | nur nach allen Gates | nur nach allen Gates | nein | production private, fail-closed und server-only Auth |

## Harte ngrok-/Preview-Regeln

1. ngrok/Public Preview ohne Auth ist FAIL.
2. ngrok/Public Preview mit `LIVE_TRADE_ENABLE=true` ist FAIL.
3. Debug-Routen sind im Preview nicht offen.
4. Interne Service-Ports werden nicht via ngrok exposed.
5. CORS wildcard (`*`) fuer sensitive Profile ist FAIL.
6. Production private braucht HTTPS (plus HSTS via Gateway/Reverse-Proxy).
7. localhost/127.0.0.1 in sensitiven Public-URLs ist Blocker.
8. Keine Secrets in Reports.

## Script: private_deployment_preflight

`scripts/private_deployment_preflight.py` unterstuetzt:

- `--dry-run`
- `--env-file .env.local --mode local_ngrok_preview`
- `--env-file .env.production --mode production_private`
- `--output-md reports/private_deployment_preflight.md`

Der Script macht keine Netzwerkaufrufe und keine Order-Aktionen.

## Main-Console-Hinweis

Die Main Console zeigt einen Runtime-/Sicherheitsmodus auf der Broker-Seite:

- `ngrok_preview` wird als Preview mit blockiertem Live-Write markiert.
- `production_private` wird als private Produktionslaufzeit mit server-only Auth
  und fail-closed Live-Gates markiert.

## Externe Schritte (TLS/Auth)

1. Reverse-Proxy/TLS (HTTPS + HSTS) fuer Produktionsdomain.
2. Strikte Auth fuer BFF/Gateway (`DASHBOARD_GATEWAY_AUTHORIZATION` etc.).
3. Keine Exposition interner Ports nach außen.
4. Externer Pen-Test/Smoke fuer Preview-URL (401/403, keine Secrets, keine Debug-Routen).
