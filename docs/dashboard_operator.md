# Dashboard: Operator-Betrieb

> Architektur-Stand: Die sichtbare Produktoberflaeche wird auf eine zentrale
> deutsche Main Console ausgerichtet. Siehe
> `docs/production_10_10/main_console_architecture.md`.

## Einstieg

- **`/console/incidents` / `/console/system-health-map`:** Systemstatus,
  Prioritaeten, Datenfluesse und Alerts.
- Standard-Route: **`/console`** (Uebersicht) mit klarer Weiterfuehrung in
  Kernmodule.
- **`/console/ops`**: Risk/Portfolio-Lage mit Fokus auf Live-Blocker und
  sichere naechste Schritte.
- **`/console/terminal`**: Chart + SSE; Fehler als Banner statt stillem
  Leerlauf.
- **`/console/live-broker/forensic/[id]`**: End-to-End-Timeline fuer
  `execution_id` inkl. Signal-, Risk-, Reconcile- und Auditkontext.

Im Zielbild ist das Dashboard **Operator-Sicht**, nicht Strategiekonfigurationskanal.
Es arbeitet gegen den Marktinventar-/Broker-/Learning-Zustand des Backends und darf
keine Exchange- oder Modell-Secrets im Browser fuehren.

**Architektur-Referenz:** `docs/adr/ADR-0001-bitget-market-universe-platform.md`
**Kanonische Statussprache:** `docs/operator_status_language.md`

## Main-Console-Kernmodule

- Uebersicht
- Asset-Universum
- Charts
- Signale & KI-Erklaerung
- Risk & Portfolio
- Paper/Shadow/Live-Readiness
- Live-Broker & Execution-Safety
- Systemstatus & Alerts
- Reports & Evidence
- Einstellungen & Runtime-Checks

Legacy-/Customer-/Billing-/Sales-Bereiche sind nicht Teil dieser aktiven
Kernnavigation und bleiben, falls technisch noetig, internal/deprecated.

## Admin & Lifecycle

- Mit **`NEXT_PUBLIC_ADMIN_USE_SERVER_PROXY=true`** erscheint der Admin-Menuepunkt und Strategie-Lifecycle-Mutationen nur, wenn **`DASHBOARD_GATEWAY_AUTHORIZATION`** gesetzt ist und `GET /v1/admin/rules` am Gateway erfolgreich ist.
- Derselbe Schalter steuert **Live-Terminal** (Browser-`fetch` + **SSE**): Client ruft dann `/api/dashboard/live/state` und `/api/dashboard/live/stream` auf dem Dashboard-Host auf; Next.js reicht mit `DASHBOARD_GATEWAY_AUTHORIZATION` ans Gateway weiter (ohne Token im Browser).
- Ohne Proxy-Modus bleibt das bisherige lokale Admin-Token-Verhalten (nur Entwicklung); bei erzwungenem Gateway-Auth schlagen direkte Browser-Calls auf `/v1/live/*` mit 401 fehl.

## Keine Secrets im Browser

Exchange- und Provider-Secrets werden nicht als `NEXT_PUBLIC_*` exponiert; serverseitige Calls nutzen `DASHBOARD_GATEWAY_AUTHORIZATION` wie in `docs/api_gateway_security.md` beschrieben.

## Zielbild fuer Marktuniversum

Die Operator-Sicht muss kuenftig family-aware sein:

- Instrumente werden nicht nur ueber `symbol`, sondern ueber Family-/Instrumentkontext dargestellt.
- Read-only-Chart-Kategorien duerfen sichtbar sein, auch wenn sie execution-disabled sind.
- Live-Aktionen bleiben operator-gated und muessen klar von Analyse-/Paper-/Learning-Sichten getrennt bleiben.

Fuer den aktuellen Metadatenlayer bedeutet das:

- Watchlist und Default-Instrumente werden ueber Profil-/Universumskeys abgeleitet, nicht ueber starre Einzelkonstanten.
- Die Live-Broker-Seite zeigt Katalog-Health und die zuletzt bekannte Instrument-Metadatensicht.
- Operatoren koennen dadurch Precision-, Session-, Delivery- und Statusprobleme erkennen, bevor Orderwege manuell freigegeben werden.

Seit dem Playbook-Register zeigt die Operator-Sicht fuer das letzte Signal
zusaetzlich:

- `playbook_id`
- `playbook_family`
- `playbook_decision_mode`
- `strategy_name`
- `specialist_router_id`
- `exit_family_effective_primary`
- `stop_distance_pct`, `stop_budget_max_pct_allowed`, `stop_fragility_0_1`, `stop_executability_0_1`
- Telegram-/Outbox-Linkstatus fuer Signal oder Execution (nur lesend)

Damit ist erkennbar, ob ein Trade wirklich an eine registrierte
Strategie-Familie gebunden war oder bewusst `playbookless` blieb.

## Operator-Queues

- **Mirror-Freigabe (Approval Queue):** nur `live_candidate_recorded` ohne bestaetigtes Operator-Release.
- **Live Mirrors & Divergenz:** Kombination aus `live_mirror_eligible`, `shadow_live_match_ok` und Shadow-/Live-Verletzungen.
- **Plan / Decision Queue:** letzte `live.execution_decisions` inkl. Risk-Hinweisen, Release-Status und Telegram-Link.
- **Paper-vs-Live Outcome:** Cockpit verdichtet Live-Kandidaten, Releases, Fills sowie geschlossene Paper-Trades. Das ist ein operatorischer Vergleich, keine implizite 1:1-Spiegelung.

Diese Ansichten sind die operative Primaersicht fuer den Ramp-Pfad aus
`docs/shadow_burn_in_ramp.md`: Shadow-Burn-in lesen, Mirror-Kandidaten freigeben,
Divergenz/Forensik pruefen und bei No-Go-Bedingungen wieder auf shadow-only fallen.
