# contracts

Grenzen zwischen Services, Gateway und Frontend.

| Pfad                                 | Rolle                                                                                                                                   |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `catalog/event_streams.json`         | **Kanonisch:** `event_type` ↔ Redis-Stream, `envelope_default_schema_version`, `envelope_fingerprint_canon_version`, Live-SSE-Teilmenge |
| `schemas/event_envelope.schema.json` | JSON-Schema fuer `EventEnvelope` (Draft 2020-12)                                                                                        |
| `schemas/payload_*.schema.json`      | Kernfelder kritischer Payloads (`candle_close`, `signal_created`, Trade-Lifecycle)                                                      |
| `schemas/*.schema.json` (bestehend)  | Drawing, News, Signal-Erklaerung (LLM/FE)                                                                                               |
| `openapi/api-gateway.openapi.json`   | Export der Gateway-OpenAPI (`python scripts/export_openapi.py`)                                                                         |

CI-Schnellcheck (ohne Pytest): `python tools/check_contracts.py` — Katalog ↔ `eventStreams.ts` (inkl. `LIVE_SSE_STREAMS`), Katalog ↔ Schema-`event_type.enum`, `contractVersions.ts`, Envelope-Fixture vs. Schema, OpenAPI-3.x-Grundstruktur.

Erweiterungsprozess: **`docs/contracts_extension.md`** — Determinismus: **`docs/contracts_determinism.md`**
