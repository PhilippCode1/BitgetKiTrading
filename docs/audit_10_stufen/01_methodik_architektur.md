# Teil 1/10: Methodik, Bewertungsskala, Architektur

**Audit-Datum:** 2026-04-03 (Workspace: bitget-btc-ai)  
**Gewichtung:** **Code** und **Endnutzer-Oberflaeche** jeweils **50 %** in der Gesamtbewertung (siehe Teil 10).

---

## 1. Zehn-Stufen-Skala (Definition)

| Stufe  | Code / Plattform                                        | Oberflaeche / Produkt                              |
| ------ | ------------------------------------------------------- | -------------------------------------------------- |
| **1**  | Fehlende Kernfunktion, unsaubere Kopplung, hohes Risiko | Keine nutzbare UI oder irrefuehrend                |
| **2**  | Prototyp, wenig Tests, fragile Integration              | Nur Platzhalter                                    |
| **3**  | Einzelne Services stabil, Luecken zwischen Modulen      | Teilweise interne Tools                            |
| **4**  | Kernpfade testbar, aber ohne Produkt-Gates              | Kein Kundenportal                                  |
| **5**  | Solide Ingenieursbasis, dokumentierte Grenzen           | Spezifikationen/Docs, keine Shippable-UI           |
| **6**  | CI gruen, sichere interne Auth-Muster                   | Admin/Kunde geplant, Contracts vorhanden           |
| **7**  | Produktnahe Policies im Code, DB-Schema fuer Kommerz    | Erste UI-Prototypen moeglich                       |
| **8**  | Echtgeld-Pfade mit mehrstufigen Gates + Audit           | Professionelle UI, klare Modus-Trennung            |
| **9**  | Pen-Test-ready, PSP-Integration, Mahnwesen              | Barrierefreiheit, i18n, Support-Flows              |
| **10** | Regulierte Betriebsreife, Notfallprozesse, Beweiskette  | Vollstaendiges serioeses Kunden- und Admin-Produkt |

---

## 2. Architektur-Ueberblick (Code-Beweis)

### 2.1 Microservices + Shared Library

Das Repository ist ein **Polyrepo-in-Monorepo**: viele Python-Services unter `services/` und gemeinsame Logik unter `shared/python/src/shared_py/`.

**Beleg (CI installiert explizit jedes Paket):**

```71:88:.github/workflows/ci.yml
      - name: Install packages (gepinnt: requirements-dev + editables)
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements-dev.txt
          pip install -c constraints-runtime.txt -e ./shared/python
          pip install -c constraints-runtime.txt -e ./services/feature-engine
          pip install -c constraints-runtime.txt -e ./services/signal-engine
          pip install -c constraints-runtime.txt -e ./services/paper-broker
          ...
          pip install -c constraints-runtime.txt -e ./services/live-broker
```

**Bewertung (nur Architektur):** Klare Modulgrenzen, reproduzierbare Installation — **stark technisch** (hohe Stufe fuer „Engineering-Struktur“ allein).  
**Einschraenkung:** Struktur ersetzt **nicht** Produkt-Gates fuer Echtgeld (siehe Teil 2–4).

### 2.2 API-Gateway als HTTP-Fassade

Das Gateway bündelt interne Aufrufe (z. B. LLM-Orchestrator) und setzt Trace-Header.

**Beleg (Forward + interner Key):**

```28:56:services/api-gateway/src/api_gateway/llm_orchestrator_forward.py
def post_llm_orchestrator_json(
    settings: GatewaySettings,
    subpath: str,
    body: dict[str, Any],
    *,
    timeout_sec: float = 120.0,
) -> Any:
    base = settings.llm_orchestrator_http_base()
    ...
    ik = str(getattr(settings, "service_internal_api_key", "") or "").strip()
    if internal_service_auth_required(settings) and not ik:
        raise RuntimeError(
            "INTERNAL_API_KEY fehlt fuer LLM-Orchestrator-Forward ..."
        )
    ...
    if ik:
        headers[INTERNAL_SERVICE_HEADER] = ik
```

**Risiko-Hinweis:** Shared-Secret zwischen Diensten ist **ueblich**, aber kein Ersatz fuer **Endnutzer-Auth** (siehe Teil 3).

### 2.3 Datenbank-Migrationen

**74** SQL-Migrationen unter `infra/migrations/postgres/` (Stand: Workspace-Listing). Beleg: Verzeichnisinhalt im Repo (siehe Teil 5 fuer kommerzielle Tabellen).

---

## 3. Teilbewertung Teil 1 (nur diese Dimensionen)

| Dimension                                   | Stufe (1–10) | Kurzbegruendung                                                   |
| ------------------------------------------- | ------------ | ----------------------------------------------------------------- |
| Architektur / Modularitaet                  | **7**        | Viele Services, shared_py, CI-Installation klar                   |
| Dokumentation Ingenieur                     | **6**        | Umfangreiche `docs/`, z. T. eng am Trading-Kern                   |
| Produkt-Architektur Modul Mate (End-to-End) | **4**        | Trading-Stack stark; **kein** geschlossenes Kundenprodukt im Repo |

---

## 4. Offene Punkte (Teil 1)

- Gesamtnote folgt **Teil 10** nach Aggregation aller Dimensionen.
- Explizite Verknuepfung **Modul-Mate-Policies → Runtime** fehlt (Details Teil 2).

**Naechste Datei:** `02_kontrakte_vs_runtime.md`
