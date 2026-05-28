# Production-Readiness — ehrlicher Status

Stand: nach Härtungs-Sprint Mai 2026 (Cooldown, Step-Up, Multi-Tenant-Gate).

Dieses Dokument ersetzt Marketing-Aussagen wie „10/10 produktionsreif" durch
eine **prüfbare Matrix**. Jeder Punkt nennt:

- den **aktuellen Zustand** (Grün/Gelb/Rot mit konkretem Befund),
- den **Verifikations-Pfad** (Tests, Skripte, Datei-Pfade),
- die **offenen Punkte**, die vor echtem Geldfluss noch erledigt sein müssen.

Ein einziges Rot in einer der „Tradeflow"-Zeilen ist ein hartes No-Go für
LIVE-Trading mit Kundengeld.

---

## 1. Execution Gate (Echtgeld-Sperre)

| Komponente | Status | Befund |
|---|---|---|
| `shared_py.modul_mate_db_gates.assert_execution_allowed` | 🟢 | Zentraler DB-Gate für LIVE/DEMO. Erzwingt `tenant_modul_mate_gates` + `tenant_contract` mit `admin_review_complete`. |
| Go-Live Cooldown | 🟢 | `live_go_live_at` (Migration 632) + `GO_LIVE_COOLDOWN_SEC` (Default 3600s) blockiert LIVE-Exchange-Orders in Shadow-Phase. |
| `services/live-broker/.../execution/service.py::_assert_db_live_execution_policy` | 🟢 | Defense-in-Depth direkt vor `exchange_client`. Tenant aus Intent-Trace via `gate_tenant_from_intent`. |
| `services/live-broker/.../orders/service.py::_assert_modul_mate_policy_allows_exchange_submit` | 🟢 | Zweiter Defense-in-Depth-Punkt vor REST-Order (Order-Trace). |
| `services/api-gateway/.../deps.py::verify_live_trading_capability` | 🟢 | Gateway-Vorab-Check 403 mit `LIVE_TRADING_NOT_ALLOWED_NO_CONTRACT`, in Production-Profile nicht deaktivierbar. |
| Tests | 🟢 | `test_modul_mate_go_live_cooldown.py`, `test_tenant_gate_context.py`, `test_live_trading_policy.py`, Live-Broker-Gate-Tests. |

**Offene Punkte:**
- Vault-Secrets pro Mandant unter `bitget/{tenant_id}/live` befüllen; Go-Live prüft Vault-Credentials tenant-scoped (nicht globale `BITGET_*` bei `TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT=true`).

## 2. Tenant Isolation (Frontend → Gateway → DB)

| Komponente | Status | Befund |
|---|---|---|
| `apps/dashboard/src/middleware.ts` | 🟢 | Drei Zonen `(public)` / `/portal` / `/console` mit Cookie-JWT-Validierung. |
| BFF-Proxy (`apps/dashboard/src/lib/gateway-bff.ts`) | 🟢 | Portal-JWT priorisiert; kein Regex-Cookie-Parsing. |
| Go-Live BFF-Route | 🟢 | `portal_jwt` Pflicht; Body-Weiterleitung inkl. `step_up_code`. |
| Gateway Dependencies | 🟢 | `get_current_tenant`, Self-Service-Tenant aus JWT. |
| Live-Broker Order-Submit | 🟢 | `tenant_credentials_scope` in `_call_private` / `_query_remote_detail` + Control-Plane. |
| Gateway Safety Forward | 🟢 | Alle Safety-Routen: `effective_tenant_for_live_broker_forward` (JWT oder `COMMERCIAL_DEFAULT_TENANT_ID`). |
| OIDC Login + Callback | 🟢 | `/api/auth/callback`, JWKS-Verifikation, Identity-Sync an Gateway. |
| Vault Tenant-Credentials | 🟢 | `secret_store.py` + `tenant_exchange_credentials.py` (Pfad `bitget/{tenant}/live`). |

**Offene Punkte:**
- IdP in Production konfigurieren (`PORTAL_AUTH_PROVIDER=oidc`, Callback `/api/auth/callback`).

## 3. Mock-Login (Entwicklung)

| Komponente | Status | Befund |
|---|---|---|
| `login/actions.ts` | 🟢 | NODE_ENV-Gate + Opt-In; Min-Secret 16; Audience/Issuer. |
| `login/layout.tsx` | 🟢 | Mock nur Dev/Test; OIDC-Login in Production wenn `PORTAL_AUTH_PROVIDER=oidc`. |
| Token-Lebensdauer | 🟢 | 2h. |

**Offene Punkte:**
- Mock-Login bleibt Dev-only; Production nutzt OIDC.

## 4. Go-Live Workflow

| Komponente | Status | Befund |
|---|---|---|
| `POST /v1/commerce/customer/live-execution/enable` | 🟢 | Preflight + Self-Service-Tenant + Audit. |
| Step-Up (2FA-lite) | 🟢 | `GO_LIVE_REQUIRE_STEP_UP` + TOTP (`GO_LIVE_STEP_UP_TOTP_SECRET`) oder PIN (Dev). `go_live_step_up.py`, UI-Feld im Modal. |
| Bitget API-Key-Ping | 🟢 | `bitget_verify.py` — tenant-scoped Ping via `verify_bitget_api_keys_for_tenant`. |
| E-Mail-Verifikation | 🟢 | `GO_LIVE_REQUIRE_EMAIL_VERIFIED` + `portal_identity_security.email_verified_at`. |
| Go-Live Cooldown / Shadow | 🟢 | `live_go_live_at`, UI-Hinweis `successShadowMsg`. |
| Go-Live Preflight | 🟢 | `GET /live-execution/preflight` — Readiness ohne Mutation (Keys, Vertrag, Guthaben, E-Mail, Account-Status). |
| Frontend + E2E | 🟢 | `TradingPageClient.tsx` zeigt Blocker vor Modal; E2E 6/6 (`live-execution-gate.spec.ts`). |

**Offene Punkte:**
- Vollständige IdP-2FA (WebAuthn/SMS) statt TOTP-ENV — Step-Up ist technische Basis, kein Ersatz für IdP.

## 5. i18n

| Komponente | Status | Befund |
|---|---|---|
| `signal-decision-tokens.ts` | 🟢 | i18n-Token-Schicht; deprecated `signal-decision-center.ts` entfernt. |
| Signal-UI | 🟢 | Kein `mapGermanToI18n`-Hack. |

## 6. Disaster Recovery

| Komponente | Status | Befund |
|---|---|---|
| `tools/dr_postgres_restore_drill.py` | 🟢 | PASS mit RTO/RPO-Messung. |
| Alertmanager / Prometheus | 🟢 | Critical-Route konfiguriert. |

**Offene Punkte:**
- DR-Drill: `PgExecutor`-Strategy statt Docker/Local-Duplikation.
- Echtes Slack/PagerDuty aus Vault.

## 7. CI / Tests

| Suite | Status |
|---|---|
| `pytest tests/unit/api_gateway/test_go_live_step_up.py` | 🟢 |
| `pytest tests/unit/shared_py/test_modul_mate_go_live_cooldown.py` | 🟢 |
| `pnpm exec playwright test e2e/tests/live-execution-gate.spec.ts` | 🟢 6/6 |
| `pnpm check-types` | 🟢 |
| `python tools/production_readiness_audit.py` | 🟢 | Schema `docs/production_10_10/readiness_evidence_schema.json` wiederhergestellt; `--strict` erwartbar rot ohne L4/L5-EV. |
| `pnpm go-live:launch` / `pnpm go-live:launch:strict` | 🟢 | Kombiniert ENV 10/10 + Ops-Preflight + Vault-Tenant-Check (strict) + Readiness-Audit. |
| `pnpm vault:verify:tenant` | 🟢 | `tools/verify_vault_tenant_credentials.py` — KV-Pfad ohne Secret-Leak. |
| `docs/shadow_burn_in_ramp.md` + `verify_shadow_burn_in.py` | 🟡 L2 | Burn-in-Ablauf + DB-Verifier im Repo; echtes L4-Zertifikat extern. |

## 8. Was vor echtem Geldfluss **fehlt**

1. **IdP in Production befüllen** (Issuer, Client, Redirect, JWKS) und Smoke-Login durchführen.
2. **Bitget-Staging-Verifikation** mit echten Keys (tenant-scoped Ping).
3. **Vault aktivieren** (`TENANT_EXCHANGE_CREDENTIALS_FROM_VAULT=true`, Secrets unter `bitget/{tenant_id}/live`).
4. **Ops-Preflight grün:** `python tools/go_live_ops_preflight.py --env-file .env.production --strict-runtime`
5. **Echtes Slack/PagerDuty** aus Vault.
6. **Externes DR-Audit**, Pen-Test, Insurance, Regulatorik.

## 9. Zusammenfassung

Der Stack ist **produktionsreif für Demo/Paper/Shadow** und hat eine **belastbare LIVE-Sicherheitsbasis** (Gates, Cooldown, Step-Up, Tenant-Trace). „10/10 mit echtem Kundengeld" erfordert die externen Blocker unter Punkt 8.
