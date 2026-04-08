# News Engine (Prompt 15 / Prompt 12 Härtung)

Der Service `services/news-engine` zieht Schlagzeilen aus vier Quellen, filtert grob per
Keyword-Liste, dedupliziert und persistiert in **`app.news_items`**. Jedes neu eingefügte
Row löst ein Event auf **`events:news_item_created`** aus (`EventEnvelope`,
`event_type=news_item_created`).

## Ausfall & Trading-Kern

- **Kein News-Dienst ist Pflicht für Signale:** Die Signal-Engine nutzt bei fehlender oder
  veralteter News-Zeile einen **Neutral-Default** (`SIGNAL_DEFAULT_NEWS_NEUTRAL_SCORE`) und
  markiert die Schicht als `news_unavailable` bzw. `stale_news_context` in den Data-Issues.
- **`SIGNAL_NEWS_IN_COMPOSITE_ENABLED=false`:** News-Gewicht wird auf **0** gesetzt und auf
  die **Structure**-Schicht umverteilt; der Composite bleibt normiert (Summe 1.0).
- **`SIGNAL_NEWS_SHOCK_REJECTION_ENABLED=false`:** News-Schock-Heuristiken in Rejection,
  Regime-Klassifikator und Risk-Warnings werden **nicht** aus News abgeleitet.
- **LLM-Anreicherung** (`NEWS_LLM_ENABLED`): verschiebt Relevanz nur innerhalb
  **`NEWS_SCORE_MAX_LLM_DELTA`** um die regelbasierte Basis; sie kann **keine** Freigabe
  allein tragen.

## Quellen

| Quelle          | Modus                          | Hinweis                                                                                                                                                                                                                |
| --------------- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CryptoPanic** | REST „posts“                   | Endpunkt/Parameter können sich ändern — URL über `CRYPTOPANIC_API_URL` anpassbar. Ohne `CRYPTOPANIC_API_KEY` wird die Quelle übersprungen (außer Fixture-Mode). Enterprise-Push/Webhook ist nicht Teil dieses Prompts. |
| **NewsAPI**     | `top-headlines` + `everything` | Ohne `NEWSAPI_API_KEY` werden beide Calls übersprungen (außer Fixture-Mode). Top-Headlines optional mit `NEWSAPI_TOP_COUNTRY` (Default `us`).                                                                          |
| **CoinDesk**    | RSS (`COINDESK_RSS_URL`)       | Immer aktiv (HTTP oder Fixture).                                                                                                                                                                                       |
| **GDELT**       | DOC 2.0 `ArtList`              | Query wird aus `NEWS_KEYWORDS` als OR-Kette gebaut; Basis-URL `GDELT_DOC_API_BASE`.                                                                                                                                    |

**API-Details können sich ändern** — Anpassungen nur im Code/ENV, keine fest eingebauten Secrets.

## Datenmodell

Migration **`090_news_items.sql`** erweitert die bestehende Tabelle aus `020` um u. a.:

- `news_id` (uuid, eindeutig), `source_item_id`, `published_ts_ms`, `ingested_ts_ms`
- `description`, `content`, `author`, `language`
- Unique weiterhin auf **`url`**
- Partieller Unique-Index auf **`(source, source_item_id)`**, wenn `source_item_id` gesetzt ist

## Fixture-Mode (`NEWS_FIXTURE_MODE=true`)

- Keine ausgehenden HTTP-Requests zu CryptoPanic/NewsAPI/GDELT/RSS.
- Es werden Dateien unter `services/news-engine/fixtures/` geladen (`*.json`, `*.xml`).
- **Pflicht für CI/pytest**, damit Tests ohne API-Keys reproduzierbar sind.
- **Verboten** bei `APP_ENV=shadow` oder `APP_ENV=production` sowie bei
  `NEWS_FIXTURE_MODE=true` zusammen mit `BITGET_DEMO_ENABLED=true` außerhalb von
  `local` / `development` / `test` (Validierung in `config/settings.py`).
- Bei `PRODUCTION=true` weiterhin unzulässig (wie zuvor).

## Keyword-Filter (hart, Prompt 17 folgt)

Nur Items, in deren Titel/Beschreibung/Text mindestens ein Eintrag aus **`NEWS_KEYWORDS`**
(kommagetrennt, case-insensitive) vorkommt, werden gespeichert.

## Dedupe

1. **URL-Kanonisierung** vor dem Insert: Tracking-Query-Parameter (`utm_*`, `gclid`, …)
   werden entfernt; optional `www.`-Präfix am Host.
2. Pro Lauf: gleiche kanonische `url` nur einmal verarbeiten (Batch); **Quellen-Priorität**
   beim Sortieren: `cryptopanic` → `coindesk` → `newsapi` → `gdelt` (höhere Priorität
   gewinnt bei gleicher URL).
3. DB: `ON CONFLICT (url) DO NOTHING`.
4. Zusätzlich Unique auf `(source, source_item_id)` — Kollisionen werden abgefangen.

## Freshness (Ingest)

- `NEWS_MAX_INGEST_ITEM_AGE_MS` (Default 7 Tage): ältere Meldungen werden verworfen.
- `NEWS_MAX_FUTURE_SKEW_MS`: Meldungen mit `published` deutlich in der Zukunft werden
  verworfen (Feed-Fehler).

## Themen-Tags (`topic_tags` in `raw_json`)

Regelbasierte Zuordnung zu Buckets (`btc`, `macro`, `regulatory`, …) für Scoring und
Symbol-Matching in der Signal-Engine (`raw_json::text` in `fetch_latest_news`).

## HTTP / SSRF

Nur Hosts aus **`NEWS_HTTP_ALLOWED_HOSTS`** sind für `httpx`-GETs erlaubt (Komma-Liste).

## API

- `GET /health` — DB/Redis-Check + letzte Ingest-Stats
- `POST /ingest/now` — ein sofortiger Poll-Zyklus (alle Quellen)
- `GET /news/latest?limit=20` — letzte Items

## Betrieb

```bash
cd services/news-engine
pip install -e .
# PYTHONPATH: shared_py siehe README
set NEWS_FIXTURE_MODE=true
set DATABASE_URL=...
set REDIS_URL=...
python -m news_engine.main
```

Worker läuft im Hintergrund mit `NEWS_POLL_INTERVAL_SEC` Pause zwischen Zyklen (kein Busy-Loop).

## Redis

```bash
redis-cli XLEN events:news_item_created
redis-cli XREAD COUNT 5 STREAMS events:news_item_created 0
```

## Sicherheit

- Keine API-Keys in Logs; URLs mit Query-Parametern werden nicht vollständig geloggt.
- Relevance/Sentiment-Scoring kommt in **Prompt 17** — hier nur `NULL` in der DB.
