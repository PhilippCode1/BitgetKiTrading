# Secret Surface Inventory

- generated_at: `2026-04-26T08:14:14.660238+00:00`
- scanned_files: `9471`
- critical: `10`
- high: `80`
- medium: `14`
- env_files_not_ignored: `0`

## Findings (redacted)

| file | line | severity | rule | redacted_snippet |
| --- | ---: | --- | --- | --- |
| `.env.demo` | 29 | high | `bitget_secret` | `******_***_***=******_**_**_******_*****` |
| `.env.demo` | 30 | high | `bitget_secret` | `******_***_******=******_**_**_******_*****` |
| `.env.demo` | 31 | high | `bitget_secret` | `******_***_**********=******_**_**_******_*****` |
| `.env.demo` | 32 | high | `bitget_secret` | `******_****_***_***=******_**_**_******_*****` |
| `.env.demo` | 33 | high | `bitget_secret` | `******_****_***_******=******_**_**_******_*****` |
| `.env.demo` | 34 | high | `bitget_secret` | `******_****_***_**********=******_**_**_******_*****` |
| `.env.demo.example` | 29 | high | `bitget_secret` | `******_***_***=******_**_**_******_*****` |
| `.env.demo.example` | 30 | high | `bitget_secret` | `******_***_******=******_**_**_******_*****` |
| `.env.demo.example` | 31 | high | `bitget_secret` | `******_***_**********=******_**_**_******_*****` |
| `.env.demo.example` | 32 | high | `bitget_secret` | `******_****_***_***=******_**_**_******_*****` |
| `.env.demo.example` | 33 | high | `bitget_secret` | `******_****_***_******=******_**_**_******_*****` |
| `.env.demo.example` | 34 | high | `bitget_secret` | `******_****_***_**********=******_**_**_******_*****` |
| `.env.example` | 177 | high | `internal_api_key_assignment` | `********_***_***=****_***_***_****` |
| `.env.example` | 179 | high | `secret_key_assignment` | `******_***=****_***_***_****` |
| `.env.example` | 180 | high | `jwt_secret_assignment` | `***_******=****_***_***_****` |
| `.env.example` | 630 | high | `bitget_secret` | `******_***_***=****_***_***_****` |
| `.env.example` | 631 | high | `bitget_secret` | `******_***_******=****_***_***_****` |
| `.env.example` | 632 | high | `bitget_secret` | `******_***_**********=****_***_***_****` |
| `.env.example` | 639 | high | `bitget_secret` | `******_****_***_***=****_***_***_****` |
| `.env.example` | 640 | high | `bitget_secret` | `******_****_***_******=****_***_***_****` |
| `.env.example` | 641 | high | `bitget_secret` | `******_****_***_**********=****_***_***_****` |
| `.env.local` | 93 | high | `internal_api_key_assignment` | `********_***_***=******************************` |
| `.env.local` | 95 | high | `secret_key_assignment` | `******_***=*****************************` |
| `.env.local` | 96 | high | `jwt_secret_assignment` | `***_******=******************************` |
| `.env.local` | 197 | critical | `openai_key` | `******_***_***=**-****--************************************************************************...` |
| `.env.local` | 245 | high | `bitget_secret` | `******_****_***_***=**_********************************` |
| `.env.local` | 246 | high | `bitget_secret` | `******_****_***_******=****************************************************************` |
| `.env.local` | 247 | high | `bitget_secret` | `******_****_***_**********=******************` |
| `.env.local.backup` | 99 | high | `internal_api_key_assignment` | `********_***_***=*************************************************` |
| `.env.local.backup` | 101 | high | `secret_key_assignment` | `******_***=************************************************` |
| `.env.local.backup` | 102 | high | `jwt_secret_assignment` | `***_******=************************************************` |
| `.env.local.backup` | 198 | critical | `openai_key` | `******_***_***=**-****-****-*************************************************************-******...` |
| `.env.local.backup` | 237 | high | `bitget_secret` | `******_***_***=**_********************************` |
| `.env.local.backup` | 238 | high | `bitget_secret` | `******_***_******=****************************************************************` |
| `.env.local.backup` | 239 | high | `bitget_secret` | `******_***_**********="***********"` |
| `.env.local.backup` | 240 | high | `bitget_secret` | `******_****_***_***=**_********************************` |
| `.env.local.backup` | 241 | high | `bitget_secret` | `******_****_***_******=****************************************************************` |
| `.env.local.backup` | 242 | high | `bitget_secret` | `******_****_***_**********="***********"` |
| `.env.local.example` | 127 | high | `internal_api_key_assignment` | `********_***_***=*******_****_********_***_***_******_______` |
| `.env.local.example` | 129 | high | `secret_key_assignment` | `******_***=*******_****_*****_******_***_**_*****_***______` |
| `.env.local.example` | 130 | high | `jwt_secret_assignment` | `***_******=*******_****_***_******_***_**_*****_*******___` |
| `.env.production` | 142 | high | `internal_api_key_assignment` | `********_***_***=******************************************************` |
| `.env.production` | 144 | high | `secret_key_assignment` | `******_***=****************************************************_***********` |
| `.env.production` | 145 | high | `jwt_secret_assignment` | `***_******=_**********************************************_**************_*` |
| `.env.production` | 261 | critical | `openai_key` | `******_***_***=**-****-****-*************************************************************-******...` |
| `.env.production` | 305 | high | `bitget_secret` | `******_***_***=**_********************************` |
| `.env.production` | 306 | high | `bitget_secret` | `******_***_******=****************************************************************` |
| `.env.production` | 307 | high | `bitget_secret` | `******_***_**********=***********` |
| `.env.production.backup` | 142 | high | `internal_api_key_assignment` | `********_***_***=******************************************************` |
| `.env.production.backup` | 144 | high | `secret_key_assignment` | `******_***=****************************************************_***********` |
| `.env.production.backup` | 145 | high | `jwt_secret_assignment` | `***_******=_**********************************************_**************_*` |
| `.env.production.backup` | 261 | critical | `openai_key` | `******_***_***=**-****-****-*************************************************************-******...` |
| `.env.production.backup` | 304 | high | `bitget_secret` | `******_***_***=**_********************************` |
| `.env.production.backup` | 305 | high | `bitget_secret` | `******_***_******=****************************************************************` |
| `.env.production.backup` | 306 | high | `bitget_secret` | `******_***_**********=***********` |
| `.env.production.example` | 121 | high | `internal_api_key_assignment` | `********_***_***=****_***_***_****` |
| `.env.production.example` | 123 | high | `secret_key_assignment` | `******_***=****_***_***_****` |
| `.env.production.example` | 124 | high | `jwt_secret_assignment` | `***_******=****_***_***_****` |
| `.env.production.example` | 311 | high | `bitget_secret` | `******_***_***=****_***_***_****` |
| `.env.production.example` | 312 | high | `bitget_secret` | `******_***_******=****_***_***_****` |
| `.env.production.example` | 313 | high | `bitget_secret` | `******_***_**********=****_***_***_****` |
| `.env.shadow.example` | 119 | high | `internal_api_key_assignment` | `********_***_***=<********>` |
| `.env.shadow.example` | 121 | high | `secret_key_assignment` | `******_***=<********>` |
| `.env.shadow.example` | 122 | high | `jwt_secret_assignment` | `***_******=<********>` |
| `.env.shadow.example` | 289 | high | `bitget_secret` | `******_***_***=<***_**>` |
| `.env.shadow.example` | 290 | high | `bitget_secret` | `******_***_******=<***_**>` |
| `.env.shadow.example` | 291 | high | `bitget_secret` | `******_***_**********=<***_**>` |
| `.env.staging.example` | 69 | high | `internal_api_key_assignment` | `********_***_***=<***_**>` |
| `.env.staging.example` | 72 | high | `secret_key_assignment` | `******_***=<***_**>` |
| `.env.staging.example` | 73 | high | `jwt_secret_assignment` | `***_******=<***_**>` |
| `.env.staging.example` | 105 | high | `bitget_secret` | `******_***_***=<***_**>` |
| `.env.staging.example` | 106 | high | `bitget_secret` | `******_***_******=<***_**>` |
| `.env.staging.example` | 107 | high | `bitget_secret` | `******_***_**********=<***_**>` |
| `.env.test.example` | 127 | high | `internal_api_key_assignment` | `********_***_***=<***_**>` |
| `apps/dashboard/src/lib/operator-jwt.ts` | 106 | medium | `token_assignment` | `***** ***** = ***********(***********);` |
| `docs/production_10_10/env_and_secrets_hardening.md` | 125 | critical | `next_public_secret_name` | `****_******_******_***_***=...` |
| `scripts/admin_gateway_security_report.py` | 238 | critical | `next_public_secret_name` | `******_******_******** = ********_*********_******_******_***("****_******_*****_*****=*******-*...` |
| `scripts/admin_gateway_security_report.py` | 249 | high | `bearer_token` | `******** = ******_****_*****("*************: ****** *********-***** ******=*****")` |
| `scripts/mint_dashboard_gateway_jwt.py` | 80 | medium | `token_assignment` | `***** = ****_*****(***, ***_****=****.***_****)` |
| `services/api-gateway/src/api_gateway/auth.py` | 207 | medium | `token_assignment` | `***** = *****[*].*****()` |
| `services/api-gateway/src/api_gateway/auth.py` | 399 | medium | `token_assignment` | `***** = (*_*****_***** ** "").*****()` |
| `services/learning-engine/src/learning_engine/self_healing/code_fix_agent.py` | 179 | medium | `token_assignment` | `*"[***** ***] ********_**={********.********_**} *****={********.*****_*****}\*"` |
| `shared/python/src/shared_py/customer_telegram_repo.py` | 31 | medium | `token_assignment` | `***** = *******.*****_*******(**)` |
| `shared/python/src/shared_py/customer_telegram_repo.py` | 103 | medium | `token_assignment` | `***** = ***[*:].*****()` |
| `tests/integration/conftest.py` | 74 | medium | `token_assignment` | `***** = ***********_******_*****(` |
| `tests/integration/test_http_stack_integration.py` | 304 | medium | `token_assignment` | `***** = ***.******(*******, ******, *********="*****")` |
| `tests/integration/test_http_stack_recovery.py` | 179 | medium | `token_assignment` | `***** = ***.******(` |
| `tests/integration/test_http_stack_recovery.py` | 235 | medium | `token_assignment` | `***** = ***.******(` |
| `tests/security/test_private_credential_safety.py` | 41 | high | `passphrase_assignment` | `****** "*******" *** ** ******_*********_****("**********=*******")` |
| `tests/security/test_private_credential_safety.py` | 139 | high | `bitget_secret` | `"******_***_***=**_******_*****\*******_***_******=****_******\*******_***_**********=****_****\...` |
| `tests/security/test_single_admin_access_contracts.py` | 65 | critical | `next_public_secret_name` | `****** ********_*********_******_******_***("****_******_*****_*****=***") ** ****` |
| `tests/security/test_single_admin_access_contracts.py` | 131 | critical | `next_public_secret_name` | `_*****(**** / ".***.**********.*******", "****_******_****_*****=***\********_*****_******_*****...` |
| `tests/unit/test_secret_leak_guard.py` | 16 | high | `bitget_secret` | `* = "******_***_******=***_*******_****_*****_*****"` |
| `tests/unit/api_gateway/test_security_audit_suite.py` | 141 | medium | `token_assignment` | `***** = _***_*****(` |
| `tests/unit/api_gateway/test_security_audit_suite.py` | 159 | medium | `token_assignment` | `***** = _***_*****(******=******, *****=["*******:****"], ****="*****")` |
| `tests/unit/api_gateway/test_security_audit_suite.py` | 175 | medium | `token_assignment` | `***** = _***_*****(******=******, *****=["*****:*****"], ****="*****")` |
| `tests/unit/config/test_base_service_settings.py` | 174 | high | `jwt_secret_assignment` | `_***_**********_***(***********, ***_******="**_****")` |
| `tests/unit/tools/test_check_production_env_template_security.py` | 94 | critical | `next_public_secret_name` | `***.*****_****("****_******_******_***_***=***********\*", ********="***-*")` |
| `tests/unit/tools/test_verify_production_secret_sources.py` | 72 | high | `jwt_secret_assignment` | `"***_******=****_***_***_****\********_***_******=*******************************\*"` |
| `tests/unit/tools/test_verify_production_secret_sources.py` | 90 | critical | `next_public_secret_name` | `"****_******_***_******=" + "**-****-" + "******-*****-**-******\*"` |
| `tests/unit/tools/test_verify_production_secret_sources.py` | 109 | high | `jwt_secret_assignment` | `*"***_******={******_*****}\*****_******_***_****_***=*****://***.****.****\*",` |
| `tools/fixtures/env_production_loopback_smoke.env` | 14 | high | `jwt_secret_assignment` | `***_******=*****_***_******_*******_**_**********_` |
| `tools/fixtures/env_production_loopback_smoke.env` | 15 | high | `secret_key_assignment` | `******_***=****_******_***_*******_**_**********` |
| `tools/fixtures/env_production_loopback_smoke.env` | 18 | high | `internal_api_key_assignment` | `********_***_***=****_********_***_***_***_**_*****_*` |
