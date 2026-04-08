# UI- und Produkt-Freigabeliste (Endkunden-Oberfläche)

Kurz-Checkliste **vor** einer als „fertig“ kommunizierten Release. Ergänzt `docs/LaunchChecklist.md` und `docs/ci_release_gates.md` mit **sichtbaren** Qualitätskriterien.

## Automatisiert (muss grün)

| Prüfung                                   | Befehl / Ort                                    |
| ----------------------------------------- | ----------------------------------------------- |
| Dashboard Lint, Tests, Build              | CI-Job `dashboard`                              |
| Vollstack + HTTP-Smokes + KI + Playwright | CI-Job `compose_healthcheck`                    |
| Lokales Release-Gate (ohne Browser)       | `pnpm release:gate` (Stack + `.env.local`)      |
| Mit Browser-E2E                           | `pnpm release:gate:full` (Dashboard erreichbar) |

## Manuell — Kernreisen (lokal oder Staging)

- [ ] **Start:** Produktstartseite `/` lädt, Sprache wählbar, Weg in die Konsole klar.
- [ ] **Navigation:** Einfache vs. Profi-Ansicht; keine toten Menüpunkte; Rückweg zur Produktseite.
- [ ] **Live-Terminal:** Kerzen sichtbar (bei laufender Pipeline); Symbol/Zeitfenster; Datenfluss-Hinweise verständlich.
- [ ] **Signale:** Liste und Signaldetail; Chart-Kontext; **KI: Strategie- und Signalerklärung** antwortet oder zeigt **klare** Fehlermeldung (kein leeres Schweigen).
- [ ] **Health:** Systemdaten, **Operator-Assistent (KI)** mit sichtbarem Ergebnis oder klarer Fehlermeldung; PDF-Link nur wenn sinnvoll.
- [ ] **Konto / Broker:** `Konto` → Unterseiten inkl. Broker ohne rohe Stack-Trace-Texte für Endkunden.
- [ ] **Mobile (≤900px):** Sidebar wird nutzbar oben; lesbare Typo; keine horizontalen Überläufe auf Start- und Konsole-Start.
- [ ] **Kein Daueralarm:** Nur **reale** Degradation zeigt Warnungen; keine Debug-Banner in der Standard-Produktansicht.

## Staging-Parität

Siehe `STAGING_PARITY.md`: gleiche Architekturregeln, `API_GATEWAY_URL` / `NEXT_PUBLIC_*` / `HEALTH_URL_*` im Container konsistent; optional:

`python scripts/staging_smoke.py --env-file .env.shadow`

## Bewusst außerhalb dieser Liste

Organisatorische Go-Live-Punkte (Backup, On-Call, Exchange-Freigaben) bleiben in `docs/LAUNCH_DOSSIER.md`.
