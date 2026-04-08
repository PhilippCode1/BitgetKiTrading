# Contracts, Determinismus und Replay-Stabilität

## Einheitliche Wahrheit

| Schicht     | Artefakt                                                                                                                         |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Katalog     | `shared/contracts/catalog/event_streams.json` (`envelope_default_schema_version`, `envelope_fingerprint_canon_version`, Streams) |
| JSON Schema | `shared/contracts/schemas/event_envelope.schema.json`                                                                            |
| Python      | `shared_py.eventbus.envelope`, `shared_py.eventbus.canonical`                                                                    |
| TypeScript  | `shared/ts/src/eventEnvelope.ts`, `eventStreams.ts`, `canonicalJson.ts`, `contractVersions.ts`                                   |
| OpenAPI     | `shared/contracts/openapi/api-gateway.openapi.json` (Export: `python scripts/export_openapi.py`)                                 |

Änderungen an Event-Typen oder Streams: zuerst `event_streams.json`, dann Python-`EventType`-Literal, TS-`EVENT_TYPE_TO_STREAM`, Schema-`enum`, Tests.

## Event-Fingerprints

Zwei Modi (gleiche Kanonisierung, unterschiedliche Feldmenge):

- **semantic**: fachlicher Kern für Dedupe und sachliche Replay-Gleichheit — **ohne** `event_id` und **ohne** `ingest_ts_ms` (Wall-Clock).
- **wire**: vollständige Hülle inkl. `event_id` und `ingest_ts_ms` für persistierte Nachrichten.

Implementierung: `envelope_fingerprint_sha256` / `envelopeFingerprintPreimage` + `stable_json_dumps` / `stableJsonStringify`.

Kanon-Version: `envelope_fingerprint_canon_version` im Katalog. Erhöhen bei Änderung der Hash- oder Rundungslogik (Migrationspfad für bestehende Fingerprints).

## Kanonisierung (JSON)

- Alle Objekte: Schlüssel lexikographisch sortiert (rekursiv).
- Separatoren: kompakt `,` und `:` (ohne Leerzeichen).
- UTF-8, `ensure_ascii=False` (Python) / normales `JSON.stringify` (TS) auf bereits kanonisierten Daten.
- **Gleitkomma**: Rundung auf **8 Dezimalstellen**; Werte, die nach Rundung ganzzahlig sind, werden als **Integer** serialisiert. `NaN`/`Inf` sind verboten.

Py/TS-Parität wird durch Golden-Hashes unter `tests/fixtures/contracts/*.sha256` und Tests in `tests/unit/shared_py/test_event_envelope_determinism.py` sowie `apps/dashboard/src/lib/__tests__/contract-envelope-canonical.test.ts` abgesichert.

## Stabilitätsgrad (Gesamtstack)

| Bereich                                     | Grad                 | Anmerkung                                                                  |
| ------------------------------------------- | -------------------- | -------------------------------------------------------------------------- |
| Event-Hülle Schema v1 + Stream-Katalog      | **stabil**           | Versionen im Katalog; CI prüft Konsistenz                                  |
| Fingerprint preimage + SHA-256              | **stabil**           | Bei gleichem Inhalt gleicher Hash; Kanon-Version bei Algorithmus-Änderung  |
| OpenAPI Gateway                             | **stabil**           | `test_openapi_export_sync` vergleicht Export mit committed JSON            |
| Vollständiger byte-identischer Stack-Replay | **nicht garantiert** | Redis, DB, parallele Worker, externe APIs, `event_id`/UUID, `ingest_ts_ms` |

## Bewusste Nicht-Determinismen

- **`event_id`**: UUID (nur im **wire**-Fingerprint).
- **`ingest_ts_ms`**: Erfassungszeit (nur **wire**); für sachliche Gleichheit **semantic** verwenden.
- **Float-Umgebungsdrift**: jenseits der 8-Dezimal-Policy können extrem pathologische Binärwerte in Python/JS divergieren — Fingerprints sind für typische Marktdaten ausgelegt; kritische Werte als Integer/Basis-Punkte modellieren.
- **Nicht-JSON-Natives in Payloads** (z. B. `Decimal`, `datetime`) dürfen in Events nicht vorkommen; nur JSON-taugliche Strukturen.

## CI

- `python tools/check_contracts.py` — Envelope-Fixture, Katalog ↔ `contractVersions.ts`, Katalog ↔ `eventStreams.ts` (inkl. `LIVE_SSE_STREAMS`), Katalog ↔ Schema-`event_type.enum`, OpenAPI-3.x-Grundstruktur.
- Pytest inkl. `test_openapi_export_sync`, `test_event_envelope_determinism`.
- Dashboard-Jest: kanonischer Fingerprint vs. Golden.
