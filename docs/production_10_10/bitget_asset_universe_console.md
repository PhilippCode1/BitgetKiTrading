# Bitget Asset-Universum in der Main Console

## Ziel

Die Main Console zeigt ein fail-closed Asset-Universum fuer Spot/Margin/Futures.
Discovery bedeutet **nicht** automatische Live-Freigabe.

## Kanonische Sicht in der Konsole

Route: `/console/market-universe`

Die Asset-Tabelle zeigt mindestens:

- Symbol
- Instrument-ID
- Market Family
- ProductType
- MarginCoin
- Status
- Datenqualitaet
- Liquiditaet
- Spread
- Funding/OI (falls relevant)
- Risk Tier
- Asset-Tier
- Modus erlaubt
- Blockgruende

## Asset-Tiers

- Tier 0: unbekannt/nicht validiert -> Live blockiert
- Tier 1: sehr liquide Hauptassets -> Shadow/Live nur mit Evidence
- Tier 2: liquide Assets -> Shadow, Live spaeter mit Caps
- Tier 3: erhoehte Volatilitaet -> Paper/Shadow, Live nur mit Evidence
- Tier 4: illiquide/high-risk -> kein Live
- Tier 5: delisted/suspended -> blockiert

## Live-Blockgruende (deutsch)

Beispiele:

- Asset-Status ist unbekannt, Live bleibt blockiert.
- Asset ist delisted/suspended, Live ist gesperrt.
- Futures ohne ProductType sind fuer Live blockiert.
- Praezisionsdaten fehlen (Tick/Lot/Precision), Live bleibt blockiert.
- Datenqualitaet ist nicht ausreichend fuer Live.
- Liquiditaet ist zu niedrig, Live bleibt blockiert.
- Slippage ist zu hoch, Live bleibt blockiert.
- Kein Strategie-Evidence-Nachweis, Live bleibt blockiert.

## Return bei fehlender Discovery

Wenn Bitget-Discovery fehlt, zeigt die Konsole einen sicheren Zustand:

- Hinweis: Asset-Discovery-Daten fehlen.
- Live-Status bleibt blockiert.
- Verweis auf Diagnose/Health statt Fake-Live-Freigaben.

## Offene externe Abhaengigkeiten

- Echte Bitget-Discovery-Feeds und stabile Metadatenpipeline
- Verifizierbare Evidence je Asset-Klasse fuer Live-Gates
- Operative Freigabeprozesse fuer Tier-Upgrade und Live-Zulassung
