# Teil 4/10: Trading, Demo vs. Live, Orderpfad

---

## 1. Bitget-Demo vs. Live: Konfiguration im Exchange-Client

```18:28:services/live-broker/src/live_broker/exchange_client.py
_PRIVATE_DETAIL_DE: dict[str, str] = {
    "missing_api_key_or_secret": (
        "API-Key oder Secret fehlt. Demo: BITGET_DEMO_ENABLED=true sowie BITGET_DEMO_API_KEY und "
        "BITGET_DEMO_API_SECRET. Live: BITGET_API_KEY und BITGET_API_SECRET."
    ),
    ...
}
```

**Bewertung:** Klare Unterscheidung **Demo-Credentials** vs. **Live-Credentials** auf technischer Ebene — **gut**.

---

## 2. Keine Verknuepfung zu Modul-Mate `resolve_execution_mode`

Siehe Teil 2: `product_policy` wird in `services/` **nicht** referenziert. Ein **Echtgeld-Submit** kann damit **nicht** automatisch an „Vertrag + Admin-Freigabe + Abo“ gekoppelt werden.

**Risiko:** Operative ENV-Fehler oder falscher Tenant koennten **weiter** Orders ermoeglichen, obwohl das Produktrechtliche Gate fehlt.

---

## 3. Paper-Broker (Simulation)

Der Repo enthaelt `services/paper-broker` (CI-Installation in `.github/workflows/ci.yml`). Das ist ein **separater** Simulationspfad — sinnvoll fuer Strategie-Tests.

**Bewertung Ingenieur:** **hoch** fuer Forschung/Betrieb intern.  
**Bewertung Modul-Mate-Kunde:** ohne UI und ohne Mandanten-Gates **nicht** als Endprodukt.

---

## 4. Teilbewertung Teil 4

| Dimension                            | Stufe (1–10) | Kurzbegruendung                                                                           |
| ------------------------------------ | ------------ | ----------------------------------------------------------------------------------------- |
| Technische Demo/Live-Trennung Bitget | **7**        | Eigene Keys, Demo-REST                                                                    |
| Produktrechtliche Demo/Live-Trennung | **2**        | Nicht an `product_policy` gebunden                                                        |
| Order-Idempotenz / Resilienz         | **6**        | Settings fuer Retries/Circuit in `LiveBrokerSettings` (siehe `config.py`, weitere Zeilen) |

---

**Naechste Datei:** `05_datenbank_migrationen.md`
