# Teil 6/10: KI- und LLM-Schicht

---

## 1. Klare Abgrenzung: LLM hat **keine** Orderhoheit

```5:8:docs/llm_orchestrator.md
**Nicht** im Verantwortungsbereich: Handelsentscheidung, Risk-Gates, Broker, Order-Submit,
Strategieparameter, Routing-Policies, Modellregistry — das bleibt deterministischer Kern /
Spezialisten-Stack.
```

**Bewertung:** **Sehr gut** fuer Echtgeld-Sicherheit — verhindert „KI drueckt Order“ direkt.

---

## 2. Strukturierte Ausgabe + Provenance

```12:19:docs/llm_orchestrator.md
| Aspekt | Umsetzung |
|--------|-----------|
| Ausgabe | JSON gemaess Draft 2020-12 Schema, Pflichtvalidierung mit `jsonschema` |
| Cache | Redis-Key aus `provider`, `model`, `schema_hash`, `input_hash` ... |
| Resilienz | Retries, Backoff ... **Circuit Breaker**, Provider **OpenAI** |
```

**Bewertung:** **Hoch** fuer Nachvollziehbarkeit und Betrieb.

---

## 3. Modul-Mate `ai_layer_contract` (Prompt 3)

Das Repo enthaelt zusaetzlich `shared_py/ai_layer_contract.py` mit Pipeline-Stufen und Pflicht-Audit-Ideen — **gut** als Produktkontrakt.

**Luecke:** Wie jede Stufe **im Gateway** bei jedem LLM-Call **persistiert** wird, ist ohne Tiefenlesen aller Routes nicht als „voll geschlossen“ belegt.

---

## 4. Teilbewertung Teil 6

| Dimension                             | Stufe (1–10) | Kurzbegruendung                                          |
| ------------------------------------- | ------------ | -------------------------------------------------------- |
| Sicherheitsarchitektur KI vs. Trading | **8**        | Dokumentiert und schema-basiert                          |
| Produkt-KI fuer Endkunden (UI)        | **3**        | Kein ausgeliefertes Web-UI                               |
| Trace/Audit End-to-End                | **5**        | Provenance vorhanden; vollstaendige Kettenpruefung offen |

---

**Naechste Datei:** `07_tests_ci_qualitaet.md`
