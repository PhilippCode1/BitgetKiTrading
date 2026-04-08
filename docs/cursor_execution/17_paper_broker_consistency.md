# 17 — Paper-Broker: API-Vertrag, DB-Bezug und Console/Paper-UI

## Ziel

Ein **konsistentes** Bild aus Gateway-Lesepfaden (`/v1/paper/*`), Postgres (`paper.*`, `learn.trade_evaluations`) und der Dashboard-Seite **`/console/paper`**: Positionen, geschlossene Trades, Konten-Metriken, eingebettetes Ledger-Snippet, Journal, Equity-Kurve. **Optionalität** ist typisiert und in der UI als leer/partiell/fehlerhaft erkennbar — ohne Abstürze bei fehlenden Daten.

## Gateway-Endpunkte (Lesen)

| Route                           | Payload (Kern)                                                                                          | Envelope              |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- | --------------------- |
| `GET /v1/paper/positions/open`  | `positions: PaperOpenPosition[]`                                                                        | `merge_read_envelope` |
| `GET /v1/paper/trades/recent`   | `trades`, `limit`                                                                                       | idem                  |
| `GET /v1/paper/metrics/summary` | `account \| null`, `fees_total_usdt`, `funding_total_usdt`, `equity_curve[]`, `account_ledger_recent[]` | idem                  |
| `GET /v1/paper/ledger/recent`   | `entries`, `limit`, optional `account_id`                                                               | idem                  |
| `GET /v1/paper/journal/recent`  | `events`, `limit`, optional `account_id`                                                                | idem                  |

Implementierung: `services/api-gateway/src/api_gateway/routes_paper_proxy.py`, Queries: `db_dashboard_queries.py` (Positionen, Trades, Metriken, Equity-Serie), `db_paper_reads.py` (Ledger, Journal).

## Equity-Kurve vs. Summary

- **Summary** (`account`, Gebühren, Funding): aus `paper.accounts` (erstes Konto), Aggregationen über `paper.fee_ledger` / `paper.funding_ledger`.
- **Equity-Kurve** (`fetch_equity_series`): kumulativ ab `initial_equity` des **ersten** Paper-Kontos über `learn.trade_evaluations` (sortiert nach `closed_ts_ms`). **Ohne Zeile in `paper.accounts`** liefert die API eine **leere** Kurve (keine erfundene 10k-Baseline — vermeidet Drift zur Summary).
- Mit Konto aber ohne abgeschlossene Evaluations: ein Punkt mit aktuellem `initial_equity`.

## Beispiel-Payloads (Auszug)

**Metriken (ok):**

```json
{
  "status": "ok",
  "message": null,
  "empty_state": false,
  "degradation_reason": null,
  "next_step": null,
  "account": {
    "account_id": "…",
    "initial_equity": 10000,
    "equity": 10042.5,
    "currency": "USDT"
  },
  "fees_total_usdt": 12.3,
  "funding_total_usdt": -0.5,
  "equity_curve": [{ "time_s": 1710000000, "equity": 10025.0 }],
  "account_ledger_recent": [
    {
      "entry_id": "…",
      "ts_ms": 1710000000000,
      "amount_usdt": "1000",
      "balance_after": "11000",
      "reason": "deposit_demo",
      "note": null,
      "meta": {}
    }
  ]
}
```

**Metriken (degradiert, DB fehlt) — stabile Keys wie im ok-Pfad:**

```json
{
  "status": "degraded",
  "account": null,
  "fees_total_usdt": 0,
  "funding_total_usdt": 0,
  "equity_curve": [],
  "account_ledger_recent": []
}
```

## Dashboard-Typen und Defaults

- `apps/dashboard/src/lib/types.ts`: `PaperOpenPosition`, `PaperTradeRow`, `PaperMetricsResponse`, `PaperLedgerEntry`, `PaperJournalEvent`, `PaperEquityPoint`.
- `apps/dashboard/src/lib/paper-response-defaults.ts`: leere Envelopes für alle Paper-Responses (kein `undefined` auf der Seite).
- `apps/dashboard/src/lib/paper-metrics-defaults.ts` re-exportiert `emptyPaperMetricsResponse` (Abwärtskompatibilität für Tests).

## UI-Recovery (`console/paper`)

- **Parallel-Ladung** mit `Promise.allSettled`: ein fehlgeschlagener Fetch blockiert nicht die übrigen Karten.
- **Totalausfall**: `PanelDataIssue` mit zusammengefasster Meldung.
- **Teilausfall**: Hinweisbox mit Liste der betroffenen Bereiche; übrige Daten bleiben sichtbar.
- **`PaperReadNotice`**: zeigt Gateway-`message` bei `degraded` oder leerem Zustand mit Text.
- **Equity-Chart**: eigener Leertext, wenn kein Konto und leere Kurve (`equityCurveNoAccount`).

## Tests / Checks

```powershell
cd apps/dashboard
pnpm check-types
pnpm test -- paper-response-defaults paper-metrics-defaults
```

Gateway-Änderungen: `fetch_equity_series` / `paper_metrics_summary` degradiert — bei Bedarf Integrationstests mit echter DB ergänzen.

## Bezug Handoff

- Daten- und Mandanten-Kontext: `docs/chatgpt_handoff/05_*`
- Nachweise: `docs/chatgpt_handoff/09_*`

## Offene Punkte

- `[FUTURE]` Mandanten-spezifische Paper-Konten in der öffentlichen Console klar von „shared demo“ trennen (Copy + API-Scope).
- `[TECHNICAL_DEBT]` Vollständiges Ledger nur über `GET /v1/paper/ledger/recent`; die Metrik-Route liefert nur ein Snippet (`account_ledger_recent`).
