# Teil 2/10: Modul-Mate-Kontrakte vs. Laufzeit-Services

**Fokus:** Sind die **fachlichen** Regeln (Probephase, Vertrag, Live-Freigabe) im **laufenden** Trading-Stack verankert?

---

## 1. Beweis: `product_policy` existiert und definiert Live-Gates

```79:106:shared/python/src/shared_py/product_policy.py
def resolve_execution_mode(gates: CustomerCommercialGates) -> CommercialExecutionMode:
    """
    ...
    - Live nur bei Vertrag + Admin-Freigabe + nicht gesperrt/pausiert + optional Abo.
    """
    if gates.account_suspended or gates.account_paused:
        return CommercialExecutionMode.NONE

    live_ok = gates.contract_accepted and gates.admin_live_trading_granted
    if REQUIRE_ACTIVE_SUBSCRIPTION_FOR_LIVE_TRADING:
        live_ok = live_ok and gates.subscription_active

    if live_ok:
        return CommercialExecutionMode.LIVE

    if gates.trial_active or gates.contract_accepted:
        return CommercialExecutionMode.DEMO

    return CommercialExecutionMode.NONE
```

**Bedeutung:** Die **Fachlogik** fuer Demo/Live ist in Python **korrekt modelliert**.

---

## 2. Beweis: Services importieren diese Policy **nicht**

**Pruefmethode:** Volltextsuche `product_policy`, `customer_lifecycle`, `commercial_data_model` unter `services/**/*.py`.

**Ergebnis:** **0 Treffer** in `services/` (Stand: Audit-Lauf).

**Konsequenz fuer Echtgeld-Produkt:** Der Live-Broker und das Gateway **wissen nichts** von `CustomerCommercialGates` oder `LifecyclePhase`. Die Ausfuehrung haengt an **anderen** Schaltern (ENV/Bitget-Demo), nicht an Vertrag/Admin-Freigabe aus Modul-Mate-Kontrakten.

**Bewertung:** **Kritische Luecke** zwischen **Spezifikation** und **Runtime** → fuer ein regelkonformes Echtgeld-Produkt **nicht** akzeptabel.

---

## 3. Gegenbeleg: Live-Broker nutzt Bitget-Demo/Live-Flags

```36:49:services/live-broker/src/live_broker/exchange_client.py
    def describe(self) -> dict[str, Any]:
        return {
            "effective_rest_base_url": self._settings.effective_rest_base_url,
            ...
            "demo_mode": self._settings.bitget_demo_enabled,
            "live_broker_enabled": self._settings.live_broker_enabled,
            "live_allow_order_submit": self._settings.live_allow_order_submit,
        }
```

**Bedeutung:** Technische Demo/Live-Steuerung ist **konfigurationsbasiert**, **nicht** an Modul-Mate-Lebenszyklus gebunden.

---

## 4. Teilbewertung Teil 2

| Dimension                      | Stufe (1–10) | Kurzbegruendung                                         |
| ------------------------------ | ------------ | ------------------------------------------------------- |
| Fachkontrakte als Code         | **8**        | Umfangreiche `shared_py/*_contract.py` + Tests          |
| Runtime-Verdrahtung Modul Mate | **2**        | Keine Imports in `services/` — Policy „tot“ fuer Broker |
| Konsistenz Risiko              | **2**        | Zwei parallele Wahrheiten (ENV vs. Produkt-Gates)       |

---

## 5. Empfohlene Massnahmen (fuer andere KI / Entwicklung)

1. Im **Order-Submit-Pfad** (Gateway oder live-broker) `commercial_gates_from_lifecycle(...)` oder DB-Aequivalent **vor** Exchange-Call erzwingen.
2. **Ein** kanonischer „Execution-Mode“ pro Request (Trace-ID), der aus DB/Session kommt, nicht nur aus ENV.
3. Unit-Tests: „Live-Order ohne `live_trading_allowed`“ muss **400/403** liefern.

**Naechste Datei:** `03_sicherheit_auth.md`
