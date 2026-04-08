# Dashboard-Seiten (Prompt 26)

## Übersicht

| Route                        | Seite                 | Datenquelle (api-gateway)                                                                                                                                            |
| ---------------------------- | --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/terminal`                  | Live-Terminal         | `GET /v1/live/state`, SSE `/v1/live/stream`                                                                                                                          |
| `/signals`                   | Signal Center         | `GET /v1/signals/recent`, `GET /v1/signals/facets`                                                                                                                   |
| `/signals/[id]`              | Signal-Detail         | `GET /v1/signals/{id}`, `GET /v1/signals/{id}/explain`                                                                                                               |
| `/paper`                     | Paper (Referenzbuch)  | `GET /v1/paper/positions/open`, `.../trades/recent`, `.../metrics/summary`                                                                                           |
| `/live-broker`               | Live-Broker Ops       | `GET /v1/live-broker/runtime`, `.../decisions/recent`, `.../orders/recent`, `.../fills/recent`, `.../orders/actions/recent`, `.../kill-switch/*`, `.../audit/recent` |
| `/live-broker/forensic/[id]` | Trade-Forensik        | `GET /v1/live-broker/executions/{execution_id}/forensic-timeline`                                                                                                    |
| `/news`                      | News Center           | `GET /v1/news/scored`                                                                                                                                                |
| `/news/[id]`                 | News-Detail           | `GET /v1/news/{id}`                                                                                                                                                  |
| `/strategies`                | Strategy Lab          | `GET /v1/registry/strategies`                                                                                                                                        |
| `/strategies/[id]`           | Strategie-Detail      | `GET /v1/registry/strategies/{id}`, Status: `GET .../{id}/status` (in Detail enthalten)                                                                              |
| `/learning`                  | Learning Board        | `GET /v1/learning/metrics/strategies`, `/patterns/top`, `/recommendations/recent`, `/drift/recent`, `/drift/online-state`, `GET /v1/backtests/runs`                  |
| `/health`                    | Model / System Health | `GET /v1/system/health`, `GET /v1/monitor/alerts/open`, `GET /v1/alerts/outbox/recent`                                                                               |
| `/admin`                     | Admin & Rules         | `GET /v1/admin/rules`, optional `POST /v1/admin/rules` (Header `X-Admin-Token`)                                                                                      |

Strategie-Statuswechsel (optional): `POST /v1/admin/strategy-status` mit Token.

## `NEXT_PUBLIC_*` und Sicherheit

- Alle `NEXT_PUBLIC_`-Variablen werden beim **Next.js-Build** in das Client-Bundle **inlined** und sind im Browser lesbar.
- **Niemals** API-Keys, `ADMIN_TOKEN` oder andere Secrets in `NEXT_PUBLIC_*` legen.
- Admin-Token nur serverseitig (`ADMIN_TOKEN` im api-gateway); die UI speichert ein lokales Token optional in `sessionStorage` und sendet es nur im Header `X-Admin-Token`.

## Live-Datenfrequenz

- Kerzen und SSE-Events können bei aktivem Markt **mehrfach pro Sekunde** ankommen; das Live-Terminal coalesct (Gateway) und nutzt Polling-Fallback.
- Aggregations-Seiten (Signals, News, …) laden bei **Seitenaufruf** per Server-Fetch; für Echtzeit-Erweiterungen können später Client-Refetches ergänzt werden.
- `/live-broker` ist die Operator-Sicht fuer Kill-Switch-, Timeout-, Flatten-, Audit-, Fill- und Order-Action-Trails des Live-Brokers.
- `/terminal` zeigt seit Prompt 14 zusaetzlich den letzten Cost-/Microstructure-
  Snapshot (`latest_feature`) mit Spread, Execution-Cost, Funding, OI sowie
  Quellen/Ages aus `features.candle_features`.
- `/terminal` zeigt seit Prompt 16 im Signal-Panel auch `market_regime`,
  `regime_bias`, `regime_confidence_0_1` und die wichtigsten Regime-Fakten des
  letzten Signals.
- `/terminal` kann Fokus-Symbole aus Watchlist-/Universumsprofilen umschalten; es fuehrt keine clientseitigen Secrets oder Admin-Token.
- `/terminal`, `/signals` und `/signals/[id]` zeigen seit Prompt 17 zusaetzlich
  das kalibrierte Meta-Label `take_trade_prob` sowie die zugehoerige
  `take_trade_model_version`, damit Heuristik (`probability_0_1`) und gelerntes
  Trade-Gating im UI getrennt auditierbar bleiben.
- Seit Prompt 18 zeigen `/terminal` und `/signals/[id]` ausserdem die drei
  Bps-Projektionen `expected_return_bps`, `expected_mae_bps` und
  `expected_mfe_bps`; `/signals` fuehrt `expected_return_bps` in der Tabelle.
- Seit Prompt 19 zeigen `/terminal`, `/signals` und `/signals/[id]` zusaetzlich
  `model_uncertainty_0_1` und `trade_action`; `/terminal` und `/signals/[id]`
  markieren ausserdem `model_ood_alert` und `abstention_reasons_json`, damit
  `do_not_trade`-Entscheidungen im UI nachvollziehbar bleiben.
- Seit Prompt 21 zeigen `/terminal`, `/signals` und `/signals/[id]` zusaetzlich
  `allowed_leverage`, `recommended_leverage` und `leverage_cap_reasons_json`.
- `/signals` und `/signals/[id]` fuehren nun ausserdem `specialist_router_id`,
  `exit_family_effective_primary`, Instrument-Metadaten, den letzten
  Execution-/Mirror-/Approval-Status sowie Telegram-/Outbox-Linking.
- `/paper` zeigt bei offenen und geschlossenen Trades jetzt auch den finalen
  Execution-Leverage samt bindender Cap-Namen aus
  `paper.positions.meta.leverage_allocator`.
- `/live-broker` fuehrt eine eigene Decision-Tabelle mit
  `signal_allowed_leverage`, `signal_recommended_leverage`,
  `signal_trade_action`, Mirror-/Release-Status und den Cap-Gruenden aus dem Leverage-Allocator.
- `/health` zeigt neben Gateway-/Service-Health jetzt auch offene Monitor-Alerts, Alert-Outbox-Status sowie eine kompakte Live-Broker-Ops-Zusammenfassung.
- `/ops` trennt Fokus-Instrument (Symbol/TF/Family) von globalen Operator-Queues: Approval Queue, Live Mirrors, Divergenz, Model Slots, Drift State und Paper-vs-Live Outcome.

## DB / Migrationen

- `app.admin_rules`: Migration `210_admin_rules_store.sql` — Default-RuleSet `default` für die Admin-Ansicht.

## Gateway: Service-Health

- HTTP-Checks optional über Env: `HEALTH_URL_LEARNING_ENGINE`, `HEALTH_URL_PAPER_BROKER`, `HEALTH_URL_*` für weitere Services.
- Freshness-Symbol: `DASHBOARD_DEFAULT_SYMBOL` oder `NEXT_PUBLIC_DEFAULT_SYMBOL`, sonst erster Watchlist-/Universe-Eintrag; kein impliziter BTCUSDT-Fallback.
