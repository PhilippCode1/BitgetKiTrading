# Live Broker (Execution & Safety)

Das `live-broker` Modul ist die ausführende und kritischste Komponente des BitgetKiTrading-Systems. Es ist verantwortlich für die Interaktion mit der Bitget Exchange, das Order-Routing und primär für die Durchsetzung strikter Risikomanagement-Regeln (Fail-Closed) bevor eine Order das System verlässt.

## 1. Architektur & Bitget-Integration

Die Kommunikation mit der Bitget API erfolgt sowohl asynchron über WebSockets für Marktdaten (in `market_stream`) als auch primär über synchrone REST-Calls (in `private_rest.py`) für Order-Aufgabe, Positionsmanagement und Kontensynchronisierung. 

- **Private REST Client (`private_rest.py`)**: Implementiert Authentifizierung (API-Key, Secret, Passphrase), Canonical Request Signatures und transport-level Fehlerbehandlung (z.B. Time-Sync-Drift, Nonces). Der Client trennt strikt zwischen Live- und Demo-Endpunkten und besitzt eine Fail-Fast-Validierung (`_reject_if_clock_skew_too_large`), falls die Systemzeit von Bitgets Serverzeit um ein kritisches Budget (default ~50ms) abweicht.
- **Circuit Breaker Pattern**: Auf HTTP-Ebene implementiert, unterbricht die Kommunikation automatisch bei gehäuften 5xx-Fehlern oder Transportfehlern.
- **Rate Limiting**: Ein asynchroner Token-Bucket (`rate_limiter.py`) drosselt Anfragen pro Endpunkt-Gewicht und vermeidet API-Banns.

## 2. Global Halt Latch & Killswitch (Fail-Closed)

Die wichtigste Eigenschaft des Live-Brokers ist die `GlobalHaltLatch`-Sicherheitsarchitektur (`global_halt_latch.py`).

| Mechanismus | Beschreibung |
|---|---|
| **Redis In-Memory Latch** | Das globale Notstopp-Flag wird in Redis (`latch:global_halt`) gespeichert. Jede Zustandsänderung (z.B. Order-Platzierung) verifiziert den Latch im Hot-Path (`assert_not_halted`). |
| **Fail-Closed Default** | Wenn Redis nicht erreichbar ist oder antwortet, wird der Latch aus Sicherheitsgründen als "gesperrt" betrachtet. Es gibt keine Silent-Failures. |
| **Administrative Trigger** | Der Latch kann manuell durch den Operator, oder automatisch durch das System (z.B. bei massiver Orderbook-Inkonsistenz oder API-Timeouts) ausgelöst werden. |
| **Graceful Shutdown** | Selbst bei aktivem Latch bleiben `Cancel Only`-Befehle (Stornierungen) erlaubt, um Risiko abzubauen. Neu-Orders und Positionsvergrößerungen sind jedoch hart blockiert. |

## 3. Order-Lifecycle & Predatory Maker-Execution

Der Order-Lifecycle ist auf deterministische Ausführung und maximale Margen-Sicherheit ausgelegt.

```mermaid
graph TD
    A[Signal Engine (JSON)] --> B{Global Halt Latch}
    B -- Halted --> C[Reject & Log]
    B -- OK --> D[Risk Adapter]
    D -- Violation --> E[Reject Trade]
    D -- Pass --> F[Passive Order Manager]
    F --> G[Predatory Maker Execution]
    G --> H[Bitget Private REST]
    H --> I[Order Placed (Ack)]
    I --> J[Reconciliation Loop]
```

- **Risk Adapter (`risk_adapter.py`)**: Überprüft vor jeder Order die Risiko-Exposure. Dies beinhaltet Portfolio-Grenzen, Margen-Auslastung und VPIN-Toxizitätsprüfung. 
- **Predatory Maker Execution (`passive_order_manager.py`)**: Setzt Limit-Orders bevorzugt am Best-Bid/Ask, nutzt Iceberg-Slicing (Zerstückelung großer Orders mit `plan_iceberg_sizes`), integriert Slippage-Budgets (`chase_price_within_slippage`) und stoppt bei starken Ungleichgewichten im Orderbuch (Orderflow-Wall-Safety-Latch).

## 4. Reconciliation & State Sync

Der State (Positionen, offene Orders, Balances) wird fortlaufend synchronisiert und abgeglichen (Reconciliation). 
- In einem asynchronen Loop werden Abweichungen zwischen der internen Ledger-Wahrheit und der tatsächlichen Exchange-Wahrheit behoben (Reconcile).
- Veraltete oder hängende (Orphan) Orders werden aktiv gelöscht, um Margin freizugeben.
