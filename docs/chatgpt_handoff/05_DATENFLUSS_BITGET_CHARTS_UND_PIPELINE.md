# Datenfluss: Bitget, Charts und Pipeline (bitget-btc-ai)

**Zweck:** Übergabe an ChatGPT — wie Marktdaten, Bitget-Anbindung, Kerzen-Charts, Features, Signale, Strategie-Registry, Paper/Shadow/Live und UI-Sichtbarkeit im Repo zusammenhängen.

**Stand der Analyse:** Code- und Doku-Review im Repository (kein Laufzeit-Nachweis des vollen Stacks in dieser Session). Wo Laufzeit nicht geprüft wurde, ist das explizit gekennzeichnet.

**Kennzeichnung:** `verifiziert (Repo)` = aus Quellcode/Doku im Repo ableitbar; `nicht verifiziert (Laufzeit)` = erfordert laufende Container/Netz/Secrets.

---

## 1. Management-Zusammenfassung

**Ist (Architektur):** Öffentliche Bitget-Marktdaten werden vom Dienst `market-stream` per WebSocket (und REST für Gap-Fill) bezogen, in Postgres (`tsdb.*`) und Redis-Streams (`events:*`) materialisiert. Downstream-Engines (`feature-engine`, `structure-engine`, `drawing-engine`, `signal-engine`, `news-engine`, `paper-broker`, `learning-engine`) schreiben in weitere Schemata (`features`, `app`, `paper`, `learn`, …). Das **api-gateway** ist die zentrale HTTP-Lese-Schicht fürs Dashboard: `GET /v1/live/state` liest **direkt Postgres** (Kerzen, letztes Signal, letztes Feature, Zeichnungen, News, Paper-State, Drift). `GET /v1/live/stream` (SSE) liest **Redis Streams** für Echtzeit-Updates. Das Dashboard ruft **keine** Worker-Microservices direkt aus dem Browser an — nur Gateway-URLs (serverseitig oder über konfigurierte Basis-URL).

**Charts im UI:** Kerzen-Charts beziehen ihre Serien aus `GET /v1/live/state` → Feld `candles[]` (Quelle `tsdb.candles`). Zusätzlich existiert auf der Paper-Seite eine **Equity-Kurve** (`ProductLineChart`) aus `/v1/paper/metrics/summary` → `equity_curve`, **kein** Bitget-OHLC.

**Paper / Shadow / Live:** Logisch getrennt über Betriebsmodi (`EXECUTION_MODE`, `APP_ENV`) und Datenpfade: Paper-Portfolio in `paper.*` + Paper-Events; Live-Ausführung und Entscheidungen über Live-Broker-Pfade (`/v1/live-broker/*`, Tabellen unter `live.*`); Shadow ist **kein** eigener Chart-Datenkanal — Vergleichs-/Forensik-Sichten nutzen Live-Broker-Daten und Paper-Trades (z. B. Konsole **Shadow/Live**).

**Soll / Lücke:** Vollständiger End-to-End-Betrieb (inkl. frischer Bitget-Daten, aller Engines, authentifiziertem Gateway) ist **umgebungsabhängig**. `PRODUCT_STATUS.md` stellt klar, dass „funktioniert“ von laufenden Diensten, ENV und Exchange abhängt.

---

## 2. End-to-End-Datenfluss von Bitget bis UI

### 2.1 Ingestion und Persistenz (Markt)

1. **Bitget (öffentlich):** WebSocket-Kanäle (u. a. Ticker, Trades, Orderbuch, Kerzen) und REST für Initial-Load / Gap-Fill — `services/market-stream` (`BitgetPublicWsClient`, Collector). `verifiziert (Repo):` `services/market-stream/README.md`, `docs/market-stream.md`.
2. **Normalisierung & Ausgabe:** Event-Envelopes in Redis Streams (`events:market_tick`, `events:candle_close`, `events:funding_update`, …) und optional Raw-Spiegel — `verifiziert (Repo):` `shared/contracts/catalog/event_streams.json`, `docs/data_pipeline_overview.md`.
3. **TSDB-Schreibpfad:** Kerzen in `tsdb.candles` (Spalten u. a. `start_ts_ms`, OHLC, `usdt_vol`, `ingest_ts_ms`); Ticker/Mark-Daten in `tsdb.ticker` für u. a. Paper-Mark — `verifiziert (Repo):` `docs/data_pipeline_overview.md`, `db_live_queries.fetch_candles` / `fetch_latest_ticker_meta`.

### 2.2 Features, Struktur, Signale, News, Paper

| Teilstrecke             | Produzent (Repo)                                   | Primäre Lesetabellen (Gateway)                                 |
| ----------------------- | -------------------------------------------------- | -------------------------------------------------------------- |
| Microstructure/Features | `feature-engine`                                   | `features.candle_features`                                     |
| Struktur → Zeichnungen  | `structure-engine`, `drawing-engine`               | `app.drawings`                                                 |
| Signale                 | `signal-engine`                                    | `app.signals_v1` (+ `app.signal_explanations`)                 |
| News                    | `news-engine`, LLM-Orchestrator (Dienst-zu-Dienst) | `app.news_items`                                               |
| Paper                   | `paper-broker`                                     | `paper.positions`, Trades/Journal/Metriken (via `/v1/paper/*`) |
| Drift                   | `learning-engine`                                  | `learn.online_drift_state`                                     |

`verifiziert (Repo):` `docs/data_pipeline_overview.md`, `services/api-gateway/src/api_gateway/db_live_queries.py` (`build_live_state`).

### 2.3 Gateway → Dashboard

1. **HTTP Aggregate:** `GET /v1/live/state?symbol=&timeframe=&limit=` → `build_live_state`: liest Kerzen, letztes Signal, Feature-Snapshot, Drawings, News, Paper-State, berechnet `market_freshness` und `data_lineage`. `verifiziert (Repo):` `routes_live.py`, `db_live_queries.py`.
2. **SSE:** `GET /v1/live/stream` — `XREAD` auf kanonischer Teilmenge (`live_sse_streams` in `event_streams.json`). Bei `LIVE_SSE_ENABLED=false` antwortet das Gateway mit HTTP 503; UI fällt auf Polling zurück. `verifiziert (Repo):` `docs/live_terminal.md`, `LiveTerminalClient.tsx` (`startManagedLiveEventSource`, Polling-Intervall `NEXT_PUBLIC_LIVE_POLL_INTERVAL_MS`).
3. **Dashboard-Aufrufe:** `apps/dashboard/src/lib/api.ts` — `fetchLiveState`, `fetchSignalsRecent` (`/v1/signals/recent`), `fetchStrategies` (`/v1/registry/strategies` → Postgres `learn.strategies` via `routes_registry_proxy.py`), Paper-/Live-Broker-Endpunkte.

### 2.4 Rendering im Browser

- **Terminal (`/terminal`):** Server-SSR lädt initial `fetchLiveState`; Client `LiveTerminalChart` / `ChartPanel` + `ProductCandleChart` (lightweight-charts), Overlays Signal/News/Paper, `LiveDataLineagePanel` aus `data_lineage`. `verifiziert (Repo):` `apps/dashboard/src/app/(operator)/console/terminal/page.tsx`, `LiveTerminalClient.tsx`.
- **Konsole Ops / Health / Live-Broker / Signale:** `ConsoleLiveMarketChartSection` pollt clientseitig erneut `fetchLiveState` bei Symbol-/TF-Wechsel. `verifiziert (Repo):` `ConsoleLiveMarketChartSection.tsx`.

---

## 3. Tabelle der beteiligten Dienste

| Dienst / Komponente   | Rolle im Datenfluss                                                       | Typische Health / Port (Doku)                                                           |
| --------------------- | ------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `market-stream`       | Bitget WS/REST → Redis + `tsdb`                                           | HTTP z. B. 8010, `/ready` prüft u. a. Datenfrische — `services/market-stream/README.md` |
| `feature-engine`      | Kerzen/Orderbuch → `features.candle_features`                             | Worker-Port laut Compose                                                                |
| `structure-engine`    | Struktur-Events                                                           | Redis/DB                                                                                |
| `drawing-engine`      | `app.drawings`, `events:drawing_updated`                                  | Redis/DB                                                                                |
| `signal-engine`       | `app.signals_v1`, `events:signal_created`                                 | Redis/DB                                                                                |
| `news-engine`         | `app.news_items`, `events:news_scored`                                    | Redis/DB                                                                                |
| `paper-broker`        | Paper-Portfolio, Trade-Events                                             | Redis/DB                                                                                |
| `learning-engine`     | `learn.online_drift_state`, Registry-Metriken                             | Redis/DB                                                                                |
| `api-gateway`         | Alle `/v1/*` Lesepfade, SSE, Auth                                         | 8000                                                                                    |
| `dashboard` (Next.js) | UI, Server-Components + Client; BFF-Routen unter `src/app/api/dashboard/` | 3000                                                                                    |
| `redis`               | Streams für Events + SSE                                                  | —                                                                                       |
| `postgres`            | TSDB, app, paper, learn, live, …                                          | —                                                                                       |

`verifiziert (Repo):` `docs/chatgpt_handoff/02_SYSTEM_TOPOLOGIE_UND_SERVICES.md`, `docker-compose.yml` (Details je nach Profil).

---

## 4. Welche Chart-Daten nachweislich unterstützt werden

### 4.1 Kerzen (OHLCV) — **Ist**

- **Quelle:** `tsdb.candles` gefiltert nach `symbol` + `timeframe` (DB-Normalisierung: `1h`→`1H`, `4h`→`4H`).
- **Unterstützte Timeframes im Gateway-Frische-Modell:** `1m`, `5m`, `15m`, `1H`, `4H` — `_TIMEFRAME_BAR_MS` in `db_live_queries.py` **muss** zu `market-stream` `CandleCollector`-Intervallen passieren (Kommentar im Code).
- **UI-Optionen:** Konsole/Terminal nutzen typischerweise `["1m","5m","15m","1h","4h"]` (URL/State).
- **Felder pro Kerze in API:** `time_s` (Unix-Sekunden, Bar-Start), `open`, `high`, `low`, `close`, `volume_usdt` (`usdt_vol` aus DB).
- **Volumen:** `ProductCandleChart` kann Volumen-Serie aus `volume_usdt` darstellen.

`verifiziert (Repo):` `fetch_candles`, `compute_market_freshness_payload`, `docs/live_terminal.md`, `ConsoleLiveMarketChartSection.tsx`.

### 4.2 Weitere „Charts“ im Dashboard — **Ist**

- **Paper Equity:** `ProductLineChart` mit Zeitreihe aus `fetchPaperMetricsSummary` → `equity_curve` (kein Bitget-Kerzenfeed).
- **Account Performance** (falls vorhanden): eigene Seitenlogik — gesondert aus `apps/dashboard` prüfen bei Bedarf.

### 4.3 Nicht als direkter Bitget-Chart-Pfad — **Ist**

- Orderbuch-Tiefe, Trades, Slippage-Metriken: in `market-stream` und TSDB/Redis modelliert (`docs/microstructure.md`), aber **das Standard-Kerzen-UI** liest sie **nicht** als Ersatz für `tsdb.candles`; Microstructure erscheint im Terminal als **`latest_feature`** (Snapshot), nicht als vollständiger historischer Chart.

---

## 5. Welche Signal- und Strategiepfade existieren

### 5.1 Signale

- **Persistenz:** `app.signals_v1` (+ optionale Erklärungen `app.signal_explanations`).
- **Lesepfade Gateway:** `GET /v1/signals/recent`, `GET /v1/signals/{id}`, `GET /v1/signals/facets`, `GET /v1/signals/{id}/explain` (soweit in `routes_*` implementiert).
- **Im Live-State:** `latest_signal` = jüngstes Signal passend zu **Symbol + Timeframe** der Chart-Auswahl.
- **SSE:** `signal_created` → Event-Typ `signal` für Terminal-Updates (`routes_live.py` Mapping).
- **Konsole Signale:** Tabelle + Filter + Chart-Section — `apps/dashboard/.../console/signals/page.tsx`.

`verifiziert (Repo):` `db_live_queries.fetch_latest_signal_bundle`, `api.ts`, `signals/page.tsx`.

### 5.2 Strategien (Registry)

- **HTTP:** `GET /v1/registry/strategies`, Detail `GET /v1/registry/strategies/{id}` — Implementierung `routes_registry_proxy.py`, Daten aus **`learn.strategies`** (`fetch_strategies_registry`).
- **UI:** `console/strategies` und `console/strategies/[id]` → `fetchStrategies` / `fetchStrategyDetail`.
- **Abgrenzung:** Das ist **Registry-Metadaten/Status**, nicht automatisch identisch mit „jeder Zeile in `signals_v1`“; Signalpfad und Strategie-Registry sind gekoppelt über Felder wie `strategy_name` / IDs im Signal, aber **getrennte** API-Endpunkte.

`verifiziert (Repo):` `routes_registry_proxy.py`, `strategies/page.tsx`.

### 5.3 LLM-Erklärungen (Signal/Strategie)

- Gateway forwardet ausgewählte Operator-KI-Routen zum LLM-Orchestrator; laut `PRODUCT_STATUS.md` sind **zwei** Dashboard-Pfade explizit als produktreif beschrieben (Operator-Explain, Strategie-Signal-Explain auf Signaldetail). **Kein** generischer „KI-Chart“.

---

## 6. Wie Paper, Shadow und Live logisch getrennt sind

### 6.1 Begriffe (Repo-konform)

- **`EXECUTION_MODE`:** `paper` | `shadow` | `live` (und `APP_ENV`: `local` | `shadow` | `production` | `test`) — `docs/env_profiles.md`, `docs/chatgpt_handoff/03_ENV_SECRETS_AUTH_MATRIX.md`.
- **Paper:** Simuliertes Portfolio; Daten in `paper.*`; API unter `/v1/paper/*`; Events `trade_opened` / `updated` / `closed` in SSE; `paper_state` in `/v1/live/state` inkl. `mark_price` aus `tsdb.ticker`.
- **Live:** Echte Ausführung nur über freigegebenen Live-Broker-Pfad; APIs `/v1/live-broker/*`, Tabellen `live.*` (Runtime, Orders, Fills, Decisions, Kill-Switch, Forensik). Signal-Payloads können `shadow_divergence_0_1` und Shadow/Live-Vergleichsfelder tragen (`db_live_broker_queries._shadow_live_fields`, `live.shadow_live_assessments`).
- **Shadow:** Produktionsnahe **Simulation ohne Live-Submit** / Spiegel-Logik — **kein** separates „Shadow-Chart“-Endpoint. Die UI-Seite **`console/shadow-live`** aggregiert **Live-Broker-Decisions**, **Fills** und **Paper-Trades** zur Vergleichssicht (`shadow-live/page.tsx`).

### 6.2 Ist vs. Soll

| Aspekt         | Ist im Code                                                       | Soll / Erwartung                                                                      |
| -------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Chart-Kerzen   | Immer aus `tsdb.candles` (gleiche Quelle für Paper-/Live-Ansicht) | Operator sieht **ein** Marktpreisbild; Ausführungsmodus ändert nicht die Kerzen-Query |
| Paper PnL      | Eigene Metriken/Trades                                            | Sichtbar auf `console/paper`                                                          |
| Live-Status    | Live-Broker-Runtime, Orders, Fills                                | Sichtbar auf `console/live-broker`                                                    |
| Shadow-Analyse | Vergleichstabellen / Divergenz                                    | `console/shadow-live` + Broker-Forensik                                               |

---

## 7. Welche Daten im Frontend wirklich sichtbar sein müssten

**Mindestbild für einen „warmen“ Stack (Soll aus Produktperspektive, angelehnt an implementierte Seiten):**

| UI-Ort                 | Erwartete sichtbare Datenquelle                                                                                                              |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `/terminal`            | Kerzen, `market_freshness`, `latest_signal`, `latest_feature`, `latest_drawings`, `latest_news`, `paper_state`, `data_lineage`, optional SSE |
| `console/ops`          | Cockpit + Chart (wie Terminal-Teil), Health, Paper-Open, Alerts, Learning-Modelle, Live-Broker-Snippets, …                                   |
| `console/signals`      | Liste + Facetten + Chart zu gewähltem Symbol/TF                                                                                              |
| `console/signals/[id]` | Signal-Detail + BFF für Strategie-Signal-Erklärung (laut `PRODUCT_STATUS.md`)                                                                |
| `console/strategies`   | Registry-Liste aus `/v1/registry/strategies`                                                                                                 |
| `console/paper`        | Positionen, Trades, Metriken, **Equity-Kurve**, Journal                                                                                      |
| `console/live-broker`  | Runtime, Orders, Fills, Decisions, Kill-Switch, Chart-Kontext                                                                                |
| `console/shadow-live`  | Aggregierte Shadow/Live/Paper-Vergleichsmetriken                                                                                             |
| `console/health`       | System-Health + Operator-Explain (KI)                                                                                                        |

**Ist-Lücke:** Wenn Gateway oder DB fehlt, liefert das Dashboard **degradierte** Envelopes oder leere Arrays; Terminal-SSR kann Platzhalter `emptyState` setzen (`terminal/page.tsx`).

---

## 8. Häufige Ursachen für leere Daten oder veraltete Daten

1. **`market-stream` läuft nicht oder Bitget nicht erreichbar:** Keine/neue Zeilen in `tsdb.candles` → leerer Chart oder alter letzter Bar; `market_freshness.status` wird `stale`/`dead` oder `no_candles` gemäß `compute_market_freshness_payload`.
2. **Falsches Symbol oder nicht ingestiertes Symbol:** Validierung `validate_live_symbol` schlägt bei ungültigem Format fehl; sonst leere Query-Ergebnisse.
3. **Timeframe nicht im Frische-Modell:** Unbekanntes TF → `unknown_timeframe` in `market_freshness`.
4. **Postgres-Down / Gateway-DB-Fehler:** `build_live_state` setzt bei DB-Fehler `health.db=error`, leert Candle/Ticker-Frische-Blöcke und setzt Status auf `no_candles` (außer `unknown_timeframe`).
5. **Redis down:** `health.redis=error`; SSE kann fehlschlagen oder 503 — Polling bleibt möglich, aber ohne Push.
6. **`LIVE_SSE_ENABLED=false`:** Kein Live-Push; verzögerte Anmutung ohne Polling-Intervall-Anpassung.
7. **Engines aus:** `latest_feature`, `latest_signal`, `latest_drawings`, `latest_news` bleiben `null`/`[]`; `data_lineage` beschreibt **warum** (Teilstrecken).
8. **Frische-Thresholds:** Standard `stale_warn_ms` default 900_000 ms (15 min) in `build_live_state` — alte Daten werden als verzögert/stale klassifiziert auch wenn noch „irgendwelche“ Kerzen existieren.
9. **Demo-Seeds:** Optional nur unter **`infra/migrations/postgres_demo/`** mit **`BITGET_ALLOW_DEMO_SCHEMA_SEEDS=true`** und zweiter Migrate-Phase — `596`/`597`/`603` im Hauptpfad sind No-Op-Platzhalter. Vertrag: `docs/cursor_execution/11_migrations_and_seed_separation.md`.

---

## 9. Verifizierte Nachweise, Tests oder Grenzen

| Nachweis                                      | Was es prüft                         | Einschränkung                                                                                                                                                                |
| --------------------------------------------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tests/dashboard/test_live_state_contract.sh` | Kontrakt `/v1/live/state`            | Benötigt laufenden Stack + **bash**; auf reinem Windows ohne WSL in dieser Session **nicht ausführbar** — `nicht verifiziert (Laufzeit)`.                                    |
| `pnpm smoke` / `scripts/rc_health.ps1`        | Edge-Health                          | In dieser Session **fehlgeschlagen** (Parser-Fehler in `scripts/_dev_compose.ps1`, vermutlich Encoding/Zeichen in Strings) — `nicht verifiziert (Laufzeit)` auf diesem Host. |
| Playwright `e2e/tests/release-gate.spec.ts`   | UI-Pfade inkl. Terminal/Chart/Broker | Laut `PRODUCT_STATUS.md` in CI im Job `compose_healthcheck`; lokal `pnpm e2e` — `verifiziert (Repo-Doku)`, Laufzeit hier nicht ausgeführt.                                   |
| `pnpm api:integration-smoke`                  | HTTP-Integration                     | `nicht verifiziert (Laufzeit)` in dieser Session.                                                                                                                            |
| Gateway-Unit-Tests (LLM-Routen etc.)          | Teilaspekte von `create_app()`       | Laut `PRODUCT_STATUS.md` ENV-abhängig.                                                                                                                                       |

**Grenze:** Ohne laufende `docker compose`-Stack und gültige `.env.local` ist kein **End-to-End-Beweis** für Bitget-Live-Daten möglich; die **Pipeline** ist im Repo **implementiert und dokumentiert**, nicht automatisch „immer live“.

---

## 10. Übergabe an ChatGPT

**So dieses Dokument nutzen:**

1. **Kerzen-Fragen** immer über `tsdb.candles` + `market-stream` beantworten, nicht über „irgendeine Chart-API“.
2. **Signal vs. Strategie:** Signale = `app.signals_v1` + `/v1/signals/*`; Strategie-Registry = `learn.strategies` + `/v1/registry/strategies`.
3. **Shadow:** Kein paralleler Marktdatenfeed — Vergleichslayer über Live-Broker + Paper + Assessments.
4. **Ist vs. Soll:** Codepfade sind **Ist**; vollständiger Betrieb ist **Soll** und umgebungsabhängig (`PRODUCT_STATUS.md`).
5. Bei **leerer UI** zuerst `data_lineage`, `health`, `market_freshness` aus `/v1/live/state` und Compose-Logs der Producer-Dienste prüfen.

---

## 11. Anhang: Pfade, Kommandos und Logs

### 11.1 Wichtige Dateipfade (Repo)

| Thema                 | Pfad                                                                      |
| --------------------- | ------------------------------------------------------------------------- |
| Live-State SQL        | `services/api-gateway/src/api_gateway/db_live_queries.py`                 |
| Live-Routen + SSE     | `services/api-gateway/src/api_gateway/routes_live.py`                     |
| Event-Stream-Katalog  | `shared/contracts/catalog/event_streams.json`                             |
| Dashboard API-Client  | `apps/dashboard/src/lib/api.ts`                                           |
| Terminal Client       | `apps/dashboard/src/components/live/LiveTerminalClient.tsx`               |
| Konsole Chart-Section | `apps/dashboard/src/components/console/ConsoleLiveMarketChartSection.tsx` |
| Kerzen-Rendering      | `apps/dashboard/src/components/chart/ProductCandleChart.tsx`              |
| Pipeline-Überblick    | `docs/data_pipeline_overview.md`                                          |
| Live-Terminal API     | `docs/live_terminal.md`                                                   |
| Market Stream         | `docs/market-stream.md`, `services/market-stream/README.md`               |
| Produktstatus         | `PRODUCT_STATUS.md`                                                       |
| Registry proxy        | `services/api-gateway/src/api_gateway/routes_registry_proxy.py`           |

### 11.2 Typische Kommandos (lokal, aus Doku)

```bash
docker compose --env-file .env.local -f docker-compose.yml logs --tail=200 market-stream feature-engine structure-engine drawing-engine signal-engine news-engine paper-broker learning-engine api-gateway
```

```bash
# Aus docs/live_terminal.md — benötigt laufendes Gateway
bash tests/dashboard/test_live_state_contract.sh
```

```powershell
# Root package.json
pnpm e2e
pnpm api:integration-smoke
pnpm smoke
```

### 11.3 API-Referenz (Auszug)

- `GET /v1/live/state` — Aggregate Chart + Signal + Feature + …
- `GET /v1/live/stream` — SSE (Redis)
- `GET /v1/signals/recent`, `GET /v1/signals/{id}`
- `GET /v1/registry/strategies`
- `GET /v1/paper/...`, `GET /v1/live-broker/...`
- `GET /v1/system/health`

### 11.4 Bekannte Schwachstellen / Risiken

- **Bitget WS Message Loss** (Herstellerhinweis) → REST-Gap-Fill im `market-stream` vorgesehen; trotzdem kurzzeitige Lücken möglich — `docs/market-stream.md`.
- **Single Gateway** als BFF — Ausfall = kein konsistenter UI-Datenkanal.
- **Windows-Smoke:** Tooling-Encoding kann Skripte brechen — siehe Abschnitt 9.

---

_Ende der Übergabedatei._
