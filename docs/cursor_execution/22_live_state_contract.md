# 22 — Live-State-Vertrag (`GET /v1/live/state`)

## Pflichtgrundlage

**Datei 05:** `docs/chatgpt_handoff/05_DATENFLUSS_BITGET_CHARTS_UND_PIPELINE.md` — Datenfluss Bitget → `tsdb` → Gateway → Dashboard; dieser Vertrag praezisiert die **JSON-Struktur** und **Degrades**.

## Rolle des Endpunkts

| Aspekt              | Inhalt                                                                                                |
| ------------------- | ----------------------------------------------------------------------------------------------------- |
| **Route**           | `GET /v1/live/state?symbol=&timeframe=&limit=`                                                        |
| **Auth**            | `require_sensitive_auth` (wie andere `/v1/*`-Lesepfade)                                               |
| **Quelle**          | Postgres im Gateway (`db_live_queries.build_live_state`)                                              |
| **Envelope**        | `merge_read_envelope` — `status`, `message`, `empty_state`, `degradation_reason`, `next_step`         |
| **Kontraktversion** | `live_state_contract_version` (Gateway: **1**; Dashboard-Platzhalter ohne erfolgreichen Fetch: **0**) |

## Pflichtfelder (Payload-Kern)

Immer gesetzt (auch bei DB-Fehler oder leerem Chart):

| Feld                          | Typ / Semantik                                                                        |
| ----------------------------- | ------------------------------------------------------------------------------------- |
| `live_state_contract_version` | `number`                                                                              |
| `symbol`, `timeframe`         | normalisiertes TF (`1H`/`4H`)                                                         |
| `server_ts_ms`                | Serverzeit bei Build                                                                  |
| `candles`                     | `[]` oder OHLCV-Zeilen                                                                |
| `latest_signal`               | Objekt oder **`null`** (= kein Signal, kein Fehler)                                   |
| `latest_feature`              | Objekt oder **`null`**                                                                |
| `structure_state`             | Objekt oder **`null`**                                                                |
| `latest_drawings`             | Array (leer erlaubt)                                                                  |
| `latest_news`                 | Array (leer erlaubt)                                                                  |
| `paper_state`                 | Objekt mit `open_positions`, `last_closed_trade`, `unrealized_pnl_usdt`, `mark_price` |
| `online_drift`                | Objekt oder **`null`**                                                                |
| `data_lineage`                | Array von Segmenten (Pipeline-Erklaerung)                                             |
| `health`                      | `{ "db": "ok"\|"error", "redis": "ok"\|"error"\|"skipped" }`                          |
| `market_freshness`            | Status + optional `candle`/`ticker`-Bloecke                                           |
| `demo_data_notice`            | `{ show_banner, reasons }`                                                            |

**GatewayReadEnvelope:**

- `status`: **`ok`** | **`empty`** | **`degraded`**
  - **`empty`:** DB `health.db === "ok"`, aber **keine Kerzen** und **`latest_signal === null`** (cold / Pipeline leer).
  - **`degraded`:** DB-Fehler, fehlende `DATABASE_URL`, oder Ausnahme beim Build; oder `health.db === "error"` im Payload.
  - **`ok`:** sonst (auch mit teilweise leeren Arrays, solange nicht beides Kerzen+Signal leer).

## `market_freshness.status`

`s live` | `delayed` | `stale` | `dead` | `no_candles` | `unknown_timeframe`

Bei DB-Fehler werden `candle`/`ticker` auf **`null`** gesetzt und (ausser `unknown_timeframe`) `status` oft **`no_candles`**.

## TypeScript (Dashboard)

- `apps/dashboard/src/lib/types.ts` — `LiveStateResponse`, `LiveStateHealthDatastore`, Pflichtarrays.
- `apps/dashboard/src/lib/live-state-defaults.ts` — `emptyLiveStateResponse()` fuer SSR-Fallback (`contract_version: 0`, `health: unknown`).

## Beispielpayloads (schematisch)

### Warm (Kerzen + Signal, Envelope ok)

```json
{
  "status": "ok",
  "message": null,
  "empty_state": false,
  "degradation_reason": null,
  "next_step": null,
  "live_state_contract_version": 1,
  "symbol": "BTCUSDT",
  "timeframe": "1m",
  "candles": [
    {
      "time_s": 1700000000,
      "open": 1,
      "high": 2,
      "low": 0.5,
      "close": 1.5,
      "volume_usdt": 1000
    }
  ],
  "latest_signal": {
    "signal_id": "…",
    "direction": "long",
    "signal_strength_0_100": 55,
    "probability_0_1": 0.6,
    "signal_class": "primary",
    "risk_warnings_json": []
  },
  "latest_drawings": [],
  "latest_news": [],
  "paper_state": {
    "open_positions": [],
    "last_closed_trade": null,
    "unrealized_pnl_usdt": 0,
    "mark_price": 42000
  },
  "health": { "db": "ok", "redis": "ok" },
  "market_freshness": {
    "status": "live",
    "timeframe": "1m",
    "stale_warn_ms": 900000,
    "candle": { "…": "…" },
    "ticker": { "last_pr": 42000, "…": "…" }
  },
  "data_lineage": [{ "segment_id": "candles", "has_data": true, "…": "…" }],
  "demo_data_notice": { "show_banner": false, "reasons": [] }
}
```

### Cold / no-signal (leerer Chart, kein Signal, DB ok)

`status`: **`empty`**, `empty_state`: **true**, `degradation_reason`: **`no_candles_and_signal`**, `candles`: **`[]`**, `latest_signal`: **`null`**.

### Stale (Frische-Modell)

`market_freshness.status`: **`stale`** oder **`dead`**; Kerzen koennen vorhanden sein; UI nutzt `freshnessBannerRole`.

### DB-Error (Build mit fehlgeschlagener Verbindung)

`health.db`: **`error`**, `candles`: **`[]`**, `market_freshness.candle`/`ticker`: **`null`**, `status` oft **`no_candles`**. HTTP-Envelope: **`degraded`** mit `degradation_reason` je nach Route (`database_url_missing`, `live_state_partial`, `database_unhealthy`).

### No-signal (Kerzen da, kein Signal)

`status`: **`ok`**, `latest_signal`: **`null`**, `empty_state`: **false** (weil nicht beides leer).

## Nachweise

**HTTP (mit JWT / Gateway-Auth wie in eurer Umgebung):**

```bash
curl -sS -H "Authorization: Bearer <JWT>" \
  "$API_GATEWAY_URL/v1/live/state?symbol=BTCUSDT&timeframe=1m&limit=120" | jq .
```

**Python:**

```bash
pytest tests/unit/api_gateway/test_live_state_contract.py -q
```

**Dashboard:**

```bash
cd apps/dashboard && pnpm check-types
pnpm exec jest src/lib/__tests__/live-state-defaults.test.ts
```

## Code-Referenzen

- `services/api-gateway/src/api_gateway/db_live_queries.py` — `LIVE_STATE_CONTRACT_VERSION`, `build_live_state`, `compute_market_freshness_payload`
- `services/api-gateway/src/api_gateway/routes_live.py` — `live_state`, Envelope-Logik
- `services/api-gateway/src/api_gateway/gateway_read_envelope.py` — Envelope-Felder
- `shared/ts/src/gatewayReadEnvelope.ts` — `GatewayReadStatus`

## Offene Punkte

- `[FUTURE]` OpenAPI-Fragment fuer `/v1/live/state` in `shared/contracts/openapi/` nachziehen.
- `[TECHNICAL_DEBT]` Shell-Skript `tests/dashboard/test_live_state_contract.sh` auf Windows/WSL dokumentiert (Datei 05).
