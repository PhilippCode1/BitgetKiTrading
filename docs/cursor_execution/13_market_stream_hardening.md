# Market-Stream Härtung (Ingest, Health, Provider-Sichtbarkeit)

**Ziel:** `market-stream` soll **echte Bitget-/Konfigurationsprobleme** über Health und Eventbus sichtbar machen, **typische Netzwerkstörungen** aber mit Reconnect, Backoff-Jitter und **429-Retries** abfedern. Anbindung bleibt **explizit über `BITGET_SYMBOL` und Instrument-Katalog** — kein stillschweigendes BTC-only.

**Referenz:** `docs/chatgpt_handoff/05_DATENFLUSS_BITGET_CHARTS_UND_PIPELINE.md`, `08_FEHLER_ALERTS_UND_ROOT_CAUSE_DOSSIER.md`.

---

## 1. Verhalten (kurz)

| Bereich                             | Änderung                                                                                                                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **WebSocket**                       | Reconnect-Backoff mit **Jitter** (1,0–1,25×); `last_reconnect_at_ms` + `reconnect_count`; Bitget-`error`-Frames → **protocol** in `provider_surface`.  |
| **REST Gap-Fill**                   | Bis zu **N 429-Retries** mit `Retry-After` oder exponentiellem Backoff (cap 30 s); API-`code`≠`00000` → **protocol**; Transport → **transport**.       |
| **Kerzen-REST (Initial/Reconnect)** | Gleiches **429-Retry**-Muster wie Gap-Fill; Fehler klassifiziert (ValueError → protocol, HTTPStatusError → protocol, sonst transport).                 |
| **Ticker-REST**                     | HTTP-/API-Fehler → `provider_surface.protocol`.                                                                                                        |
| **Persistenz Kerzen**               | Nach erfolgreichem `upsert`: `last_candle_persist_ts_ms`, `last_successful_candle_bar` (Symbol, TF, `start_ts_ms`, `origin`).                          |
| **Health `/health`**                | Neuer Block **`ingest`** (Ticker-Zeiten, Kerzen, Reconnect, `provider_surface`, Gap-Fill-Fehler) + `bitget_ws_stream` um Reconnect-Telemetrie ergänzt. |
| **Feed-Health Event**               | Redis-Event `market_feed_health` enthält `ingest` (Snapshot) und `gapfill_last_error`.                                                                 |

---

## 2. Health-Felder (`GET /health`)

### 2.1 `ingest` (neu)

Beispielstruktur (Werte variieren zur Laufzeit):

```json
{
  "ingest": {
    "universe_note": "Alle Kerzen/Ticker-Pfade nutzen BITGET_SYMBOL und Katalog-Metadaten — kein implizites BTC-only; Multi-Symbol erfordert weitere Instanzen oder zukuenftige Fan-out-Erweiterung.",
    "configured_symbol": "BTCUSDT",
    "market_family": "futures",
    "candles": {
      "timeframe_to_channel": {
        "1m": "candle1m",
        "5m": "candle5m",
        "15m": "candle15m",
        "1H": "candle1H",
        "4H": "candle4H"
      },
      "last_close_event_ingest_ts_ms": 1743864123456,
      "last_persist_ts_ms": 1743864123400,
      "last_successful_bar": {
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "start_ts_ms": 1743864060000,
        "origin": "ws"
      }
    },
    "ticker": {
      "last_quote_ts_ms": 1743864123500,
      "last_ws_ticker_ts_ms": 1743864123480,
      "last_rest_snapshot_ts_ms": 1743864122000
    },
    "reconnect": {
      "ws_connection_state": "connected",
      "ws_reconnect_count": 0,
      "last_ws_reconnect_at_ms": null
    },
    "provider_surface": {
      "protocol": null,
      "transport": null
    },
    "gapfill": {
      "last_ok_ts_ms": 1743864100000,
      "last_reason": "reconnect",
      "last_error": null
    }
  }
}
```

**Semantik `provider_surface`:**

- **`protocol`:** Bitget hat „Nein“ gesagt (WS-`error`, REST-HTTP-Fehler nach Status, REST-Body `code` ungleich Erfolg). Sollte bei **falschem Symbol/ProductType** auffallen.
- **`transport`:** Verbindungsabbruch, Timeout, generische Exceptions auf dem Weg — **häufig kurzlebig**; Reconnect zählt weiter.

### 2.2 `bitget_ws_stream` (ergänzt)

Zusätzlich u. a.:

- `last_reconnect_at_ms`
- `ws_reconnect_count` (identisch zu `stats.reconnect_count` im übergeordneten Payload)

---

## 3. Nachweise

### 3.1 Öffentliche Bitget-Verifikation (Readonly)

```text
python tools/verify_bitget_rest.py live-readonly
```

**Erwartung:** Skript endet mit zusammenfassendem JSON (ohne Secrets); `public_api_ok` true bei erreichbarer Bitget-Öffentlich-API und passendem ENV.

**Smoke (nur Hilfe / Parser):**

```text
python tools/verify_bitget_rest.py --help
```

### 3.2 Service-nahe Unit-Tests

```text
python -m pytest tests/market-stream/test_provider_diagnostics.py tests/market-stream/test_rest_gapfill_429.py tests/market-stream/test_feed_freshness.py services/market-stream/tests/test_candles.py -q
```

- `test_provider_diagnostics`: Länge/Struktur von `provider_surface`.
- `test_rest_gapfill_429`: **429 → Retry → 200** gegen gemockten `httpx.AsyncClient`.

### 3.3 Health-Nachweis Marktfeed (laufender Dienst)

Voraussetzung: `market-stream` läuft (z. B. Compose), Port z. B. **8010**.

```text
curl -sS http://127.0.0.1:8010/health
```

**Operator-Checkliste:**

1. `ingest.reconnect.ws_connection_state` ist `connected` bei gesundem Feed.
2. `ingest.ticker.last_quote_ts_ms` wandert bei liquidem Markt.
3. `ingest.candles.last_persist_ts_ms` aktualisiert sich bei eingehenden Kerzen/REST-Sync.
4. `ingest.provider_surface.protocol` bei anhaltenden Problemen **nicht** null → Ursache vor Transport ausschließen (Symbol, `productType`, Channel).
5. `ingest.gapfill.last_error` gesetzt → letzter REST-Gap-Fill-Lauf fehlgeschlagen (Detail in Logs).

**Readiness** (`GET /ready`): unverändert in der Semantik der Checks; zusätzliche Diagnose primär über `/health` und `ingest`.

---

## 4. Betroffene Pfade (Code)

- `services/market-stream/src/market_stream/provider_diagnostics.py` (neu)
- `services/market-stream/src/market_stream/gapfill/rest_gapfill.py`
- `services/market-stream/src/market_stream/bitget_ws/client.py`
- `services/market-stream/src/market_stream/collectors/candles.py`
- `services/market-stream/src/market_stream/collectors/ticker.py`
- `services/market-stream/src/market_stream/app.py`
- `tests/market-stream/test_provider_diagnostics.py` (neu)
- `tests/market-stream/test_rest_gapfill_429.py` (neu)

---

## 5. Bekannte offene Punkte

- **[FUTURE]** Multi-Symbol aus **einer** `market-stream`-Instanz: erfordert Architektur (Fan-out, Limits Bitget pro Verbindung) — aktuell dokumentiert über `universe_note` und eine Instanz pro Symbol.
- **[TECHNICAL_DEBT]** Ticker-REST ohne eigenes 429-Retry (niedrigere Frequenz als Gap-Fill); bei Bedarf gleiches Muster wie Kerzen nachziehen.
