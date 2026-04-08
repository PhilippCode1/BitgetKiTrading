# News-Scoring (V1)

Erweiterung des `news-engine`: regelbasierte Bewertung gespeicherter `app.news_items`,
optional Anreicherung per LLM-Orchestrator (`POST /llm/news_summary`). Versionierung ueber
`NEWS_SCORING_VERSION` und Spalte `scoring_version`.

## Datenbank

Migration `100_news_scoring.sql`:

- `relevance_score` **integer** 0–100, Default 0
- `sentiment` **text**: `bullisch` | `baerisch` | `neutral` | `mixed` | `unknown`
- `impact_window` **text**: `sofort` | `mittel` | `langsam` | `unknown`
- `scored_ts_ms`, `scoring_version`, `llm_summary_json`, `entities_json`
- Index `(relevance_score DESC, published_ts_ms DESC)`

## Regeln V1 (deterministisch)

### Keyword-Relevanz (Basis)

| Muster                                                                      | Punkte     |
| --------------------------------------------------------------------------- | ---------- |
| `bitcoin`, Wort `btc`                                                       | +30        |
| `etf`, `sec`, `regulation`                                                  | +25        |
| `lawsuit`                                                                   | +25        |
| `fed`, `cpi`, `inflation`, `rates`                                          | +20        |
| `hack`, `exploit`, `breach`                                                 | +25        |
| „Minor noise“: allgemeine Crypto/Markt-Begriffe (`crypto`, `blockchain`, …) | +0 bis +10 |

### Quellen-Bonus

| `source`      | Bonus |
| ------------- | ----- |
| `cryptopanic` | +10   |
| `coindesk`    | +10   |
| `newsapi`     | +5    |
| `gdelt`       | +5    |

### Zeitfaktor (Multiplikator auf die Summe vor Cap)

- Alter &lt; 10 min: **×1.2**
- &lt; 60 min: **×1.0**
- &lt; 6 h: **×0.8**
- sonst: **×0.5**

Ergebnis wird auf **0..100** begrenzt.

### Sentiment (heuristisch)

- Woerter wie `approval`, `adopt`, `inflow`, `surge`, `rally` → **bullisch**
- `ban`, `lawsuit`, `hack`, `outflow`, `crash`, … → **baerisch**
- Beides → **mixed**
- sonst **neutral**

### Impact-Window (heuristisch)

Siehe `scoring/impact_window.py`:

- NewsAPI **Top-Headlines** (`raw_json.ingest_channel == top_headlines`) → **sofort**
- Breaking/Urgent in jungen Artikeln → **sofort**
- Macro/Opinion ohne Regulatorik → eher **langsam**
- ETF/Fed/Regulation → **sofort** oder **mittel**

## LLM-Erweiterung (`NEWS_LLM_ENABLED=true`)

- Aufruf nur an `LLM_ORCH_BASE_URL` → `POST /llm/news_summary` (kein direkter Provider-Key im News-Engine).
- Antwortschema: `shared/contracts/schemas/news_summary.schema.json` (u. a. `relevance_score_0_100`,
  `sentiment_neg1_to_1`, optional `impact_window`).
- **Relevanz-Clamp**: LLM-Score wird auf **rule_score ± NEWS_SCORE_MAX_LLM_DELTA** begrenzt (Default 15).
- Bei ausreichender `confidence_0_1` (≥ 0.4) duerfen LLM-Sentiment und LLM-`impact_window` die Regelwerte
  ueberschreiben.
- `llm_summary_json` und `entities_json` werden nur gesetzt, wenn der LLM-Call erfolgreich war;
  erneutes reines Rule-Scoring ueberschreibt sie nicht (SQL `COALESCE`).

## Events

Stream **`events:news_scored`**, `event_type=news_scored`, Payload u. a.:

- `news_id`, `relevance_score`, `sentiment`, `impact_window`, `published_ts_ms`

Steuerung: `NEWS_SCORE_PUBLISH_EVENTS` (Default `true`).

## HTTP

- `GET /health` (bestehend)
- `POST /score/now` — alle „unscored“ oder „stale“ (andere `scoring_version`) Items
- `GET /news/scored?min_score=&limit=`
- `GET /news/{id}` — DB-`id` (bigserial)

## Signal-Engine

`sentiment` wird aus der DB als Text gelesen; fuer Schock-Heuristiken und News-Layer wird er in
`signal_engine.news_compat.news_sentiment_as_float` auf ein internes Float gemappt.

## Strukturierter Marktkontext (SMC)

Die gleichen DB-Felder (`relevance_score`, `sentiment`, `impact_window`, `raw_json.topic_tags`, Text)
fliessen zusaetzlich in den deterministischen **Structured Market Context** ein: Facetten, Decay,
Surprise, Konfliktregeln gegen die technische Richtung und getrennte Pfade fuer Annotation vs.
Soft-Downgrade vs. optionale Hard-Vetos vs. **nur Live**-Execution-Blocker. Siehe
[structured_market_context.md](structured_market_context.md).
