# API-Gateway: Auth, Rate-Limits, Audit

## Authentifizierung (erweiterbar)

Kanonische Begriffe fuer Operator-Zustaende und Freigaben: `docs/operator_status_language.md`.

- **JWT (HS256)**: Header `Authorization: Bearer <token>`. Claims: `sub`, Audience `GATEWAY_JWT_AUDIENCE`, Issuer `GATEWAY_JWT_ISSUER`. Rollen aus `gateway_roles` (Liste oder Leerzeichen-getrennt) oder `scope`.
- **Interner Dienst-Key**: Header `X-Gateway-Internal-Key` gleich `GATEWAY_INTERNAL_API_KEY`. Rollen **konfigurierbar** über `GATEWAY_INTERNAL_KEY_ROLES` (komma-separiert). **Leer** = volles Set inkl. `gateway:read`, `admin:read`, `admin:write`, `operator:mutate`, `emergency:mutate` (Backward-Compat fuer Service-zu-Service).
- **Legacy** `X-Admin-Token`: nur wenn sensibles Auth **nicht** erzwungen ist und `GATEWAY_ALLOW_LEGACY_ADMIN_TOKEN=true` (explizit lokal setzen; **Default in Code ist `false`**). Traegt effektiv Admin- + Mutationsrollen.

Sensibles Auth ist aktiv, wenn `PRODUCTION=true` oder `GATEWAY_ENFORCE_SENSITIVE_AUTH=true`. Dann muss mindestens eines von `GATEWAY_JWT_SECRET` / `GATEWAY_INTERNAL_API_KEY` gesetzt sein. Strukturell lassen sich weitere Quellen (OAuth2-Introspection, API-Key-Stores, mTLS-Claims) als zusätzliche Resolver anbinden.

## Rollenmodell (Kurz)

| Rolle                        | Zweck                                                                                                                                          |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `gateway:read`               | Sensible Lesepfade (`/v1/paper`, `/v1/signals`, …)                                                                                             |
| `admin:read` / `admin:write` | Admin-API                                                                                                                                      |
| `operator:mutate`            | `operator_release`, Safety-Latch-Release                                                                                                       |
| `emergency:mutate`           | Kill-Switch, Cancel-All, Emergency-Flatten                                                                                                     |
| `billing:read`               | `/v1/commerce/usage/*`, `/v1/commerce/invoice-preview`, **`/v1/commerce/customer/*`** (Kundenbereich; Tenant aus JWT `tenant_id` oder Default) |
| `billing:admin`              | Meter-Ingest per `X-Commercial-Meter-Secret`; **`/v1/commerce/admin/customer/*`** (Zahlungen, Wallet, Integrations-Hinweise je Tenant)         |

JWT kann optional **`tenant_id`** (String) enthalten. **Mandantenisolation (Prompt 10):** Ist `COMMERCIAL_ENABLED=true` und sensibles Gateway-Auth aktiv, muessen **reine Kunden-JWTs** (nur `billing:read`, ohne `admin:read`/`admin:write`) den Claim **`tenant_id`** setzen — sonst `403 TENANT_ID_REQUIRED`. Admins und Dienst-Keys (nicht-JWT) sind ausgenommen. Ohne diese Kombination gilt weiterhin `COMMERCIAL_DEFAULT_TENANT_ID`, wenn kein `tenant_id` gesetzt ist. Nur `admin:write` darf bei Usage-APIs einen abweichenden `tenant_id`-Query setzen.

Optional **`portal_roles`** und **`platform_role`** (Einzelwert): UI-Kennzeichnung; technische Rechte aus `gateway_roles` / `scope`. Claim-Wert **`super_admin`** (siehe `shared_py.portal_access_contract`) ist nur wirksam, wenn `sub` exakt **`GATEWAY_SUPER_ADMIN_SUBJECT`** entspricht; sonst wird das Portal-Flag serverseitig entfernt (kein Admin-UI-Leak). Leeres `GATEWAY_SUPER_ADMIN_SUBJECT` = kein JWT-Subject erhaelt `super_admin_portal` in der `access_matrix`.

`admin:write` impliziert weiterhin volle Admin-Mutation; fuer Echtgeld-/Safety-Pfade ist zusaetzlich ein **manuelles Aktions-Token** erforderlich, sobald `GATEWAY_MANUAL_ACTION_REQUIRED` effektiv `true` ist (Default: gleichbedeutend mit erzwungenem sensiblem Auth).

## Kundenbereich vs. Admin-Commerce

- **Lesend (Kunde)**: `GET/PATCH /v1/commerce/customer/me`, `GET .../integrations`, `balance`, `payments`, `history`. Antworten enthalten **keine** `usage_ledger.meta_json`, keine Roh-Tenant-IDs (nur maskiert), keine Telegram-Chat-IDs.
- **Schreibend (Betrieb)**: `POST /v1/commerce/admin/customer/payment`, `POST .../wallet/adjust`, `PATCH .../integrations` — erfordern `billing:admin` oder `admin:write`; Aktionen schreiben **customer_portal_audit** und **gateway_request_audit** (ohne Geheimnisse im `detail_json`, Redaction wie ueblich).

Siehe `docs/customer_domain.md`.

## Manuelle Aktions-Tokens (gebunden, kurzlebig, Anti-Replay)

1. **Mint**: `POST /v1/auth/manual-action/mint` mit JSON `{ "route_key": "<...>", "payload": { ... } }`. Erfordert dieselbe Mutations-Berechtigung wie die Zielroute. `payload` muss **identisch** zum spaeteren Request-Body sein (Fingerprint = SHA-256 kanonisches JSON).
2. **Ausfuehrung**: Mutation mit Header `X-Manual-Action-Token: <jwt>` und gleichem Body wie beim Mint.
3. **Technik**: HS256, Audience `gateway-manual-action-v1`, Claims `rk`, `fp`, `jti`, `exp`. Signatur-Secret: `GATEWAY_MANUAL_ACTION_SECRET` oder Fallback `GATEWAY_JWT_SECRET`. Anti-Replay: Redis `SETNX gateway:mia:jti:<jti>` wenn `GATEWAY_MANUAL_ACTION_REDIS_REPLAY_GUARD=true`.
4. **operator_release / Mirror-Freigabe**: `payload` muss `_execution_id` (UUID-String) enthalten; der Ausfuehrungs-Request nutzt dieselbe `execution_id` in der URL und denselben Body-Fingerprint.

Telegram nutzt einen **parallelen** zweistufigen Flow (Pending + Einmalcode in Postgres, Vertrag `telegram-chat-contract-v1`); optional zusaetzlich **TELEGRAM_OPERATOR_ALLOWED_USER_IDS** (RBAC auf Telegram-`user_id`) und **TELEGRAM_OPERATOR_CONFIRM_TOKEN** als drittes Argument bei `/release_confirm` / `/emerg_confirm` (Vergleich mit `secrets.compare_digest`, in Audits nur Fingerprint). Das Gateway nutzt **dieselben inhaltlichen Prinzipien** (kein Freiform-Trade, gebundene `execution_id` bzw. `internal_order_id`, Audit), aber mit **Mint** + `X-Manual-Action-Token` (JWT `jti`) statt Chat-Code. Vollstaendiger Befehls- und Nachrichtentyp-Vertrag: `docs/alert_engine.md` und `shared_py.telegram_chat_contract`.

## Live-Broker-Mutationen ueber das Gateway

- **Lesend**: `/v1/live-broker/*` GET (Proxy auf Postgres) bleibt bei `require_sensitive_auth` / `gateway:read`.
- **Schreibend**: `/v1/live-broker/safety/*` POST und `POST /v1/live-broker/executions/{id}/operator-release` erfordern **Mutationsrollen** + (in Prod/sensiblem Profil) **Manual-Action-Token**. Forward zum live-broker setzt `X-Internal-Service-Key` aus `INTERNAL_API_KEY`, wenn gesetzt.
- **Kein** reines `gateway:read` mehr fuer diese POSTs (frueher fachlich inkonsistent).

## Rate-Limits (Redis)

Kategorien: oeffentlich, sensibel (`/v1/live`, Live-Broker-GETs, …), Admin-Mutationen, **Safety-Mutationen** (eigener Zaehler `GATEWAY_RL_SAFETY_MUTATE_PER_MINUTE` + **Burst** `GATEWAY_RL_SAFETY_BURST_PER_10S` pro Client-Bucket). Konfiguration: `GATEWAY_RL_*`. Ueberschreitungen bei Safety-Pfaden werden **geloggt** (`warning`). Ohne Redis: in Produktion **503**, sonst Durchlass (Fail-open).

## Audit

Admin-, Proxy- und **Manual-Action**-Ereignisse schreiben in `app.gateway_request_audit` (Migration `420_gateway_request_audit.sql`). Safety-/Operator-Routen loggen `manual_action_jti` wenn Token geprueft wurde. Keine Roh-Secrets in `detail_json`.

## Live-SSE

Bei **erzwungenem** sensiblem Auth ist `/v1/live/stream` **nicht** oeffentlich: `Authorization: Bearer …`, `X-Gateway-Internal-Key` oder zuvor ausgestelltes **HttpOnly-Cookie** (`POST /v1/auth/sse-cookie` nach normalem Login). `/v1/live/state` bleibt abgesichert wie bisher. Striktere Limits gelten fuer `/v1/live`; Safety-Mutationen haben eigene Limits (siehe oben).

## Dashboard

Keine Exchange-/Provider-Secrets im Browser. Produktion: `NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY=true` und serverseitig `DASHBOARD_GATEWAY_AUTHORIZATION` (voller Header-Wert, z. B. `Bearer <jwt>`). Fuer Mutationen: JWT mit passenden `gateway_roles` und zweistufig **Mint** + `X-Manual-Action-Token` auf den entsprechenden POSTs — analog zur institutionellen Telegram-Kette (Freigabe -> Ausfuehrung).

**JWT lokal erzeugen** (liest `GATEWAY_JWT_SECRET` / Audience / Issuer aus der ENV-Datei und schreibt optional `DASHBOARD_GATEWAY_AUTHORIZATION`):

```bash
python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file
```

**Next.js BFF** (`apps/dashboard/src/app/api/dashboard/…`): dieselbe Variable fuer alle proxten Gateway-Pfade — u. a. `GET /api/dashboard/system/health` (JSON, inkl. `execution_tier` ueber Operator-Aggregate-Auth), `GET /api/dashboard/health/operator-report` (PDF), Live/Commerce-Proxys. Ohne gesetztes `DASHBOARD_GATEWAY_AUTHORIZATION` liefern diese Routen **503** mit klarer Fehlermeldung (kein stilles Leer-JSON). Diagnose: `GET /api/dashboard/edge-status` inkl. `operatorHealthProbe`, wenn Basis-`/health` des Gateways ok ist.

## Lokale Entwicklung

- `GATEWAY_ALLOW_ANONYMOUS_SAFETY_MUTATIONS=true` (nur wenn **weder** `PRODUCTION` **noch** erzwungenes sensibles Auth): erlaubt Mutationen ohne JWT — bei `GATEWAY_ENFORCE_SENSITIVE_AUTH=true` oder `PRODUCTION=true` **immer aus**, damit Shadow/Prod nicht ueber Umgebungsfehler offen bleiben.
- `GATEWAY_MANUAL_ACTION_REQUIRED=false`: erzwingt kein zweites Token; **Rollen** fuer Safety-POSTs gelten weiterhin.

## Kommerzielle Transparenz (serverseitig)

Siehe `docs/commercial_transparency.md`: Plaene, `usage_ledger`, Metering-Ingest, Budget-/Token-Caps — **ohne** versteckte Multiplikatoren (`platform_markup_factor` fix `1.0` in der DB).
