# Events und Contracts erweitern (ohne Drift)

## 1. Neuen Event-Typ / Stream einfuehren

1. **`shared/contracts/catalog/event_streams.json`**
   - Eintrag unter `streams` mit `event_type` und `stream` (`events:…`).
   - Bei Bedarf `live_sse_streams` erweitern (nur wenn das Dashboard den Stream live sehen soll).

2. **`shared/python/src/shared_py/eventbus/envelope.py`**
   - `EventType` Literal um den neuen String ergaenzen (muss exakt zum Katalog passen; beim Import prueft der Code die Gleichheit).

3. **`shared/contracts/schemas/event_envelope.schema.json`**
   - `properties.event_type.enum` um den gleichen String ergaenzen.

4. **Optional: Payload-Schema** unter `shared/contracts/schemas/payload_<event_type>.schema.json` und Tests in `tests/unit/shared_py/test_event_contracts.py` ergaenzen.

5. **`shared/ts/src/eventStreams.ts`**
   - `EVENT_TYPE_TO_STREAM` und ggf. `LIVE_SSE_STREAMS` spiegeln (Kommentar: Sync mit JSON).

6. **Producer/Consumer** in den Services anbinden; Publish nur ueber `RedisStreamBus.publish` mit passendem `EventEnvelope`.

7. **`python scripts/export_openapi.py`** ausfuehren, falls neue oeffentliche Gateway-Routen hinzukamen.

8. **`pytest tests/unit/shared_py/test_event_contracts.py`** — prueft Katalog ↔ Literal ↔ Schema-Enum.

## 2. Neue Gateway-Route

- FastAPI-Modelle bevorzugt mit Pydantic definieren; nach Aenderungen OpenAPI exportieren (siehe oben).
- Dashboard-Typen: entweder aus `shared/ts` importieren (`EventEnvelopeV1`, `EventBusEventType`) oder manuell an OpenAPI anlehnen.

## 3. Bekannte Altlasten (Freeze-Matrix)

- **Replay/Determinismus:** `ingest_ts_ms` und `event_id` sind zur Laufzeit nicht replay-stabil — siehe `docs/REPO_FREEZE_GAP_MATRIX.md` / Prompt 06; das ist kein Stream-Namens-Drift, aber Envelope-Semantik.
- Aeltere Roh-Streams ausserhalb von `events:*` (z. B. `stream:market:raw`) sind **kein** Eventbus-Vertrag und stehen nicht im Katalog.

## 4. Validierung

```bash
pytest tests/unit/shared_py/test_event_contracts.py tests/unit/shared_py/test_event_envelope.py -q
python tools/check_schema.py --schema shared/contracts/schemas/event_envelope.schema.json --json_file tests/fixtures/contracts/envelope_candle_close_ok.json
python tools/check_contracts.py
python scripts/export_openapi.py
```

`tools/check_contracts.py` ist **CI-blockierend** und prueft u. a. Paritaet `event_streams.json` ↔ `shared/ts/src/eventStreams.ts` (inkl. Live-SSE-Liste) sowie `event_type`-Enum im Envelope-Schema.

Siehe auch: `shared/contracts/README.md`, `docs/eventbus.md`.
