# Instrument Precision und Order-Parameter-Vertrag

## Warum Symbol allein nicht reicht

Ein Symbol ohne ProductType, MarginCoin, Precision und Min-Grenzen ist fuer
institutionelles Multi-Asset-Trading unzureichend. Spot, Margin und Futures
haben unterschiedliche Vertragsparameter und Fail-Closed-Regeln.

## Spot vs Margin vs Futures

- Spot: kein Futures-Leverage-Kontext.
- Margin: AccountMode ist relevant.
- Futures: ProductType und MarginCoin sind Pflicht.

## ProductType- und MarginCoin-Regeln

- Futures ohne `product_type` blockieren.
- Futures ohne `margin_coin` blockieren.
- `product_type`/`margin_coin`-Mismatch zwischen Signal und Instrument blockiert.

## Precision- und Rounding-Regeln

- Preis wird per `tick_size` nach unten gerundet.
- Menge wird per `lot_size` nach unten gerundet.
- Kein Aufrunden, das Risiko erhoeht.
- Unbekannte Precision blockiert live.

## MinQty und MinNotional

- `min_qty` und `min_notional` werden nach Rounding geprueft.
- Unterschreitung blockiert den Live-Preflight.

## Stale Metadata

- `source_freshness_status in {stale, unknown}` blockiert live.

## Main-Console-Anzeige

Pro Asset zeigt die Main Console:

- ProductType
- MarginCoin
- Tick Size
- Lot Size
- MinQty
- MinNotional
- Live-Orderfaehig ja/nein
- deutscher Blockgrund

## No-Go-Regeln

- Kein Live-Submit ohne vollstaendigen Instrumentvertrag.
- Kein Live bei fehlender/unklarer Precision oder stale Metadaten.
- Kein Live bei ProductType-/MarginCoin-Mismatch.
