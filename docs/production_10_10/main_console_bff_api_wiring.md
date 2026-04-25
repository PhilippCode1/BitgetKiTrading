# Main Console BFF/API Wiring

## 1) Zielbild

Die private Main Console von `bitget-btc-ai` zeigt Philipp fuer jede zentrale
Karte klar, welche Datenquelle genutzt wird, ob die Anzeige `loading`, `ready`,
`empty`, `degraded`, `error` oder `unavailable` ist und ob der Zustand einen
Live-Blocker betrifft. Keine Karte darf ohne deutschen Fehler-, Lade- oder Empty
State wirken.

## 2) Datenfluss

Main Console -> Dashboard-BFF -> API-Gateway -> Services:

- UI-Komponenten unter `apps/dashboard/src/app/(operator)/console` und
  `apps/dashboard/src/components`.
- BFF-Route bevorzugt `/api/dashboard/gateway/v1/...`; Spezial-BFFs bleiben
  unter `/api/dashboard/...`.
- Gateway/API-Route unter `/v1/...`.
- Service-Quelle ist der jeweilige Backend-Service oder ein dokumentierter
  sicherer `unavailable`-/Demo-Adapter.

Browser-Regel: Der Browser sieht keine Gateway-JWTs, OpenAI-Keys, Bitget-Keys,
Telegram-Tokens, DB-/Redis-Secrets oder interne Service-Tokens.

## 3) Statusmodell

- `loading`: Daten werden geladen; UI zeigt deutschen Ladehinweis.
- `ready`: echte Datenquelle antwortet und Anzeige ist nutzbar.
- `empty`: Quelle antwortet, aber es gibt noch keine Eintraege.
- `degraded`: Teilquelle fehlt, UI bleibt nutzbar und nennt die fehlende Quelle.
- `error`: Fehler wurde abgefangen; UI zeigt deutsche, handlungsorientierte Meldung.
- `unavailable`: echte Integration fehlt oder Backend ist nicht erreichbar; Live bleibt blockiert, falls live-relevant.

## 4) Pflichtkarten

Jede Pflichtkarte fuehrt zusaetzlich den Datenmodus: `echt`, `demo-markiert` oder `unavailable`.

| Bereich | UI-Komponente oder Route | BFF-Route | Gateway/API-Route | Service-Quelle | Ladezustand | Fehlerzustand | Empty State | Live-Relevanz | Deutscher UI-Text |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Systemzustand | `/console`, `/console/health`, `HealthGrid`, `LiveDataSituationBar` | `/api/dashboard/gateway/v1/system/health`, `/api/dashboard/edge-status` | `/v1/system/health` | API-Gateway, Monitor, alle Health-Probes | Loading: Health-Snapshot wird geladen | Error: Systemzustand konnte nicht geladen werden | Empty: Noch kein Health-Snapshot vorhanden | Ja, blockiert Go/No-Go bei fehlender Health | `Systemzustand wird geladen`, `Systemzustand nicht erreichbar` |
| Bitget Readiness | `/console/health`, `/console/live-broker`, Bitget Panel | `/api/dashboard/gateway/v1/live-broker/bitget/readiness` oder Health-Envelope | `/v1/live-broker/bitget/readiness` | Live-Broker, Bitget REST/WebSocket-Probes | Loading: Bitget-Pruefung laeuft | Error: Bitget-Readiness konnte nicht geladen werden | Empty: Noch keine Bitget-Diagnose geschrieben | Ja, Live ohne Exchange-Health blockiert | `Bitget nicht trade-ready`, `Keine Bitget-Diagnose vorhanden` |
| Asset Universe | `/console/market-universe`, `MarketCapabilityMatrixTable` | `/api/dashboard/gateway/v1/market/universe/status` | `/v1/market/universe/status` | API-Gateway, Instrument-Catalog, Bitget Discovery | Loading: Marktuniversum wird geladen | Error: Marktuniversum konnte nicht geladen werden | Empty: Keine Assets im aktuellen Snapshot | Ja, unbekannte Assets blockieren Live | `Asset-Universum nicht verfuegbar` |
| Asset Live Eligibility | `/console/market-universe`, `/console/capabilities` | `/api/dashboard/gateway/v1/market/universe/status` | `/v1/market/universe/status` | Instrument-Catalog, Asset-Governance, Risk-Tier-Gates | Loading: Live-Freigaben werden geladen | Error: Live-Freigaben konnten nicht geladen werden | Empty: Keine live-freigegebenen Assets | Ja, fehlende Eligibility blockiert Live | `Kein Asset ist live freigegeben` |
| Market Data Quality | `/console/market-universe`, Chart-Sektion | `/api/dashboard/gateway/v1/market/universe/status`, `/api/dashboard/gateway/v1/live/state` | `/v1/market/universe/status`, `/v1/live/state` | Market-Stream, Feature-Engine, Data-Quality-Report | Loading: Datenqualitaet wird geladen | Error: Datenqualitaet konnte nicht geladen werden | Empty: Keine Qualitaetsbewertung vorhanden | Ja, stale/invalid Daten blockieren Live | `Datenqualitaet fehlt oder ist zu alt` |
| Signals | `/console/signals`, `/console/signals/[id]` | `/api/dashboard/gateway/v1/signals/recent`, `/api/dashboard/gateway/v1/signals/{id}` | `/v1/signals/recent`, `/v1/signals/{id}` | Signal-Engine, Redis/DB Signal Store | Loading: Signale werden geladen | Error: Signale konnten nicht geladen werden | Empty: Noch keine Signale vorhanden | Ja, fehlende/alte Signale erzeugen no-trade | `Keine Signale im aktuellen Fenster` |
| KI-Erklaerung | `AssistLayerPanel`, `SituationAiExplainPanel`, `/api/dashboard/llm/operator-explain` | `/api/dashboard/llm/operator-explain`, `/api/dashboard/llm/strategy-signal-explain` | Gateway-Kontext plus LLM-Orchestrator intern | LLM-Orchestrator, Gateway-Kontext, keine Browser-Secrets | Loading: KI-Erklaerung wird erstellt | Error: KI-Erklaerung konnte nicht erstellt werden | Empty: Keine Faktenbasis fuer KI-Erklaerung | Nein fuer Live-Freigabe; nur Erklaerhilfe | `KI-Erklaerung derzeit nicht verfuegbar` |
| Risk Governor | `/console/ops`, Health/Risk Panels | `/api/dashboard/gateway/v1/risk/state` oder `/api/dashboard/gateway/v1/system/health` | `/v1/risk/state`, `/v1/system/health` | Risk-Governor, API-Gateway Health Envelope | Loading: Risk-Governor wird geladen | Error: Risk-Governor konnte nicht geladen werden | Empty: Keine Risk-Entscheidung vorhanden | Ja, Risk-Hard-Gate blockiert Live | `Risk-Governor blockiert oder fehlt` |
| Portfolio Risk | `/console/ops`, `/console/paper` | `/api/dashboard/gateway/v1/portfolio/risk`, `/api/dashboard/gateway/v1/paper/metrics` | `/v1/portfolio/risk`, `/v1/paper/metrics` | Risk-Governor, Paper-Broker, Portfolio Store | Loading: Portfolio-Risiko wird geladen | Error: Portfolio-Risiko konnte nicht geladen werden | Empty: Keine Positionen oder Metriken vorhanden | Ja, Exposure/Drawdown blockiert Live | `Keine Portfolio-Risiko-Daten vorhanden` |
| Live-Broker | `/console/live-broker` | `/api/dashboard/gateway/v1/live-broker/runtime`, weitere Live-Broker-Leser | `/v1/live-broker/runtime`, `/v1/live-broker/orders`, `/v1/live-broker/fills` | Live-Broker, Redis Streams, Audit Store | Loading: Live-Broker-Sektionen werden geladen | Error: Live-Broker-Daten konnten nicht geladen werden | Empty: Keine Live-Broker-Ereignisse | Ja, Live-Broker muss enabled/readiness-ok sein | `Live-Broker-Abschnitt nicht verfuegbar` |
| Reconcile | `/console/live-broker`, `/console/shadow-live` | `/api/dashboard/gateway/v1/live-broker/reconcile/latest` oder Runtime Envelope | `/v1/live-broker/reconcile/latest` | Live-Broker Reconcile, Exchange Truth, Audit Store | Loading: Reconcile wird geladen | Error: Reconcile konnte nicht geladen werden | Empty: Noch kein Reconcile-Lauf vorhanden | Ja, ungeklaerte Divergenz blockiert Live | `Kein Reconcile-Nachweis vorhanden` |
| Kill-Switch | `/console/live-broker`, `TerminalSafetyHaltOverlay` | `/api/dashboard/gateway/v1/live-broker/kill-switch/active`, `/events` | `/v1/live-broker/kill-switch/active`, `/v1/live-broker/kill-switch/events` | Live-Broker Safety Store | Loading: Kill-Switch wird geladen | Error: Kill-Switch-Status konnte nicht geladen werden | Empty: Keine aktiven Kill-Switches | Ja, aktive Schalter blockieren Live | `Aktiver Kill-Switch sichtbar` |
| Safety-Latch | `/console/live-broker`, `/console/health` | `/api/dashboard/gateway/v1/system/health`, `/api/dashboard/gateway/v1/live-broker/runtime` | `/v1/system/health`, `/v1/live-broker/runtime` | Gateway Safety-Latch, Live-Broker Runtime | Loading: Safety-Latch wird geladen | Error: Safety-Latch konnte nicht geladen werden | Empty: Kein Latch-Ereignis vorhanden | Ja, aktiver Latch blockiert Live | `Safety-Latch aktiv oder unbekannt` |
| Shadow Burn-in | `/console/shadow-live` | `/api/dashboard/gateway/v1/live/state`, `/api/dashboard/gateway/v1/shadow/burn-in` | `/v1/live/state`, `/v1/shadow/burn-in` | Paper-Broker, Live-Broker, Redis Shadow-Match | Loading: Shadow-Burn-in wird geladen | Error: Shadow-Burn-in konnte nicht geladen werden | Empty: Noch keine Shadow-Vergleiche | Ja, fehlender Shadow-Match blockiert Live | `Shadow-Match fehlt` |
| Restore/Safety Evidence | `/console/self-healing`, `/console/diagnostics`, Operator Report | `/api/dashboard/self-healing/snapshot`, `/api/dashboard/health/operator-report` | `/v1/system/health`, Report-Renderer | Monitor, Self-Healing Snapshot, Evidence Store | Loading: Evidence wird geladen | Error: Evidence konnte nicht geladen werden | Empty: Noch kein Restore-/Safety-Nachweis | Ja fuer Release-Go/No-Go | `Kein Restore-Nachweis vorhanden` |
| Alerts | `/console/admin`, `/console/health`, Alert Panels | `/api/dashboard/gateway/v1/monitor/alerts/open` | `/v1/monitor/alerts/open` | Monitor-Engine, Alert-Engine | Loading: Alerts werden geladen | Error: Alerts konnten nicht geladen werden | Empty: Keine offenen Alerts | Ja, offene P0/P1 blockieren Release/Live | `Keine offenen Alerts` |
| Reports | `/console/usage`, `/api/dashboard/health/operator-report` | `/api/dashboard/health/operator-report`, `/api/dashboard/gateway/v1/reports/*` | `/v1/reports/*`, PDF-Report-Route | API-Gateway, Report Renderer, Audit/Evidence Store | Loading: Report wird erzeugt | Error: Report konnte nicht erzeugt werden | Empty: Noch kein Report vorhanden | Ja fuer Evidence/Release | `Report derzeit nicht verfuegbar` |
| Settings | `/console/account`, `/console/account/language`, `/api/dashboard/preferences/*` | `/api/dashboard/preferences/locale`, `/api/dashboard/preferences/ui-mode` | BFF-local Cookie/Preference, optional Gateway Profil | Dashboard-BFF, sichere Cookies, keine Secrets | Loading: Einstellungen werden geladen | Error: Einstellungen konnten nicht gespeichert werden | Empty: Standardwerte aktiv | Indirekt; falsche Sprache/ENV nicht live-entsperrend | `Einstellungen konnten nicht gespeichert werden` |

## 5) Deutsche Fehlermeldungen

Fehler sind deutsch, kurz und ohne Stacktrace. Beispiele:

- `Backend nicht erreichbar. Die Konsole zeigt einen sicheren degradieren Zustand.`
- `Daten fehlen: Es wurde noch kein Reconcile-Lauf geschrieben.`
- `Live bleibt blockiert, bis Asset-Freigabe, Risk-Governor und Exchange-Health gruen sind.`

## 6) Sichere Mock-/Demo-Fallbacks

Mock- oder Demo-Daten sind nur fuer `APP_ENV=local` oder Tests erlaubt. Sie
muessen sichtbar als Demo markiert sein und duerfen nie als echte Live-Daten
erscheinen. In Shadow/Production ist fehlende Quelle `degraded` oder
`unavailable`, nicht stiller Mock.

## 7) Keine Secrets im Browser

BFF-Routen halten `DASHBOARD_GATEWAY_AUTHORIZATION`, Gateway-JWT,
`INTERNAL_API_KEY`, OpenAI-, Bitget-, Telegram-, DB- und Redis-Secrets
serverseitig. UI und JSON-Antworten duerfen keine Secret-Felder ausgeben.

## 8) No-Go-Regeln

- Keine Karte ohne Loading State, Fehlerzustand und Empty State.
- Keine technischen Stacktraces im UI.
- Kein Browserzugriff auf interne Gateway-/Service-Secrets.
- Backend-Ausfall darf die Main Console nicht crashen.
- Live-Blocker duerfen nicht versteckt oder durch Mock-Daten ueberdeckt werden.
- Billing-, Customer-, Sales-, Checkout- oder Payment-Flows sind keine
  Main-Console-Pflicht fuer die private Owner-Version.

## 9) Tests

```bash
python tools/check_main_console_wiring.py
python tools/check_main_console_wiring.py --strict
python tools/check_main_console_wiring.py --json
pytest tests/tools/test_check_main_console_wiring.py -q
```

Zusaetzliche UI-/BFF-Tests sind erforderlich, sobald neue UI/BFF-Codepfade fuer
diese Matrix geaendert werden: deutsche BFF-Fehlerabbildung, Empty State,
Demo-Markierung, Secret-Redaktion und Timeout als `degraded`/`unavailable`.
