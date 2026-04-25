# Main Console System Diagnostics

Status: `implemented`

## Ziel

Die Route `console/system-health-map` ist die zentrale deutsche Diagnosekonsole fuer Runtime, Provider, Datenfrische und Alerts. Unsichere oder unvollstaendige Zustaende werden fail-closed als Warnung/Blockade sichtbar gemacht.

## Sichtbare Systemstatus-Felder

- Gesamtstatus: `OK` / `Warnung` / `Blockiert`
- Zusammenfassende Gruende fuer den Status
- DB/Redis-Status
- Bitget Public/Private Status
- LLM/News Status
- Alert-/Monitor-Status
- Service-Tabelle mit Status und redigierten Fehlerdetails
- letzte kritische Fehler
- letzte erfolgreiche Checks

## Stale-Data-Checks

Die Konsole zeigt explizit:

- Candles stale
- Orderbook stale
- Signals stale
- Reconcile stale
- Worker heartbeat stale

Jeder Check zeigt `ok` oder `stale` plus deutsche Detailbeschreibung.

## Diagnose-Aktionen

- Nur Read-only Aktionen (kein ungefragtes Production-Netzwerk)
- `Safe Refresh` als UI-Read-only-Hinweis
- `Safe Check` nur, wenn Health-Endpunkt lesbar ist
- Wenn Endpunkt fehlt: klarer Status `Nicht verdrahtet`, kein falsches OK

## Redaction

Fehlerdetails werden vor Anzeige redigiert:

- `authorization`
- `bearer`
- `token`
- `secret`
- `api_key`
- `password`

Keine Secret-Werte werden im UI ausgegeben.

## Relevante Dateien

- `apps/dashboard/src/app/(operator)/console/system-health-map/page.tsx`
- `apps/dashboard/src/lib/system-diagnostics-view-model.ts`
- `apps/dashboard/src/lib/__tests__/system-diagnostics-view-model.test.ts`
