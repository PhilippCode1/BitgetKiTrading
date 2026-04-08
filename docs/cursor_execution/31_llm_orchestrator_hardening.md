# 31 — LLM-Orchestrator Hardening (Provider, Health, Fehler, Tests)

**Stand:** 2026-04-05  
**Pflichtgrundlage:** `docs/chatgpt_handoff/06_KI_ORCHESTRATOR_UND_STRATEGIE_SICHTBARKEIT.md` (Landkarte, Fake-Verbot shadow/production, Strecken Operator/Assist/Structured).

---

## 1. Zielbild

| Thema               | Umsetzung                                                                                                                                                                                                                                   |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **OpenAI vs. Fake** | `provider_mode` in `/health`: `fake` \| `openai` \| `openai_key_missing`; Textfeld `provider_separation_note_de`. Fake weiterhin per `LLM_USE_FAKE_PROVIDER` nur ausserhalb `APP_ENV` shadow/production (`config.py` unveraendert im Kern). |
| **Ausfälle**        | Letzter strukturierter Fehler: `last_structured_failure` in Health; HTTP **502** `detail.failure_class` (z. B. `retry_exhausted`, `circuit_open`, `no_provider_configured`).                                                                |
| **Health ehrlich**  | Redis: `redis.ok`, `redis.last_error_class` bei Ping-Fehler; Circuit: `providers_currently_open`; `structured_output` mit Timeout/Retries/Prompt-Cap.                                                                                       |
| **Korrelation**     | `run_structured` loggt `request_id` / `correlation_id` aus Contextvars (Middleware setzt Header wie Gateway).                                                                                                                               |
| **Konfiguration**   | `LLM_TIMEOUT_MS` validiert 1000..600000 ms.                                                                                                                                                                                                 |

---

## 2. Provider- und Umgebungsnachweise

- **Fake:** `LLM_USE_FAKE_PROVIDER=true` + `APP_ENV` ∈ {`local`, `development`, `test`, …} — erlaubt.
- **Verboten:** `APP_ENV` shadow/production + `LLM_USE_FAKE_PROVIDER=true` → `ValidationError` (bestehend, siehe `test_production_resilience.py`).
- **Chat-Fallback:** `LLM_OPENAI_ALLOW_CHAT_FALLBACK=true` in shadow/production verboten (bestehend).
- **Produktion:** `PRODUCTION=true` + kein Fake → `OPENAI_API_KEY` Pflicht (bestehend).

---

## 3. Health-Felder (final)

Zusätzlich zu den bestehenden Feldern liefert `GET /health` u. a.:

| Feld                                     | Bedeutung                                                                      |
| ---------------------------------------- | ------------------------------------------------------------------------------ |
| `app_env`, `production`                  | Laufzeitprofil                                                                 |
| `provider_mode`                          | `fake` / `openai` / `openai_key_missing`                                       |
| `provider_separation_note_de`            | Kurzreferenz OpenAI vs. Fake                                                   |
| `structured_output.llm_timeout_ms`       | Request-Timeout an den Provider                                                |
| `structured_output.llm_max_retries`      | Retry-Versuche                                                                 |
| `structured_output.llm_max_prompt_chars` | Hard-Cap                                                                       |
| `redis.ok`, `redis.last_error_class`     | Ping + Exception-Typ bei Fehler                                                |
| `redis_ok`                               | Abwaertskompatibel (bool)                                                      |
| `circuit.providers_currently_open`       | Offene Circuit-Keys (lesbar)                                                   |
| `last_structured_failure`                | `failure_class`, `message_snippet`, `task_type`, `recorded_at_utc` oder `null` |
| `request_correlation`                    | Erwartete Header `X-Request-ID`, `X-Correlation-ID`                            |

---

## 4. HTTP-Fehlerbild (502)

`detail` bei Provider-Ausfall:

```json
{
  "code": "LLM_UNAVAILABLE",
  "message": "…",
  "failure_class": "retry_exhausted"
}
```

Mögliche `failure_class`-Werte (heuristisch aus letztem Fehlertext):  
`circuit_open`, `schema_validation_exhausted`, `no_provider_configured`, `retry_exhausted`, `provider_failed`, `unknown`.

---

## 5. Geänderte / neue Artefakte

| Datei                                                             | Änderung                                                                      |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `services/llm-orchestrator/src/llm_orchestrator/config.py`        | Validator `LLM_TIMEOUT_MS`                                                    |
| `services/llm-orchestrator/src/llm_orchestrator/retry/circuit.py` | `providers_currently_open` im Snapshot                                        |
| `services/llm-orchestrator/src/llm_orchestrator/service.py`       | Health erweitert, Fehler-Tracking, Trace-IDs in Logs, `_chain`-Fehler erfasst |
| `services/llm-orchestrator/src/llm_orchestrator/api/routes.py`    | `_llm_http_error` mit `failure_class`, Health-Debug-Log                       |
| `tests/llm_orchestrator/test_health_openai_metadata.py`           | Assertions neue Health-Felder                                                 |
| `tests/llm_orchestrator/test_production_resilience.py`            | `failure_class` bei 502; Timeout-Validator-Test                               |
| `docs/cursor_execution/31_llm_orchestrator_hardening.md`          | Dieser Nachweis                                                               |

---

## 6. Testnachweise

**Befehl (Pflicht):**

```bash
python -m pytest tests/llm_orchestrator/test_structured_fake_provider.py -q --tb=no
```

**Weitere Orchestrator-Suite:**

```bash
python -m pytest tests/llm_orchestrator/ -q --tb=no
```

**Ergebnis (lokal, 2026-04-05):** `test_structured_fake_provider.py` — **3 passed**; gesamte `tests/llm_orchestrator/` — **24 passed**.

---

## 7. Health-Nachweis (ohne laufenden Stack: TestClient)

Mit gesetztem `INTERNAL_API_KEY` und Fake-ENV (wie in `test_health_openai_metadata.py`):

- `GET /health` → HTTP 200, JSON enthält `provider_mode`, `circuit.providers_currently_open`, `last_structured_failure: null` nach Start.

**Live-Stack:** `GET http://<orch-host>/health` (ohne Auth) entspricht demselben Handler.

---

## 8. Offene Punkte

- **[FUTURE]** Metriken (Latenz/Cache-Quote) pro `task_type` — in 06 als Observability-Empfehlung genannt, nicht implementiert.
- **[RISK]** `failure_class` ist heuristisch aus `last_error`-String abgeleitet; präzisere Codes erforderten Exception-Typen bis zum HTTP-Layer.
