# 18 — Live-Broker, Safety und Operator-Sicht

## Ziel

Eine **klare Live-Story** für Operatoren und die Konsole: Live ist **deaktiviert**, **bereit**, **blockiert** (Safety, Exchange, Upstream) oder **fehlerhaft** (Reconcile) — mit **konkreten Begründungen**, nicht mit stillem „es passiert nichts“. Bezug: Handoff **02** (Topologie/Health), **03** (Auth/ENV), **04** (Gateway/BFF), **08** (Fehler/Alerts).

## Laufzeit und Probes

| Ort             | Pfad                          | Inhalt (Kern)                                                                                                             |
| --------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **live-broker** | `GET /ready`                  | `ready`, `checks` inkl. `execution_mode`, `live_order_submission_enabled`, `execution_runtime`, optional `exchange_probe` |
| **live-broker** | `GET /health`                 | Aggregat inkl. `latest_reconcile`, Bitget-REST-Snapshot                                                                   |
| **API-Gateway** | `GET /v1/live-broker/runtime` | Letzter `live.reconcile_snapshots` + Kill-Switch-Zeilen + Latch + **`operator_live_submission`**                          |
| **API-Gateway** | `GET /v1/system/health`       | `ops.live_broker`, `warnings` + **`warnings_display`** (Kill-Switch / Latch mit erklärendem Text)                         |

Lesende Gateway-Routen: `routes_live_broker_proxy.py` (Runtime, Decisions, Orders, Fills, Order-Actions, Kill-Switch, Audit, Forensic-Timeline).  
Safety-Mutationen (Forward zum Worker): `routes_live_broker_safety.py` → live-broker `POST .../kill-switch/*`, `.../safety/*`.

## Feld `operator_live_submission` (Runtime-JSON)

Berechnet in `api_gateway.db_live_broker_queries.compute_operator_live_submission_summary`, eingebettet in `fetch_live_broker_runtime`.

| `lane`                         | Bedeutung                                                                                        |
| ------------------------------ | ------------------------------------------------------------------------------------------------ |
| `live_lane_ready`              | Reconcile ok, keine Safety-Sperre, Gates an, Bitget-Status nicht blockierend                     |
| `live_lane_disabled_config`    | Paper-Modus, Shadow ohne Live-Freigabe, oder `live_trade_enable` / `live_submission_enabled` aus |
| `live_lane_blocked_safety`     | Aktiver Kill-Switch und/oder Safety-Latch                                                        |
| `live_lane_blocked_exchange`   | Bitget `ui_status` in `credentials_invalid` / `credentials_missing` / `exchange_unreachable`     |
| `live_lane_blocked_upstream`   | `upstream_ok == false`                                                                           |
| `live_lane_degraded_reconcile` | Reconcile-Status ≠ `ok`                                                                          |
| `live_lane_unknown`            | Leerer Reconcile-Status im Snapshot                                                              |

`reasons_de`: Liste deutscher Sätze (z. B. pro Kill-Switch eine Zeile mit scope/reason).  
`safety_kill_switch_count`, `safety_latch_active`: kompakte Safety-Metadaten für UI und Health-Anreicherung.

## UI-Recovery (Dashboard)

- **`/console/live-broker`**: `LiveSubmissionOperatorStrip` oberhalb des Charts — farbige Situation (`operator-strip-live` / `-warn` / `-critical` laut `lane`).
- **Kill-Switch-Tabelle**: Wenn leer, Text aus i18n `pages.broker.killSwitchInactiveExplain` (verweist auf Runtime-Banner).
- **Gateway** `GET .../kill-switch/active` leerer Zustand: `empty_message` verweist explizit auf Runtime-Feld `operator_live_submission`.

## Health-Warnungen (sichtbar statt versteckt)

`shared_py.health_warnings_display`:

- `live_broker_kill_switch_active` / `live_broker_safety_latch_active`: Titel und Fließtext betonen **bewusste Blockade**.
- `_enrich_with_ops`: bei Kill-Switch **Anzahl** aus `ops.live_broker.active_kill_switch_count`; bei Latch **Hinweis auf Audit action=arm**.

## Beispiel-Payloads

**Runtime (Auszug, mit Operator-Zusammenfassung):**

```json
{
  "status": "ok",
  "item": {
    "runtime_mode": "shadow",
    "live_trade_enable": true,
    "live_submission_enabled": false,
    "active_kill_switches": [],
    "safety_latch_active": false,
    "operator_live_submission": {
      "lane": "live_lane_disabled_config",
      "reasons_de": [
        "Shadow-Modus: Boersen-Submission (live_submission_enabled) ist aus — typisch bis Live explizit freigeschaltet wird."
      ],
      "safety_kill_switch_count": 0,
      "safety_latch_active": false
    }
  }
}
```

**Kill-Switch aktiv (lane gekürzt):**

```json
{
  "lane": "live_lane_blocked_safety",
  "reasons_de": ["Kill-Switch aktiv (global / *): manueller_stop"],
  "safety_kill_switch_count": 1,
  "safety_latch_active": false
}
```

## Nachweise (Befehle)

```powershell
cd c:\Users\Acer\OneDrive\Documents\Cursor1\bitget-btc-ai
pnpm check-types
pytest tests/unit/api_gateway/test_db_live_broker_queries.py tests/unit/shared_py/test_health_warnings_live_broker_enrich.py -q
# optional mit Stack:
pytest tests/integration/test_http_stack_integration.py -k "live_broker_runtime_operator" -m integration -q
```

**live-broker /ready (direkt):** `GET http://<live-broker-host>:8120/ready` — `checks.execution_mode`, `checks.live_order_submission_enabled`.

## Offene Punkte

- `[FUTURE]` Shadow-Live-Abweichung pro Signal weiter in **Decisions** und Forensic-Timeline vertiefen; Runtime bleibt Snapshot-Ebene.
- `[TECHNICAL_DEBT]` `operator_live_submission` dupliziert teilweise Logik aus live-broker-Settings — bei Drift Reconcile-Writer als Single Source of Truth priorisieren.
