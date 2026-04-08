# Eventbus

## Ziel

Der interne Eventbus entkoppelt Services ueber feste Redis Streams. Jeder
Business-Event wird als `EventEnvelope` publiziert; Ad-hoc-Formate ohne
Envelope sind fuer die fachliche Weitergabe nicht erlaubt.

## Kanonische Stream-Liste

**Quelle:** `shared/contracts/catalog/event_streams.json` — wird von `shared_py.eventbus.envelope` geladen (`EVENT_STREAMS`, `EVENT_TYPE_TO_STREAM`, `LIVE_SSE_STREAMS`). Gateway `routes_events` und `routes_live` importieren dieselben Konstanten (keine zweite Hardcode-Liste).

Enthalten u. a.: `events:market_tick`, `events:candle_close`, `events:funding_update`, `events:structure_updated`, `events:drawing_updated`, `events:signal_created`, `events:trade_*`, `events:funding_booked`, `events:risk_alert`, `events:learning_feedback`, `events:strategy_registry_updated`, `events:news_*`, `events:llm_failed`, `events:system_alert`, `events:dlq`.

**Live-SSE (Teilmenge):** `live_sse_streams` im Katalog — nur diese Streams werden unter `/v1/live/stream` dem UI zugefuehrt.

## Envelope-Felder

- `schema_version`: muss mit `envelope_default_schema_version` im Katalog uebereinstimmen (aktuell `1.0`); JSON-Schema: `shared/contracts/schemas/event_envelope.schema.json`
- Determinismus / Fingerprints (`semantic` vs. `wire`): `docs/contracts_determinism.md`, `shared_py.eventbus.canonical`, `shared/ts/src/canonicalJson.ts`
- `event_id`: eindeutige UUID je Event
- `event_type`: fachlicher Eventtyp
- `symbol`: Marktbezug; wird aus Instrument oder Payload abgeleitet, kein impliziter BTCUSDT-Default
- `timeframe`: optional, z. B. `1m`
- `exchange_ts_ms`: Exchange-Zeitstempel, falls vorhanden
- `ingest_ts_ms`: lokaler Ingest-Zeitstempel
- `dedupe_key`: optionaler Idempotenz-Key
- `payload`: fachliche Nutzdaten
- `trace`: technische Herkunft und Debug-Kontext

## RedisStreamBus

Die Shared-Library liegt unter `shared/python/src/shared_py/eventbus/` und
stellt bereit:

- `EventEnvelope` als Pydantic-Contract
- `RedisStreamBus.publish()` fuer valide Envelope-Events
- `RedisStreamBus.ensure_group()`, `consume()` und `ack()` fuer Consumer-Groups
- `RedisStreamBus.publish_dlq()` fuer Fehlerfaelle nach `events:dlq`

Optionales Dedupe nutzt Redis-Keys im Schema
`dedupe:<stream>:<dedupe_key>` mit TTL. Dadurch werden z. B. doppelte
`candle_close`-Publishes nach Reconnects abgefangen.

## DLQ-Semantik

- Parsing- und Validierungsfehler duerfen nicht still verschwinden.
- Fehlerhafte oder nicht validierbare Messages werden nach `events:dlq`
  kopiert.
- Das DLQ-Payload enthaelt das Original-Event bzw. die Rohdaten plus
  `error.stage` und `error.error`.
- `event_type="dlq"` ist als technischer Kontrolltyp fuer den DLQ-Stream
  reserviert.

## API-Debug-Endpunkte

- `GET /events/health`: Redis-Ping plus `XLEN` fuer alle Pflicht-Streams
- `GET /events/tail?stream=events:candle_close&count=10`: letzte N Events eines
  Streams
- `GET /events/dlq?count=10`: Tail fuer `events:dlq`

## Tools

- `python tools/publish_test_event.py`: publiziert ein Test-`candle_close` und
  ein Test-`market_tick`
- `python tools/read_stream_tail.py events:candle_close --count 5`: liest die
  letzten Events eines Streams

## Sicherheit

- `.env.local` bleibt lokal und darf nicht committed werden.
- `dedupe_key` darf keine Secrets, API-Keys oder Tokens enthalten.
- In Produktion sollte Redis nur mit Auth und TLS exponiert werden.
