# 09 — Auth-Kette: Dashboard-BFF, Gateway, Dienst-zu-Dienst

**Pflichtgrundlage:** `docs/chatgpt_handoff/03_ENV_SECRETS_AUTH_MATRIX.md`  
**Stand:** 2026-04-05

---

## 1. Auth-Kette (Kurz)

| Schicht                                       | Header / Mechanismus                     | ENV / Secret                                     | Verwechslungsgefahr                             |
| --------------------------------------------- | ---------------------------------------- | ------------------------------------------------ | ----------------------------------------------- |
| **Browser → Dashboard**                       | Kein Gateway-JWT im Client (BFF)         | `NEXT_PUBLIC_*` nur öffentliche URLs             | Keine Secrets unter `NEXT_PUBLIC_`              |
| **Next.js BFF → Gateway**                     | `Authorization: Bearer <jwt>`            | `DASHBOARD_GATEWAY_AUTHORIZATION`                | Nicht `INTERNAL_API_KEY`                        |
| **Gateway (sensible Pfade)**                  | Bearer JWT oder `X-Gateway-Internal-Key` | `GATEWAY_JWT_SECRET`, `GATEWAY_INTERNAL_API_KEY` | `GATEWAY_INTERNAL_API_KEY` ≠ `INTERNAL_API_KEY` |
| **Gateway → Worker (z. B. llm-orchestrator)** | `X-Internal-Service-Key`                 | `INTERNAL_API_KEY`                               | Nicht `X-Gateway-Internal-Key`                  |

**Code-Referenzen**

- BFF: `apps/dashboard/src/lib/server-env.ts` (`DASHBOARD_GATEWAY_AUTHORIZATION`, `API_GATEWAY_URL`)
- Gateway: `services/api-gateway/src/api_gateway/auth.py` (`resolve_gateway_auth_with_diagnostic`, `require_*`)
- Worker: `shared/python/src/shared_py/service_auth.py` (`INTERNAL_SERVICE_HEADER`, `assert_internal_service_auth`)

---

## 2. Neue / erweiterte Gateway-Fehlercodes (401)

Struktur: `{"detail": {"code", "message", "hint", "required_capability"? }}` (FastAPI).

| Code                               | Bedeutung                                                                    |
| ---------------------------------- | ---------------------------------------------------------------------------- |
| `GATEWAY_AUTH_MISSING`             | Weder gültiges JWT noch passender Gateway-Internal-Key                       |
| `GATEWAY_JWT_EXPIRED`              | JWT abgelaufen                                                               |
| `GATEWAY_JWT_INVALID`              | Signatur / aud / iss falsch                                                  |
| `GATEWAY_JWT_SECRET_MISSING`       | Bearer gesendet, Secret im Gateway leer                                      |
| `GATEWAY_AUTHORIZATION_MALFORMED`  | Header nicht `Bearer …`                                                      |
| `GATEWAY_INTERNAL_KEY_MISMATCH`    | `X-Gateway-Internal-Key` gesendet, Wert ≠ `GATEWAY_INTERNAL_API_KEY`         |
| `GATEWAY_INSUFFICIENT_ROLES`       | Authentifiziert, aber Rollen reichen nicht (u. a. `sensitive_read_ok` Flags) |
| `LIVE_STREAM_AUTH_REQUIRED`        | SSE: JWT/Internal-Key fehlgeschlagen und kein gültiges SSE-Cookie            |
| `OPERATOR_AGGREGATE_AUTH_REQUIRED` | Aggregierte Operator-Pfade wie `/v1/system/health`                           |

**auth_method** bei Gateway-Internal-Key: `gateway_internal_key` (früher irreführend `internal_api_key`).

---

## 3. BFF / edge-status

- `apps/dashboard/src/lib/gateway-bootstrap-probe.ts`: parst Gateway-JSON bei 401/403, füllt `operatorGatewayAuthCode` / `operatorGatewayAuthHint`.
- `apps/dashboard/src/app/api/dashboard/edge-status/route.ts`: liefert `gatewayAuthFailureCode` / `gatewayAuthFailureHint` (keine Secrets).

---

## 4. shared_py.service_auth

- `INTERNAL_AUTH_REQUIRED`: zusätzlich `hint` mit Abgrenzung zu `X-Gateway-Internal-Key`.

---

## 5. Nachweise (Kommandoausgaben)

### 5.1 JWT-Mint

```text
python scripts/mint_dashboard_gateway_jwt.py --env-file .env.local --update-env-file
Aktualisiert: .env.local (DASHBOARD_GATEWAY_AUTHORIZATION)
```

_(Lauf auf Entwicklermaschine; aktualisiert lokale `.env.local`.)_

### 5.2 Pytest (Gateway-Auth, service_auth, LLM-Operator-Routen)

```text
python -m pytest tests/unit/api_gateway/test_gateway_auth.py tests/shared/test_service_auth.py tests/unit/api_gateway/test_routes_llm_operator.py -q
...........................                                              [100%]
27 passed in ~52s
```

### 5.3 edge-status

Lokal nur sinnvoll mit laufendem Dashboard (`pnpm dev` o. ä.):

```bash
# Beispiel (Linux/macOS)
curl -s http://127.0.0.1:3000/api/dashboard/edge-status | jq .
```

**Hinweis:** Auf der ausführenden Umgebung war kein Next-Server auf Port 3000 erreichbar — kein Live-JSON in diesem Lauf.

### 5.4 Typecheck Dashboard

```text
cd apps/dashboard && pnpm exec tsc --noEmit
(exit 0)
```

---

## 6. Offene Punkte

- `[TECHNICAL_DEBT]` Weitere Gateway-Routen mit Rohtext-`detail` (außerhalb `auth.py`) können schrittweise auf dieselbe Struktur migriert werden.
- `[FUTURE]` Einheitliche `detail`-Form auch für 403 außerhalb Commerce (`TENANT_ID_REQUIRED` bleibt).
