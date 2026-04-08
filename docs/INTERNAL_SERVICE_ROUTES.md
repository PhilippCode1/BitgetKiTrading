# Interne Service-Routen (`INTERNAL_API_KEY` / `X-Internal-Service-Key`)

Dienste mit produktionskritischen Direktpfaden nutzen [`shared_py.service_auth`](../shared/python/src/shared_py/service_auth.py):

| HTTP    | Situation                                                   | Code (detail.code)                               |
| ------- | ----------------------------------------------------------- | ------------------------------------------------ |
| 401     | `INTERNAL_API_KEY` gesetzt, Header fehlt/falsch             | `INTERNAL_AUTH_REQUIRED`                         |
| 503     | `PRODUCTION=true`, aber `INTERNAL_API_KEY` leer (Misconfig) | `INTERNAL_AUTH_MISCONFIGURED`                    |
| (lokal) | Key nicht gesetzt, `PRODUCTION=false`                       | Interner Check wird umgangen (`anonymous_local`) |

Öffentliche Liveness bleibt ohne internen Key: typisch `GET /health`, `GET /ready`.

## Inventar (Services)

| Service              | Geschützte Präfixe / Pfade                                              | Mechanismus                                                                     |
| -------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ----------------------------------- |
| **llm-orchestrator** | `POST /llm/*` (alle LLM-Endpunkte)                                      | `build_internal_service_dependency`                                             |
| **live-broker**      | `GET                                                                    | POST /live-broker/\*` (Ops-Router)                                              | `build_internal_service_dependency` |
| **monitor-engine**   | `GET /ops/alerts/open`, `POST /ops/alerts/.../ack`, `POST /ops/run-now` | `assert_internal_service_auth`                                                  |
| **alert-engine**     | `POST /admin/*`                                                         | `assert_internal_service_auth` in `_require_admin` (zusätzlich `X-Admin-Token`) |

## Repo prüfen (Grep)

Aus dem Repository-Root:

```bash
rg "assert_internal_service_auth|build_internal_service_dependency" services shared/python/src/shared_py/service_auth.py -g "*.py"
```

Erwartung: Treffer nur in `shared_py/service_auth.py` und in den oben genannten Service-Routern (plus Tests).

## Tests

- Unit: `tests/shared/test_service_auth.py` (401 / 503 / lokaler Bypass).
- HTTP-Skizze: `tests/unit/live_broker/test_ops_internal_auth_http.py`, `tests/llm_orchestrator/test_internal_header_http.py`.

Siehe auch [`docs/SECRETS_MATRIX.md`](SECRETS_MATRIX.md).
