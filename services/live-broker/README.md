# live-broker

Der Service `live-broker` ist das Runtime-Glied fuer Shadow-/Live-Execution im bestehenden Monorepo.

## Execution Controls

- `EXECUTION_MODE` ist die globale Wahrheit fuer `paper`, `shadow` und `live`.
- `STRATEGY_EXEC_MODE` steuert, ob validierte Candidates nur manuell freigegeben oder automatisch weiterverarbeitet werden.
- `SHADOW_TRADE_ENABLE` schaltet den Shadow-Pfad frei, ohne reale Orders an Bitget zu senden.
- `LIVE_TRADE_ENABLE` ist das Hard-Gate fuer echte Order-Sends und wirkt nur mit `EXECUTION_MODE=live`.

## Struktur

- `src/live_broker/config.py`: laedt gemeinsame Base-/Bitget-Settings und validiert die Service-Streams.
- `src/live_broker/exchange_client.py`: nutzt die gemeinsame Bitget-Konfiguration fuer REST-Probe und Order-Preview.
- `src/live_broker/private_rest.py`: implementiert private Bitget-REST-Auth, Signing, Serverzeit-Sync, Retry/Backoff und Circuit Breaker; Lese-Helfer fuer Order-/Fill-Historie und Set-Leverage (siehe Endpoint-Profil).
- `src/live_broker/control_plane/`: **Bitget Control-Plane** — Capability-Matrix je Marktfamilie, Gates vor Writes, sichere interne Read-/Operator-Mutationsrouten mit Audit. Doku: `docs/live_broker_control_plane.md`.
- `src/live_broker/execution/`: nimmt Execution-Intents an und persistiert Shadow-, Blocked- oder Live-Candidate-Entscheidungen.
- `src/live_broker/exits/`: verwaltet aktive Shared-Exit-Plaene, finalisiert
  Pending-Plaene aus Positions-Snapshots und loest gemeinsame TP-/SL-/Trail-
  Entscheidungen als reduce-only Orders aus.
- `src/live_broker/orders/`: fachliche Order-API fuer create, cancel, replace, query, reduce-only, Kill-Switch und Emergency-Flatten mit `clientOid`-Idempotenz.
- `src/live_broker/reconcile/`: erzeugt periodische Reconcile-Snapshots, vergleicht lokale Orders/Fills mit persistierten Exchange-Snapshots, reichert **Divergenz-Metriken** (fehlendes Exchange-Ack, Journal-Tail, Fill-Ledger vs. Status, Private-WS-Staleness) an und publiziert bei Degradation `events:system_alert`. Operatorische Details: `docs/recovery_runbook.md`.
- `src/live_broker/persistence/`: speichert Decisions, Orders, Order-Actions, Fills, Exchange-Snapshots, Safety-Actions, Kill-Switch-Events, Audit-Trails und Reconcile-Snapshots in Postgres.
- `src/live_broker/api/`: liefert Health-, Runtime- und Ops-Routen.
- `src/live_broker/worker.py`: konsumiert Signal- und Paper-Streams als regulaerer Redis-Consumer.

## Sichtbare Schnittstellen

- `signal-engine` -> `live-broker`: Redis `events:signal_created`
- `paper-broker` -> `live-broker`: Redis `events:trade_opened`, `events:trade_updated`, `events:trade_closed`
- `api-gateway` -> `live-broker`: DB-gestuetzte Runtime-/Decision-/Reference-Endpunkte unter `/v1/live-broker/*`
- `monitor-engine` -> `live-broker`: HTTP `/ready` plus `events:system_alert` bei Reconcile-Degradation
- interne Ops-/Order-API: `/live-broker/orders/create`, `/live-broker/orders/reduce-only`, `/live-broker/orders/cancel`, `/live-broker/orders/replace`, `/live-broker/orders/query`
- Operator-Freigabe (Live-Open-Gate, optional per ENV): `POST /live-broker/executions/{execution_id}/operator-release` (Internal Service Auth); Journal: `GET /live-broker/executions/{execution_id}/journal`
- Safety-/Operator-Pfade: `/live-broker/kill-switch/arm`, `/live-broker/kill-switch/release`, `/live-broker/orders/emergency-flatten`, `/live-broker/orders/timeouts/run`, `/live-broker/audit/recent`
- Control-Plane (nur Internal Auth): `GET /live-broker/control-plane/capability-matrix`, `POST /live-broker/control-plane/read/orders-history`, `POST /live-broker/control-plane/read/fill-history`, `POST /live-broker/control-plane/operator/set-leverage`

## Shadow-vs-Live-Abgleich (Prompt 28)

Fuer jeden Live-Intent berechnet der Broker eine **Shadow-Pfad-Simulation** und vergleicht sie mit dem Live-Pfad plus Signal-/Risk-Feldern. Ergebnis: `payload_json.shadow_live_divergence`. Mit `REQUIRE_SHADOW_MATCH_BEFORE_LIVE=true` werden `live_candidate_recorded`-Kandidaten bei harten Divergenzen in `blocked` / `shadow_live_divergence_gate` ueberfuehrt. Schwellen und Toleranzen: `docs/shadow_live_divergence.md`.

Der institutionelle Ramp-Pfad ist bewusst enger als die technische Maximalfaehigkeit
des Services: zuerst shadow-only, danach operator-gated mirror fuer eine enge
Startkohorte, danach evidenzbasierter Ausbau. Referenz: `docs/shadow_burn_in_ramp.md`.

## Mode-Verhalten

Wenn `EXECUTION_MODE=paper` ist, ignoriert der Service Signal-getriebene Trading-Entscheidungen und bleibt auf Read-/Ops-Pfade beschraenkt. Bei `EXECUTION_MODE=shadow` nutzt `live-broker` dieselbe fachliche Entscheidung wie im Live-Pfad, persistiert aber nur Shadow-Entscheidungen. Reale Orders koennen ausschliesslich mit `EXECUTION_MODE=live` und `LIVE_TRADE_ENABLE=true` entstehen; `paper` und `shadow` senden niemals versehentlich echte Orders.

## Signal-/Leverage-Kontext

- Seit Prompt 21 persistiert der Decision-Journal-Pfad fuer `signal_created`
  zusaetzlich `signal_trade_action`, `signal_allowed_leverage`,
  `signal_recommended_leverage`, `signal_leverage_policy_version` und
  `signal_leverage_cap_reasons_json`.
- Wenn das Upstream-Signal bereits `trade_action=do_not_trade` oder
  `allowed_leverage < 7` traegt, blockt `live-broker` den Candidate explizit mit
  einem fachlichen Decision-Reason statt nur auf `missing_execution_plan` zu
  fallen.
- Seit Prompt 22 berechnet `live-broker` vor der finalen Candidate-Entscheidung
  denselben Shared-Risk-Entscheid wie `paper-broker`. Dabei werden
  Signal-/Uncertainty-/Leverage-Felder aus `signal_created` mit
  Exchange-/Reconcile-Snapshots fuer Konto, offene Positionen, Margin-Usage,
  Daily-/Weekly-Drawdown und harte Snapshot-Staleness zusammengefuehrt.
- Der Shared-Risk-Trace wird als `risk_engine` in `live.execution_decisions`
  gespeichert, sodass Shadow-/Live-Candidates dieselben fachlichen Blockgruende
  wie Paper im Audit tragen.
- Seit Prompt 23 persistiert `live-broker` zusaetzlich eine `exit_preview`
  fuer Decision-Journale und verwaltet aktive `live.exit_plans`, damit Stop,
  Partial-TP, Break-Even und Trailing fachlich denselben Shared-Core wie Paper
  nutzen.

## Multi-Asset Orders und Governance

- **Family-aware REST:** `place_order` / `cancel_order` / `modify_order` / `get_order_detail` nutzen pro Request das `endpoint_profile_for(market_family, margin_account_mode)` aus `shared_py.bitget.instruments` (Spot, Margin isolated/crossed, Futures), nicht die globale Default-`MARKET_FAMILY` der Settings allein.
- **Order-Zeilen:** Migration `570_live_orders_execution_governance.sql` ergaenzt `live.orders` um `market_family`, `margin_account_mode`, `source_execution_decision_id` (FK auf `live.execution_decisions`).
- **Binding (optional):** `LIVE_REQUIRE_EXECUTION_BINDING=true` erzwingt fuer **Opening-Orders** (nicht `reduce_only`, kein `allow_safety_bypass`) ein gueltiges `source_execution_decision_id` mit `decision_action=live_candidate_recorded` und passendem Symbol.
- **Operator-Release (optional):** `LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN=true` erfordert zusaetzlich einen Eintrag in `live.execution_operator_releases` (via Ops-Route oben).
- **Demo vs. Produktion:** Bei `PRODUCTION=true` oder `APP_ENV=production` schlaegt `LiveBrokerSettings` fehl, wenn `BITGET_DEMO_ENABLED=true` — der Live-Broker darf dann nicht gegen Demo/Paper-REST laufen.

## Private Order Auth

Private REST-Aufrufe folgen der offiziellen Bitget-Signatur mit `ACCESS-SIGN`,
`ACCESS-TIMESTAMP`, `ACCESS-PASSPHRASE` und `locale`. Fuer die Korrelation zwischen
internen Orders und Bitget-Orders wird `clientOid` deterministisch aus
`ORDER_IDEMPOTENCY_PREFIX + internal_order_id` abgeleitet.

## Private WebSocket

Der `live-broker` lauscht ueber einen dedizierten, authentifizierten WebSocket-Client (`BitgetPrivateWsClient`) auf die Kanaele `orders`, `positions`, `fill` und `account`. Die eingehenden Nachrichten werden auf `NormalizedPrivateEvent`s abgebildet und ueber eine thread-sichere Queue an den Worker uebergeben. Dort persistiert `ExchangeStateSyncService` Order-Lifecycle-Updates, Fills und gruppierte Exchange-Snapshots pro Symbol bzw. Margin-Coin. Der Client verfuegt ueber Reconnect, Backoff und Ping/Pong Keep-Alive gemaess Bitget-Dokumentation.

## Journal und Reconcile

- `live.execution_journal` ergaenzt die Kette Plan (`execution_decision`) → optional `operator_release` → `order_submit` / `order_exchange_ack` (weitere Phasen: `fill`, `reconcile`, `close` fuer Folgearbeiten).
- `live.orders` + `live.order_actions` bilden das lokale Order-Journal fuer Submission, Cancel, Replace und Query.
- `live.exit_plans` speichert aktive/pending Exit-Plaene pro Trade-Root-Order,
  inklusive Stop-/TP-Zustand, Runner/Break-Even-Fortschritt und letztem
  Decision-/Market-Snapshot.
- `live.fills` speichert echte Fill-Events aus dem privaten Bitget-Stream idempotent ueber `exchange_trade_id`.
- `live.exchange_snapshots` speichert die letzte bekannte Exchange-Wahrheit fuer Orders, Positionen und Account-Zustaende.
- Der Reconcile-Loop vergleicht lokale aktive Orders sowie aus Fills abgeleitete Netto-Exposures mit der letzten Exchange-Wahrheit und markiert Drift in `live.reconcile_snapshots.details_json`.
- Nach Restart kann der Worker offene Orders, letzte Positions-Snapshots, Account-Snapshots und Fill-Historie wieder aus Postgres rekonstruieren.

## Gemeinsame Exit-Logik

- Open-Orders mit Stop-/TP-Preset werden vor Submission gegen Shared-Risk und
  Leverage validiert; widerspruechliche Exit-Parameter blocken bereits den
  Order-Call.
- Replace aktualisiert denselben Root-Trade-Exit-Plan statt einen separaten
  Sonderpfad aufzubauen; ein Cancel verwirft Pending-Plaene nur dann, wenn noch
  keine offene Position aktiv ist.
- Der Worker wertet aktive Exit-Plaene pro Reconcile-Takt gegen aktuelle
  Marktpreise aus und sendet Exit-Aktionen ausschliesslich als `reduce-only`
  Market-Orders.
- Exit-Gruende, Triggerpreise, Runner-Trail-Updates und Closing-Fortschritt
  werden ueber `live.audit_trails` und `live.exit_plans.last_decision_json`
  nachvollziehbar gespeichert.

## Safety Controls

- Kill-Switches sind auf Service-, Account- und Trade-Ebene modelliert und werden in Postgres persistiert.
- Trade-Kill-Switches werden auf die gesamte Replace-Kette eines Trades normalisiert, damit ein nachgelagerter Replace den Switch nicht umgehen kann.
- Ein aktiver Kill-Switch blockiert normale Order-Sends, laesst aber Safety-Aktionen wie `cancel`, `reduce-only` und `emergency flatten` weiter zu.
- `cancel` und `query` koennen auch exchange-only Orders ueber `orderId` oder `clientOid` aufloesen, wenn der lokale Sync kurz hinterherhaengt.
- `LIVE_ORDER_TIMEOUT_SEC` erzwingt einen echten Timeout-Cancel-Pfad fuer haengende Live-Orders; lokal wird der Status danach als `timed_out` markiert.
- `emergency flatten` arbeitet priorisiert, versucht offene Orders zuerst bestmoeglich zu raeumen und kann Side/Size bei Bedarf aus den letzten Positions-Snapshots ableiten.
- Safety-Aktionen werden als Audit-Trails, Kill-Switch-Events und `live.order_actions` gespeichert und bei kritischen Pfaden ueber `events:system_alert` sichtbar gemacht.
