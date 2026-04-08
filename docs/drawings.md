# Drawing Engine (Prompt 12)

`drawing-engine` konsumiert **`events:structure_updated`**, liest Swings,
Strukturzustand und optional das letzte **Orderbook-Top25** aus Postgres,
erzeugt daraus **versionierte** Drawing-Objekte und speichert sie in
**`app.drawings`**. Vor jedem Insert wird der Datensatz gegen
**`shared/contracts/schemas/drawing.schema.json`** validiert (JSON Schema +
Format-Checks). Bei neuen Revisionen wird **`events:drawing_updated`**
publiziert (`payload.parent_ids`).

## HTTP

| Methode | Pfad                                  | Beschreibung                                                  |
| ------- | ------------------------------------- | ------------------------------------------------------------- |
| GET     | `/health`                             | Liveness + Worker-Stats                                       |
| GET     | `/drawings/latest?symbol=&timeframe=` | Nur **active**, jeweils **hoechste Revision** pro `parent_id` |
| GET     | `/drawings/history?parent_id=`        | Alle Revisionen sortiert nach `revision`                      |

## Drawing-Typen (`type`)

| Typ               | Geometrie (`geometry.kind`) | Quelle                                           |
| ----------------- | --------------------------- | ------------------------------------------------ |
| `support_zone`    | `horizontal_zone`           | Swing-Low-Cluster                                |
| `resistance_zone` | `horizontal_zone`           | Swing-High-Cluster                               |
| `trendline`       | `two_point_line`            | letzte 2–3 Swing Lows (UP) bzw. Highs (DOWN)     |
| `breakout_box`    | `price_time_box`            | `breakout_box_json` aus `app.structure_state`    |
| `liquidity_zone`  | `horizontal_zone`           | Orderbook Top-K nach Notional, sonst Swing-Proxy |
| `target_zone`     | `horizontal_zone`           | naechste R/S gemaess Bias (`trend_dir`)          |
| `stop_zone`       | `horizontal_zone`           | Invalidierung unter/unter letztem Swing          |

Preise in der Geometrie sind **Dezimalstrings** (keine wissenschaftliche Notation),
kompatibel mit spaeteren **LLM Structured Outputs**.

## Status & Revisionierung

- **`parent_id`**: stabil (UUIDv5 aus logischem Key), identifiziert „dieselbe“ Zone/Linie.
- **`revision`**: strikt monoton pro `parent_id` (`UNIQUE (parent_id, revision)`).
- **`drawing_id`**: UUID der konkreten Zeile (eine pro Revision).
- **`status`**: `active` | `hit` | `invalidated` | `expired` — bei neuem Inhalt werden
  bisherige `active`-Zeilen dieses `parent_id` auf **`expired`** gesetzt, dann folgt
  eine neue Revision mit `active`.

Drawings, deren `parent_id` bei einem Update nicht mehr vorkommt, werden ebenfalls
auf **`expired`** gesetzt.

## Konfiguration (ENV)

Siehe `.env.example`: `ZONE_CLUSTER_BPS`, `ZONE_PAD_BPS`, `STOP_PAD_BPS`,
`LIQUIDITY_TOPK`, `LIQUIDITY_CLUSTER_BPS`, Redis/DB/Stream/Group/Port.

## LLM / JSON Schema

Das Schema unter `shared/contracts/schemas/` ist **contract-first** angelegt;
TypeScript-Typen liegen in `shared/ts/src/drawing.ts`. So koennen spaeter
OpenAI Structured Outputs schema-konforme Drawing-Objekte liefern.

## Tests

```bash
pytest -q tests/drawing_engine
```
