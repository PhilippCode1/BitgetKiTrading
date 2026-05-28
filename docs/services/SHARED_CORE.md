# Shared Core Libraries (Python & Rust)

Die Shared Core Libraries (`/shared_py` und `/shared_rs`) bilden das technologische Rückgrat für das gesamte Microservice-Ökosystem. Sie abstrahieren System-Calls, standardisieren die Interservice-Kommunikation und verlagern performancekritische Operationen auf Systemebene (Rust).

## 1. Rust Core (`shared_rs`)

Die Rust-Module garantieren extrem niedrige Latenzen und Speichereffizienz in Hot-Paths. Die Integration in Python erfolgt über Maturin/PyO3.

| Modul | Funktion |
|---|---|
| `apex_core` | Zentrale Rechen-Engine für numerische Indikatoren (SMA, EMA, ATR, RSI, Trend). Berechnet Features direkt auf C-Arrays (via numpy FFI) ohne Python-GIL-Bottleneck. |
| `orderbook` | Performante L2-Orderbuch-Pflege. Verarbeitet Delta-Snapshots und verwaltet die Bids/Asks in hochoptimierten Trees/Maps. Bereitet VPIN und Imbalance-Metriken vor. |
| `shm_ring` | Inter-Process-Communication (IPC) via Shared Memory. Erlaubt den Zero-Copy Datenaustausch von High-Frequency Ticks zwischen verschiedenen Python-Prozessen (z.B. zwischen Streamer und Engine) unter Umgehung des Netzwerkstacks. |

## 2. Eventbus & Redis Streams (`shared_py/eventbus`)

Das zentrale Nervensystem für das Event-Driven Architecture (EDA) Messaging ist Redis Streams. 

- **Envelope Modell (`envelope.py`)**: Jeder Event auf dem Bus ist strikt als Pydantic-Modell (`EventEnvelope`) typisiert. Jeder Envelope hat eine UUID, einen deterministischen Zeitstempel (`ingest_ts_ms`), ein Tracing-Feld für Data-Lineage und wird gegen ein strenges JSON-Schema validiert (`ensure_payload_matches_schema`).
- **Stream Registry**: Das Mapping von Event-Typen zu Redis-Streams ist fest in `event_streams.json` verdrahtet (z.B. `market_tick`, `signal_created`, `dlq`).
- **Redis Stream Bus (`redis_streams.py`)**: Implementiert Producer und Consumer Groups. Das System nutzt `XADD` zum Senden und blockierendes `XREADGROUP` zum Empfangen. 
- **DLQ (Dead Letter Queue)**: Fehlerhafte Nachrichten (z.B. Parse-Errors, Schema-Violations) werden von den Consumern automatisch über die `publish_dlq`-Methode in einen Quarantäne-Stream verschoben und blockieren so nicht die Main-Pipeline.

## 3. Pydantic-Modelle und Replay Determinismus

Die gesamte Systemkommunikation ist über Pydantic-Verträge (`shared_py/model_contracts/`) definiert.

- **Replay-Fähigkeit**: Ein Kern-Paradigma des Backtestings ist der Replay-Determinismus. Der Event-Envelope unterstützt stabile Event-IDs und garantierte Ingestions-Zeitstempel (`stable_stream_event_id`), sodass Backtesting (und Paper-Trading) exakt dieselben Ergebnisse liefert wie das spätere Live-Trading.
- **Payload Validation**: Durch strikte Typisierung und JSON-Schema-Prüfung (`_jsonschema_payload_fail_fast`) werden korrupte Datenstrukturen (z.B. Null-Pointer, ungültige Typen) abgewiesen, noch bevor sie auf dem Bus landen. Dies setzt die "Zero-Regression" Philosophie bis auf die Daten-Ebene fort.
