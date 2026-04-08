# Teil 7/10: Tests, CI und Codequalitaet

---

## 1. GitHub Actions CI-Umfang

```90:112:.github/workflows/ci.yml
      - name: Ruff (tests, tools, integration inkl. fixtures)
        run: >-
          ruff check tests/unit tests/integration ...
      - name: Black (ohne tests/unit — Legacy-Format dort)
        run: >-
          black --check tests/integration ...
      - name: Mypy (kritische shared_py-Module, strict package)
        working-directory: shared/python
        run: >-
          mypy src/shared_py/leverage_allocator.py src/shared_py/risk_engine.py
          src/shared_py/exit_engine.py src/shared_py/shadow_live_divergence.py
```

**Beleg:** **Ruff + Black + Mypy (teilweise)** + Postgres/Redis Services.

---

## 2. Bekannte Schwaeche (explizit im CI genannt)

```100:106:.github/workflows/ci.yml
      - name: Black (ohne tests/unit — Legacy-Format dort)
        run: >-
          black --check tests/integration ...
```

**Bewertung:** `tests/unit` ist **ausgeschlossen** — **technische Schuld** sichtbar und dokumentiert.

---

## 3. Modul-Mate Contract-Tests

Es existieren u. a. `tests/unit/shared_py/test_product_policy.py`, `test_customer_lifecycle.py`, `test_billing_subscription_contract.py` — **positiv** fuer die **Spezifikations**-Module.

**Luecke:** **Keine** Integrationstests gefunden, die **live-broker** + **DB-Lebenszyklus** + **Gates** gemeinsam pruefen (Stand: Stichprobe).

---

## 4. Teilbewertung Teil 7

| Dimension                          | Stufe (1–10) | Kurzbegruendung                         |
| ---------------------------------- | ------------ | --------------------------------------- |
| CI-Breite                          | **8**        | DB, Redis, viele Pakete, Security-Gates |
| Striktheit Formatierung Unit-Tests | **4**        | Black skip tests/unit                   |
| Mypy-Abdeckung shared_py           | **5**        | Nur Untermenge „kritisch“               |
| Produkt-Integrationstests Gates    | **3**        | Nicht belegt                            |

---

**Naechste Datei:** `08_observability_betrieb.md`
