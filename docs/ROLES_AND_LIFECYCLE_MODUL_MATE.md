# Rollen, Lebenszyklus und Nutzerwege (Modul Mate GmbH)

**Dokumentversion:** 1.0  
**Bezug:** Prompt 2; technische Abbildung: `shared_py.customer_lifecycle`

---

## Legende

| Kennzeichnung | Bedeutung                           |
| ------------- | ----------------------------------- |
| **[FEST]**    | Aus stakeholder-Vorgaben            |
| **[ANNAHME]** | Standard bis explizite Entscheidung |

---

## Rollenmatrix (Kurz)

| Rolle                      | Beschreibung                                                                                |
| -------------------------- | ------------------------------------------------------------------------------------------- |
| **Super-Admin** **[FEST]** | Philipp Crljic – alleiniger Vollzugriff auf KI-Schalter und Freigaben                       |
| **Interessent**            | Nicht eingeloggt / kein Konto                                                               |
| **Kunde (Lebenszyklus)**   | Eine Rolle `CUSTOMER` mit **Phase** (Status) – vermeidet doppelte Rollenlogik **[ANNAHME]** |

---

## Phasen (Basis-Status)

Siehe Enum `LifecyclePhase` in `customer_lifecycle.py` (fein granular). **Prompt 11 (Produktion):** kanonische öffentliche Status in `CustomerLifecycleStatus`: `invited`, `registered`, `trial_active`, `trial_expired`, `contract_pending`, `contract_signed_waiting_admin`, `live_approved`, `suspended`, `cancelled` — Persistenz `app.tenant_customer_lifecycle`, Audit `app.tenant_lifecycle_audit`, Sync nach `app.tenant_modul_mate_gates`. Probephase: **21 Kalendertage** (`TRIAL_PERIOD_DAYS`). Überlagernd möglich:

- **Pause** (`is_paused`): weiche Sperre (Zahlung, Wunsch)
- **Sperre** (`is_suspended`): harte Sperre (Admin, Compliance)

---

## Seitenstruktur (Referenz für UI)

### Kunde

Start, Produkt, Preise, Registrierung, Login, E-Mail bestätigen, Onboarding, Dashboard (Demo/Live getrennt), KI-Ansicht, Börse verbinden, Telegram, Orders, Limits, Vereinbarung, Abo, Daten, Support, Sicherheit, Rechtliches.

### Super-Admin

Verwaltungs-Start, Kundenliste, Kundendetails (Übersicht, Probephase, Vereinbarung, Demo/Echtgeld, API, Telegram, Zahlungen, KI pro Kunde, Notizen, Verlauf), Belege, Anbindungen, globale KI, Notfall, Berichte.

---

## Freigaben und Ausführung

- **Demo-Orders:** u. a. in `TRIAL_ACTIVE` oder ab `CONTRACT_ACTIVE` ohne Live-Freigabe (über `commercial_gates_from_lifecycle` → `product_policy`).
- **Echtgeld-Orders:** nur in `LIVE_RELEASED` (impliziert Vertrag, Zahlung **[ANNAHME]**, Admin-Freigabe) und ohne Pause/Sperre.
- **Telegram Live-Aktionen:** gleiche Gates wie Echtgeld **[ANNAHME]** plus zusätzliche Absicherung in den Services.

---

## Statusübergänge

Erlaubte Übergänge und verantwortliche Akteure sind in `ALLOWED_LIFECYCLE_TRANSITIONS` und `is_lifecycle_transition_allowed` zentral definiert.

---

## Offene Punkte

- Exakte Kopplung **Zahlungspflicht** an einzelne Phasen (aktuell: Abo ab `PAYMENT_*`).
- **Telegram Live-Orders** in v1: empfohlen nur Info; siehe `CustomerCapabilities.telegram_live_actions`.
