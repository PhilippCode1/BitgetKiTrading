# 23 — SSE und Polling: Live-Terminal-Zuverlaessigkeit

## Pflichtgrundlagen

- **Datei 05:** `docs/chatgpt_handoff/05_DATENFLUSS_BITGET_CHARTS_UND_PIPELINE.md` — `GET /v1/live/stream` (Redis-Streams), Polling-Fallback.
- **Datei 08:** `docs/chatgpt_handoff/08_FEHLER_ALERTS_UND_ROOT_CAUSE_DOSSIER.md` — ehrliche Zustaende statt stiller Ausfaelle; Hinweise fuer Betrieb.

## Architektur (kurz)

| Schicht           | Pfad                                                            | Rolle                                                                                                           |
| ----------------- | --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| **Browser**       | `EventSource` → `/api/dashboard/live/stream?symbol=&timeframe=` | Same-Origin SSE; **kein** Gateway-JWT im Client                                                                 |
| **Dashboard BFF** | `apps/dashboard/src/app/api/dashboard/live/stream/route.ts`     | Haengt `Authorization` an `GET /v1/live/stream`; `timeoutMs: null`; leitet Stream durch                         |
| **API-Gateway**   | `GET /v1/live/stream`                                           | `LIVE_SSE_ENABLED`, `REDIS_URL`, `XREAD` auf `LIVE_SSE_STREAMS`; **Ping-Events** im Abstand `LIVE_SSE_PING_SEC` |
| **Polling**       | `GET /v1/live/state`                                            | HTTP-Aggregat; Intervall `NEXT_PUBLIC_LIVE_POLL_INTERVAL_MS` (Default 2000 ms)                                  |

## Gateway-Vertrag

- **503** wenn `LIVE_SSE_ENABLED=false` oder `REDIS_URL` fehlt — Body-Text z. B. `SSE disabled (LIVE_SSE_ENABLED=false)`.
- **Auth:** `require_live_stream_access` (SSE-Ticket / Policy laut Gateway).
- **Oeffentliche SSE-Hinweise** (ohne Secrets): `GET /v1/meta/surface` → `live_terminal.sse_enabled`, `live_terminal.sse_ping_sec` — vom **Terminal-Server** beim SSR gelesen (`fetchLiveTerminalServerMeta`).

## Dashboard-Client-Vertrag

### Transport-Trennung

1. **SSE aus (Gateway-Meta `sse_enabled: false`):** Kein `EventSource` — Zustand **`inactive`**, UI: „kein Echtzeit-Push … HTTP alle {n}s“, Polling **immer** aktiv (wenn nicht eingefroren).
2. **SSE versucht (Meta true oder unbekannt):** `startManagedLiveEventSource` mit exponentiellem Backoff (`computeReconnectDelayMs`), max. **22** Fehlversuche ohne erfolgreiches `onopen`, danach **`given_up`** — kein endloser Reconnect; Polling uebernimmt.
3. **SSE offen:** Polling-Intervall fuer Live-State **aus**; Aktualisierung durch Events + kurzes REST-Backfill nach Connect und bei Coalesce.
4. **Ping / Stale:** Wenn laenger als **max(45 s, 3 × sse_ping_sec)** kein Ping, Banner „ruhig … HTTP alle {n}s“; Polling laeuft parallel solange Verbindung nicht `open`.

### BFF-Stream

- Upstream-Fehler: Status und Body werden durchgereicht; Browser-`EventSource` sieht keinen HTTP-Status — daher Meta-Fallback und Reconnect-Limit zentral im Client.

## Reconnect- und Fallback-Vertrag (final)

| Phase            | Verhalten                                                                                    |
| ---------------- | -------------------------------------------------------------------------------------------- |
| **connecting**   | Erster oder neuer Verbindungsaufbau                                                          |
| **open**         | Push aktiv; Ping erwartet gemaess Gateway-Ping-Sekunden                                      |
| **reconnecting** | Nach `onerror`: Backoff, dann erneuter Connect                                               |
| **given_up**     | Nach `maxReconnectAttempts` (Default 22): **kein** weiterer Reconnect; nur noch HTTP-Polling |
| **inactive**     | Gateway meldet SSE aus: **kein** EventSource                                                 |
| **Polling**      | `setInterval(reload, livePollIntervalMs)` wenn `!frozen && sseConnection !== "open"`         |

## Nachweise

**Gateway (laufender Stack):**

```bash
curl -sS "$API_GATEWAY_URL/v1/meta/surface" | jq .live_terminal
# SSE (Auth ggf. Cookie/Ticket — je nach Gateway-Policy):
curl -N -H "Accept: text/event-stream" -H "Authorization: Bearer …" \
  "$API_GATEWAY_URL/v1/live/stream?symbol=BTCUSDT&timeframe=1m" | head
```

**BFF (lokal, eingeloggte Session / Server-ENV):**

Browser: DevTools → Netzwerk → `/api/dashboard/live/stream` (EventStream).

**Tests:**

```bash
cd apps/dashboard && pnpm exec jest src/lib/__tests__/live-event-source.test.ts
pytest tests/unit/api_gateway/test_public_meta.py -q
```

## Dokumentierter Fallback-Fall

**Szenario:** `LIVE_SSE_ENABLED=false` am Gateway.

1. `GET /v1/meta/surface` liefert `live_terminal.sse_enabled: false`.
2. Terminal-SSR laedt diese Meta und uebergibt sie an `LiveTerminalClient`.
3. Client startet **keinen** `EventSource`; zeigt Status „kein Echtzeit-Push …“ und Hinweiszeile zu HTTP-Polling alle **n** Sekunden (`NEXT_PUBLIC_LIVE_POLL_INTERVAL_MS`).
4. Kein Reconnect-Chaos — technisch sauber getrennt von „SSE versucht aber kaputt“.

**Szenario:** Redis down, SSE enabled.

1. EventSource schlaegt wiederholt fehl.
2. Nach 22 Versuchen: `given_up`, Hinweis zu HTTP-Polling und Logs/edge-status.

## Code-Referenzen

- `services/api-gateway/src/api_gateway/routes_live.py` — `/stream`, `/state`
- `services/api-gateway/src/api_gateway/routes_public_meta.py` — `live_terminal`
- `apps/dashboard/src/app/api/dashboard/live/stream/route.ts`
- `apps/dashboard/src/lib/live-event-source.ts`
- `apps/dashboard/src/lib/live-terminal-server-meta.ts`
- `apps/dashboard/src/components/live/LiveTerminalClient.tsx`
- `apps/dashboard/src/lib/sse.ts` — `buildLiveStreamUrl`

## Offene Punkte

- `[FUTURE]` Expliziter **HEAD**- oder **JSON-Probe** am BFF fuer „SSE erreichbar“ ohne EventSource-Spam (derzeit Meta + Give-up).
- `[TECHNICAL_DEBT]` `require_live_stream_access` vs. Operator-JWT — in Datei 04/Security-Doku verankert; hier nicht geaendert.
