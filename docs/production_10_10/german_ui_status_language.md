# Deutsche UI-Statussprache

## Zweck

Die sichtbare Anwendungssprache ist produktiv **Deutsch**. Englisch darf als
technischer Fallback fuer Tests/Entwicklung bestehen, ist aber nicht
Produktstandard fuer Philipp.

## Erlaubte Statusbegriffe

- bereit zur Pruefung
- blockiert
- kein Handel (`do_not_trade`)
- Papiermodus aktiv
- Schattenmodus aktiv
- Echtgeldmodus gesperrt
- Freigabe ausstehend
- Freigabe erteilt
- Abgleich sauber
- Sicherheits-Sperre aktiv
- Not-Stopp aktiv
- Quarantaene aktiv
- Daten veraltet
- Systemstatus unbekannt

## Verbotene Begriffe (sichtbar)

- Billing
- Customer
- Tenant
- Pricing
- Plans
- Subscribe
- Contract
- Sales
- Public Launch
- Gewinn garantiert
- risikofrei
- sichere Rendite

## Standardtexte fuer Fehler

- **Allgemeiner Fehler:**  
  `Aktion konnte nicht abgeschlossen werden. Grund ist derzeit unklar. Naechster sicherer Schritt: Seite neu laden und Systemstatus pruefen.`
- **System nicht erreichbar:**  
  `Systemstatus konnte nicht geladen werden. Ohne belastbare Systemdaten bleibt die Ausfuehrung blockiert. Naechster sicherer Schritt: Verbindung und Gateway pruefen.`
- **Freigabefehler:**  
  `Freigabe fehlt oder ist ungueltig. Aus Sicherheitsgruenden bleibt Echtgeld blockiert. Naechster sicherer Schritt: Freigabekette und Betreiberstatus pruefen.`

## Standardtexte fuer leere Zustaende

- **Keine Daten:**  
  `Derzeit liegen keine verwertbaren Daten vor. Naechster sicherer Schritt: Filter pruefen oder spaeter erneut laden.`
- **Keine Signale:**  
  `Aktuell keine handelbaren Signale. Plattform bleibt im sicheren Beobachtungsmodus.`
- **Keine Vorfaelle:**  
  `Keine offenen Vorfaelle im aktuellen Zeitraum.`

## Standardtexte fuer Live-Blockaden

- `Echtgeld bleibt blockiert, bis alle Sicherheits- und Freigabegates erfuellt sind.`
- `Unsichere oder unvollstaendige Datenlage erkannt: kein Live-Start.`
- `Safety-Latch oder Not-Stopp aktiv: keine Orderfreigabe.`

## Standardtexte fuer Asset-Quarantaene

- `Asset in Quarantaene: Handel gesperrt bis Datenqualitaet, Liquiditaet und Owner-Freigabe nachgewiesen sind.`
- `Neues oder instabiles Asset erkannt: nur Beobachtung, kein Live-Handel.`

## Standardtexte fuer Paper/Shadow/Live

- **Paper:** `Papiermodus aktiv: keine echten Boersenorders.`
- **Shadow:** `Schattenmodus aktiv: Vergleichspfad ohne echte Ausfuehrung.`
- **Live:** `Echtgeldmodus nur mit vollstaendiger Freigabe- und Sicherheitskette.`

## Schreibregeln fuer jede Seite

- Direkt mit Zweck, Status, naechster Aktion starten.
- Keine Marketing-Einleitung.
- Keine Gewinnversprechen oder Anlageberatung.
- Keine Aussage wie "alles bereit", wenn Nachweise fehlen.
