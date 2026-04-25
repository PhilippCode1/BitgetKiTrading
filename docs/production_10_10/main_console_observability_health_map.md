# Main Console Observability- und Health-Landkarte

## Zweck

Die Health-Landkarte bündelt Service-Gesundheit, Datenfrische und Live-Auswirkung
in einer deutschen Betreiberansicht. Sie ist fail-closed: unbekannte oder stale
livekritische Pfade blockieren Live.

## Abgebildete Komponenten

1. API-Gateway
2. Dashboard/BFF
3. Market-Stream
4. Feature-Engine
5. Signal-Engine
6. Paper-Broker
7. Live-Broker
8. Alert-/Monitor-Engine
9. Redis/Eventbus
10. Postgres
11. Bitget Public API
12. Bitget Private Read-only
13. LLM-Orchestrator (falls aktiv)
14. News-Engine (falls aktiv)
15. Asset-Katalog
16. Reconcile
17. Shadow-Burn-in Evidence
18. Restore/Safety Evidence

## Payload-Contract je Komponente

Jede Komponente liefert:

- `status`: `ok|warn|fail|unknown`
- `freshness_status`: `fresh|stale|missing|not_applicable`
- `live_auswirkung_de`
- `blockiert_live`
- `letzter_erfolg_ts`
- `letzter_fehler_ts`
- `fehlergrund_de`
- `nächster_schritt_de`

## Harte Fail-Closed-Regeln

1. Unknown im livekritischen Pfad blockiert Live.
2. Stale Market Data blockiert signalbasiertes Live.
3. Stale Reconcile blockiert Live-Openings.
4. Fehlender Redis/Eventbus blockiert Live, wenn Shadow-Match/Liquidity/Signals betroffen sind.
5. Fehlende DB blockiert alle livekritischen Pfade.
6. Health zeigt keine Secrets.
7. Sichtbare Labels sind deutsch.
8. Kein globales „Alles OK“, wenn ein kritischer Teil `fail` oder `unknown` ist.

## Implementierung

- Python Contract: `shared/python/src/shared_py/health_map.py`
- Dashboard View-Model: `apps/dashboard/src/lib/health-map-view-model.ts`
- Main-Console-Modul: `apps/dashboard/src/app/(operator)/console/system-health-map/page.tsx`
- Checker: `tools/check_main_console_health_map.py`

## Noch offene echte Datenquellen

Für vollständige Reife sollen später zusätzlich angebunden werden:

- echte Eventbus-Lag-Metriken je Stream,
- echte Reconcile-Last-Success/-Error-Zeitstempel aus Persistenz,
- Shadow-Burn-in Evidence aus zentralem Evidence-Store,
- Restore/Safety Evidence aus DR-Testlauf-Pipeline.

Bis dahin gilt: fehlende Quellen = `unknown`/`missing`, niemals „grün“ simulieren.
