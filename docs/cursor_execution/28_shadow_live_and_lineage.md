# 28 — Shadow/Live-Vergleich, Divergenz und data_lineage

**Stand:** 2026-04-05

**Bezug:** [05 — Format/YAML](05_format_and_yaml_hygiene.md) (saubere Artefakte), [08 — ENV/Auth](08_env_profiles_and_secrets_sync.md) (BFF/Gateway nur serverseitig authentifiziert), [18 — Live-Broker](18_live_broker_and_safety.md), [27 — Live-Broker-Oberfläche](27_live_broker_surface_completion.md).

## Ziel

Die Seite **`/console/shadow-live`** beschreibt **ehrlich**, woher Zahlen kommen: **Paper** (Simulator), **Shadow/Live-Decisions** (DB + Payload), **Fills** (Börse/Live-Pfad), **Divergenz** (aus `shadow_live_divergence`), **Markt-Pipeline** (`GET /v1/live/state` → `data_lineage`). Keine stillen Gleichsetzungen von Paper und Live-Marktdaten.

## Vergleichsregeln (final)

| Aspekt                        | Quelle                                                                  | Regel                                                                                             |
| ----------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Shadow≈Live-Zelle             | `live.execution_decisions.payload_json.shadow_live_divergence.match_ok` | `true` / `false` / fehlend → UI „kein Wert“, **nicht** als „ok“ interpretieren                    |
| Hard/Soft-Violations          | dieselbe Payload-Struktur                                               | Anzahl in der Tabelle; Detail per `title` (JSON); voller Report in **Forensic**                   |
| Divergenz-Zeilen              | Decisions mit `match_ok === false` oder nicht-leeren Violation-Arrays   | Stichprobe (erste 15), kein aggregierter PnL-Vergleich                                            |
| Paper Gewinn/Verlust          | `GET /v1/paper/trades/recent`                                           | Nur Zeilen mit `closed_ts_ms` **und** `pnl_net_usdt` (geschlossene Evaluation)                    |
| Paper „geladen“               | gleiche Route                                                           | Anzahl aller Zeilen im Fenster (z. B. 40) — getrennt von „geschlossen“                            |
| Live-Fills                    | `GET /v1/live-broker/fills/recent`                                      | Fenster über Börse/live-broker; **keine** automatische 1:1-Zuordnung zu Paper ohne `execution_id` |
| Tiefere Shadow-Live-Analyse   | `live.shadow_live_assessments` u. a.                                    | In **Forensic-Timeline** (`GET /v1/live-broker/executions/{id}/forensic-timeline`)                |
| Markt-Herkunft (Signal/Chart) | `GET /v1/live/state`                                                    | `data_lineage[]`: Segmente mit `has_data`, `producer_*`, `why_empty_*`, `next_step_*` (DE/EN)     |

## UI-Pfade

| Pfad                                           | Inhalt                                                                                                        |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `/console/shadow-live`                         | Herkunftstexte, Kurzfassung, `data_lineage`-Tabelle (Symbol/TF aus Chart-Kontext wie Paper), Divergenztabelle |
| `/console/live-broker`                         | Vollständiges Journal inkl. aller Decisions                                                                   |
| `/console/live-broker/forensic/{execution_id}` | `shadow_live_assessment`, Risk, Timeline                                                                      |

## Backend (Kurz)

- Decisions inkl. Shadow-Felder: `fetch_live_broker_decisions` in `db_live_broker_queries.py` — `_shadow_live_fields` aus `payload_json.shadow_live_divergence`.
- Forensic: `live.shadow_live_assessments` per `execution_decision_id` (siehe `fetch_execution_forensic_timeline`).
- `data_lineage`: `db_live_queries.build_data_lineage` — an `GET /v1/live/state` angehängt.

## Beispiel-Payloads (Nachweis)

**Decision-Ausschnitt (Shadow-Felder, vereinfacht):**

```json
{
  "execution_id": "…",
  "effective_runtime_mode": "shadow",
  "shadow_live_match_ok": false,
  "shadow_live_hard_violations": ["…"],
  "shadow_live_soft_violations": []
}
```

**Live-State `data_lineage` (Segment):**

```json
{
  "segment_id": "candles",
  "label_de": "Kerzen",
  "label_en": "Candles",
  "has_data": true,
  "producer_de": "Bitget REST",
  "producer_en": "Bitget REST",
  "why_empty_de": "",
  "why_empty_en": "",
  "next_step_de": "",
  "next_step_en": ""
}
```

## Nachweise (Befehle)

```powershell
cd c:\Users\Acer\OneDrive\Documents\Cursor1\bitget-btc-ai
pnpm check-types
cd apps\dashboard
pnpm exec jest --testPathPattern="operator-console|shadow-live-console" --runInBand
```

**HTTP (laufendes Gateway):**

```bash
curl -sf "$API_BASE_URL/v1/live-broker/decisions/recent" | head -c 600
curl -sf "$API_BASE_URL/v1/live/state?symbol=BTCUSDT&timeframe=1m&limit=5" | head -c 800
```

(`tests/dashboard/test_routes_smoke.sh` enthält u. a. `live/state`.)

## Offene Punkte

- `[FUTURE]` Ops-Kachel könnte `paperTradeRowsLoaded` neben W/L anzeigen — optional.
- `[TECHNICAL_DEBT]` `db_dashboard_queries._shadow_live_from_execution_payload` und `db_live_broker_queries._shadow_live_fields` sind parallel; langfristig eine Hilfsfunktion im Gateway würde Drift reduzieren.
