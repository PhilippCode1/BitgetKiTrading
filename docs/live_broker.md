# Live-Broker (Control-Plane)

## Rolle

Der Dienst **`live-broker`** ist die **Exchange-Control-Plane** im Monorepo: private REST/WS, Order-Lifecycle, Reconcile mit der Boerse, Kill-Switches, Audit-Pfade und Shadow-/Live-Abgleich. Er ist **kein** Ersatz fuer Risk-Engine oder Signal-Engine; er setzt nur freigegebene Entscheidungen um bzw. blockiert sie bei Safety-Regeln.

**Trading-Kern** bleibt: deterministische Safety-Layer, Quant/ML, Risk-Engine, Uncertainty, harte Gating-Policy. **LLM** ist keine alleinige Handelsinstanz.

Der Live-Broker ist jetzt **family-aware**: Spot, Margin und Futures teilen sich dieselbe
Control-Plane, verwenden aber unterschiedliche Bitget-Endpoint-Profile und Guard-Rails.
Die direkte Service-API ist fuer produktionskritische Pfade ueber `INTERNAL_API_KEY`
haertbar; der bevorzugte Operator-Zugriff bleibt weiterhin der API-Gateway-Proxypfad.

**Architektur-Referenz:** `docs/adr/ADR-0001-bitget-market-universe-platform.md`

Der Broker darf sich im Zielzustand **nicht** auf lokale Einzelkonstanten fuer Symbol,
Product-Type oder Precision verlassen. Er konsumiert den zentralen Instrumentenkatalog
als Resolver-/Health-Quelle.

Zusaetzlich sitzt ein Shared-Metadatenservice ueber dem Katalog. Dieser liefert:

- Snapshot-Version
- Trading-/Subscribe-Status
- Session-/Delivery-/Maintenance-Zustand
- Preis-/Mengenpraezision
- min/max order size
- Hebel-Capabilities

## Ausfuehrungsmodi (global)

**Normativ:** `docs/execution_modes.md` (Modusmatrix, Guard-Rails, Operator-Kommandos).

Kurzfassung: `EXECUTION_MODE` + `SHADOW_TRADE_ENABLE` / `LIVE_TRADE_ENABLE` / `LIVE_BROKER_ENABLED` + `STRATEGY_EXEC_MODE`. Abgeleitete Sicht fuer Health/API: `BaseServiceSettings.execution_runtime_snapshot()`.

**Go-Live-Reihenfolge:** stabil shadow betreiben → Alerts/Observability gruen → explizites Live-Gate (ENV + operatives Freigabeprotokoll, siehe `docs/prod_runbook.md` und `docs/LaunchChecklist.md`).

**Institutioneller Ramp-Pfad:** `docs/shadow_burn_in_ramp.md` beschreibt die Reihenfolge
shadow-only → operator-gated mirror → evidenzbasierter Ausbau. Der Live-Broker setzt
die technischen Mirror-Gates bereits ueber `LIVE_REQUIRE_EXECUTION_BINDING`,
`LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN` und
`REQUIRE_SHADOW_MATCH_BEFORE_LIVE` um.

**Notfall / Safety-Schicht (Kill-Switch, Cancel-All, Emergency-Flatten, Safety-Latch):** `docs/emergency_runbook.md`.

## Leverage und 7x

- Erlaubter Hebel-Integerbereich: **7..75** (konfigurierbar ueber `RISK_ALLOWED_LEVERAGE_MIN`/`MAX`, Minimum ist verbindlich **7**).
- Mit `RISK_REQUIRE_7X_APPROVAL=true` gilt: ohne sauber freigegebenen **7x**-Fall → **`do_not_trade`** (Policy-Seite Signal/Risk; Live-Broker respektiert Signal-Caps).
- Exit-/Stop-Plaene laufen ueber die gemeinsame Stop-Budget-Kurve in `shared_py.exit_engine`: unhaltbare Kombinationen aus Hebel, Spread, Tiefe und Stop-Distanz werden im Preview blockiert, statt blind an die Boerse geschickt zu werden.
- Details zur Shadow/Live-Divergenz: `docs/shadow_live_divergence.md`.

## Marktfamilien

- **Futures**: `/api/v2/mix/*`, Funding/Open-Interest aktiv, `long`/`short`, `reduceOnly`, `productType`, `marginCoin`.
- **Spot**: `/api/v2/spot/*`, kein Short-Support im direkten Spot-Family-Pfad; Spot-Shorts werden im Spezialisten-/Risk-Pfad als `do_not_trade` geblockt.
- **Margin**: Spot-Market-Data plus Margin-Private-REST. `isolated` und `crossed` werden ueber `BITGET_MARGIN_ACCOUNT_MODE` unterschieden; order-spezifische Loan-Typen laufen ueber `BITGET_MARGIN_LOAN_TYPE`.

Der Live-Broker ist **nicht** Owner des Marktinventars. Er konsumiert den kanonischen
Instrumentvertrag und setzt nur die family-spezifischen Execution-Adapter um.

**Order-REST pro Instrument:** Private `place`/`cancel`/`modify`/`detail`-Pfade werden aus
`endpoint_profile_for` fuer die effektive `market_family` des Requests (inkl. Margin-Modus)
gewaehlt; die globale `MARKET_FAMILY`-ENV allein steuert nicht mehr den Submit-Pfad bei
gemischtem Universum.

**Governance (optional, Produktion empfohlen):** `LIVE_REQUIRE_EXECUTION_BINDING`,
`LIVE_REQUIRE_OPERATOR_RELEASE_FOR_LIVE_OPEN`, Journal-Tabelle `live.execution_journal`,
Operator-Route `POST /live-broker/executions/{id}/operator-release` — siehe
`services/live-broker/README.md` und Migration `570_live_orders_execution_governance.sql`.

**Modul-Mate-Kommerzgates (optional, DB):** `MODUL_MATE_GATE_ENFORCEMENT=true` erzwingt
vor jedem Exchange-Submit die Pruefung von `app.tenant_modul_mate_gates` gegen
`shared_py.product_policy` (Demo-API vs. Live-API). Dafuer sind `DATABASE_URL` und
Migration `604_modul_mate_execution_gates.sql` erforderlich; Tenant-ID per
`MODUL_MATE_GATE_TENANT_ID` (Default `default`). Self-Check: `python tools/modul_mate_selfcheck.py`.

Unbekanntes Instrument oder fehlende Katalogauflösung bedeutet im Broker:

- kein stilles Routing auf Defaults
- kein Order-Submit
- `blocked` / `validation` / `instrument_unknown`

Metadatenbezogene weitere Blocker:

- `instrument_session_not_tradeable`
- `instrument_open_session_restricted`
- `instrument_does_not_support_reduce_only`
- `order_size_below_minimum` / `order_size_above_maximum`
- `order_notional_below_minimum`

## Datenbank (Auszug)

Wesentliche Schemas unter `live.*` (Migrationen unter `infra/migrations/postgres/`):

- `live.orders`, `live.order_actions`, `live.fills` — Orderpfad und API-Spiegel
- `live.reconcile_snapshots` — periodischer Abgleich mit Exchange-Zustand (`details_json` inkl. Drift-Summary)
- `live.kill_switch_events` — Arm/Release, aktive Schalter fuer Monitor und Gateway
- `live.execution_decisions` — Entscheidungen inkl. Shadow-Live-Felder
- `live.audit_trails` — Safety-/Ops-Audit

## API und Dashboard

- Gateway (authentifizierter Read-Path): `/v1/live-broker/*` (Runtime, Orders, Fills, Kill-Switch, Decisions, Audit) — siehe `docs/api_gateway_security.md`.
- Operator-Dashboard: `/live-broker`, Cockpit `/ops` — siehe `docs/dashboard_operator.md`.
- Direkte Service-API: `/live-broker/*` bleibt nur fuer interne, explizit autorisierte Aufrufer gedacht (`X-Internal-Service-Key` bei gesetztem `INTERNAL_API_KEY`).

Der Runtime-/Gateway-Pfad spiegelt jetzt auch:

- Instrumentenkatalog-Health
- aktuelle Metadaten-Health
- zuletzt bekannte Instrumentmetadaten fuer Audit / Operator-Sicht

Die operator-gated Live-Ausfuehrung bleibt eine eigene Grenze: Analyse, Paper und
Learning duerfen autonom laufen; echte Order-Sends bleiben explizit freigabepflichtig.

## Betrieb

- **Reconcile:** bei wiederholtem `fail` oder hohem Drift Monitor-Alerts und Prometheus-Regeln pruefen (`docs/observability.md`). Erweiterte Recovery-Sicht: `docs/recovery_runbook.md` (Journal, fehlende Acks, WS-Stale, Exit-Plan-Restart). **Repo-Nachweise:** gleiches Dokument Abschnitt _Nachweise im Repo_; HTTP- und DB-Integration unter `tests/integration/test_http_stack_recovery.py` und `test_db_live_recovery_contracts.py`.
- **Execution-Guards (Preflight + Post-Preflight):** family-aware Katalog-Checks (`shared_py.bitget.metadata.preflight_order`), danach deterministische Guards fuer Market-Spread, Preset-Stop-Abstand, Reduce-only vs. Exchange-Position, Replace-Groesse. Konfiguration: `LIVE_PREFLIGHT_*`, `LIVE_EXECUTION_MAX_SPREAD_HALF_BPS_MARKET`, `LIVE_PRESET_STOP_*`, `LIVE_REQUIRE_EXCHANGE_POSITION_FOR_REDUCE_ONLY`, `LIVE_BLOCK_SUBMIT_ON_RECONCILE_*`. Alerts/Audit: `docs/emergency_runbook.md`.
- **Kill-Switch:** Scope/Reason in DB und Alerts; Freigabe nur nach Ursachenanalyse (`docs/prod_runbook.md`).
- **Health:** `GET /ready` am Live-Broker; Kette ueber Gateway `GET /v1/system/health`.
