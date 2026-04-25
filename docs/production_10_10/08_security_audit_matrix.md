# 08 - Security Audit Matrix (Auth, RBAC, OWASP)

Ziel: negative Security-Checks als wiederholbare Evidence (L3), ohne Fake-PASS bei fehlender Laufzeitumgebung.

## Security-Matrix

| Kategorie | Kernfrage | Repo-Evidence (automated) | Status |
| --- | --- | --- | --- |
| AuthN | Werden fehlende/ungueltige Credentials abgewiesen? | `tests/unit/api_gateway/test_security_audit_suite.py`, `tests/unit/api_gateway/test_gateway_auth.py` | automated |
| AuthZ / RBAC | Trennen Rollen Kunde/Operator/Admin/S2S korrekt? | `test_security_audit_suite.py` (Customer->Admin 403, falsche Scope fuer Mutation 403), `test_gateway_auth.py` | automated |
| Tenant Isolation | Wird `tenant_id` fuer Customer-Commerce bei sensibler Auth erzwungen? | `tests/unit/api_gateway/test_gateway_auth.py` (`TENANT_ID_REQUIRED`) | automated |
| Rate Limits | Greifen Klassifizierung + 429 fuer Ueberlast? | `tests/unit/api_gateway/test_gateway_auth.py` (Rate-Limit-Mock), `test_rate_limit_path_classification.py` | automated |
| Debug Routes | Sind Debug-/Replay-Routen in Production-Settings verboten? | `tests/unit/config/test_base_service_settings.py` | automated |
| Secret Leakage | Leaken Fehlerantworten keine Secrets? | `test_security_audit_suite.py` (401/403 ohne Secret-Strings), `tools/verify_production_secret_sources.py` | automated |
| CSRF / Cookie / Browser Security | SSE/Cookie-Auth und Header-Guards korrekt? | `test_gateway_auth.py`, `test_gateway_security_hardening.py`, `apps/dashboard/public-env-allowlist.cjs` | automated + manual |
| Admin Mutation Safety | Brauchen sensitive Mutationen Rollen + Manual-Action-Token? | `test_security_audit_suite.py`, `test_manual_action.py`, `api_gateway/mutation_deps.py` | automated |
| Internal Service Boundary | Werden `X-Gateway-Internal-Key` und `X-Internal-Service-Key` nicht verwechselt? | `test_gateway_auth.py`, `test_security_audit_suite.py`, `docs/api_gateway_security.md` | automated |

## OWASP-Checkliste (Kurz)

| OWASP-Bereich | Kontrollpunkt | Status |
| --- | --- | --- |
| A01 Broken Access Control | Customer-JWT darf keine `/v1/admin/*` Route nutzen | automated |
| A01 Broken Access Control | Falsche Mutation-Rolle (`billing:read`) wird auf Operator-Mutation geblockt | automated |
| A02 Cryptographic Failures | Keine Secret-Werte in Fehlerantworten/Reports | automated |
| A05 Security Misconfiguration | Prod verbietet Debug-Routen/Fake-Provider/Legacy-Bypass-Pfade | automated |
| A05 Security Misconfiguration | Runtime-Header/CSP/HSTS/SameSite in echter Edge-Umgebung pruefen | manual |
| A07 Identification and Authentication Failures | JWT-Validierung, Expiry, malformed Bearer und missing auth geben 401/403 | automated |
| A08 Software and Data Integrity Failures | Manual-Action-Token fuer kritische Mutationen erzwungen | automated |
| A10 SSRF | Upstream-Allowlist/egress-policy gegen interne/externe Zielmanipulation | manual |
| A09 Security Logging & Monitoring Failures | Audit-Logs + SIEM/Alert-Korrelation extern pruefen | external |
| Penetration Test | Externer Pentest/Threat-Review inkl. Bericht/SHA/Owner-Signoff | external |

## Smoke-Check (laufendes Gateway erforderlich)

- Hilfe: `python tools/security_audit_smoke.py --help`
- Lokal/Staging: `python tools/security_audit_smoke.py --base-url http://127.0.0.1:8000 --strict --report-md /tmp/security_smoke.md`
- Ohne erreichbares Gateway muss das Ergebnis `BLOCKED_EXTERNAL` sein (kein PASS).
