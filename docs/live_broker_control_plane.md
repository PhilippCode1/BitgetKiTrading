# Live-Broker Bitget Control-Plane

**Matrix-Version:** `bitget-control-plane-v1` (`CONTROL_PLANE_MATRIX_VERSION` in `live_broker/control_plane/capabilities.py`).

## Ziel

Alle relevanten Bitget-Lese-/Schreibpfade laufen ueber eine **explizite Capability-Matrix** je `BitgetEndpointProfile` (Family + Margin-Modus). Nicht unterstuetzte Kombinationen liefern **`execution_disabled`** mit Begruendung — keine stillschweigenden Fehlzugriffe.

## Family-Scope (kurz)

| Kategorie                     | Futures (USDT-M etc.) | Spot                         | Margin isolated | Margin crossed                         |
| ----------------------------- | --------------------- | ---------------------------- | --------------- | -------------------------------------- |
| Instrument Discovery (public) | ja                    | ja                           | ja              | ja                                     |
| Account / Balance             | ja (mix account)      | ja                           | ja              | ja                                     |
| Positionen (dediziert)        | ja                    | nein (nur implizit)          | nein            | nein                                   |
| Offene Orders                 | ja                    | ja                           | ja              | nein (kein Open-Orders-Pfad im Profil) |
| Order-Historie REST           | ja                    | ja                           | nein\*          | nein\*                                 |
| Fill-Historie REST            | ja                    | ja                           | nein\*          | nein\*                                 |
| Order create / cancel         | ja                    | ja                           | ja              | ja                                     |
| Replace                       | ja                    | nein                         | nein            | nein                                   |
| Cancel-All                    | ja                    | nein                         | nein            | nein                                   |
| Reduce-only                   | ja                    | nein                         | nein            | nein                                   |
| Leverage set (REST)           | ja                    | nein                         | nein\*          | nein\*                                 |
| Private WS                    | ja                    | nein\*\*                     | MARGIN          | MARGIN                                 |
| REST-Reconcile-Snapshot       | ja                    | ja (ohne Positions-Endpoint) | ja              | eingeschraenkt                         |

\*Endpunkte im Profil nicht gesetzt → Matrix markiert `execution_disabled` bis verifizierte Pfade nachgezogen werden.  
\*\*Spot-Profil ohne `private_ws_inst_type` → Kategorie `private_ws` in der Matrix disabled (oertliche WS-Strategie kann davon abweichen).

## API (nur Internal Service Auth)

- `GET /live-broker/control-plane/capability-matrix` — volle Matrix fuer die **laufende** `BITGET_MARKET_FAMILY` / Margin-Konfiguration.
- `POST /live-broker/control-plane/read/orders-history` — historische Orders (wenn Kategorie supported).
- `POST /live-broker/control-plane/read/fill-history` — Fill-Historie (wenn supported).
- `POST /live-broker/control-plane/operator/set-leverage` — Hebel setzen (nur wenn `leverage_config` supported und `LIVE_TRADE_ENABLE` an); erfordert wie alle Writes **keinen** oeffentlichen Zugang, nur interne Auth.

Request-Bodies: `ControlPlaneReadHistoryRequest` / `ControlPlaneSetLeverageRequest` mit optionalem **`operator_jti`** und Audit-Notiz fuer Forensik.

## Schreibpfade (Order-Service)

Vor Exchange-Calls: `assert_write_capability` fuer `order_create`, `reduce_only`, `order_replace`, `order_cancel`, `cancel_all`. Kill-Switch **Cancel-All** ueberspringt den Exchange-Call, wenn `cancel_all` fuer die Family disabled ist, und macht weiterhin **lokales** Order-Matching.

## Resilienz (bestehend + ergaenzt)

- **Idempotenz / clientOid:** unveraendert im Order-Service.
- **Retry / Backoff / Circuit Breaker:** `BitgetPrivateRestClient._private_request`.
- **Failure Classes:** `BitgetRestError` + HTTP-Mapping in `routes_ops._http_status_for_classification` (inkl. `operator_intervention` → 403).
- **Dead-Letter-Audit:** `live.audit_trails` mit `category=exchange_write_dead_letter` bei festen Exchange-Failure-Klassen nach fehlgeschlagenem Write; Control-Plane-Write `set_leverage` nutzt zusaetzlich `exchange_write_dead_letter` bei nicht-retryable Fehlern.
- **Safety-Latch / Kill-Switch:** unveraendert zentral im Order-Service.

## Paper / Shadow / Live

**Gleicher fachlicher Entscheidungs-Input** (Signal/Snapshot) bleibt ausserhalb des Live-Brokers; die **Ausfuehrung** ist nur auf dem Live-Broker an die Bitget-Control-Plane und Exchange-Truth gebunden.
