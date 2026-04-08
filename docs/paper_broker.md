# Paper-Broker (Prompt 18)

Produktionsnaher **Simulations**-Microservice fuer kataloggebundene Bitget-Instrumente. Der Paper-Pfad konsumiert denselben Instrumentenkatalog / Metadatenlayer wie die produktionsnahen Dienste; Kontrakt- und Gebuehrenkontext werden bei Opens **aus dem Signal** (`market_family`, `product_type`, …) aufgeloest, sofern gesetzt. Migration `560_paper_broker_multi_asset_audit.sql`: Positions-Spalten fuer Lern-Spiegelung und erweiterte `paper.strategy_events`-Typen (u. a. `NO_TRADE_GATE`, `PLAN_SNAPSHOT`, `POST_TRADE_REVIEW_READY`).

## Gebuehren (Bitget-konform)

- Transaktionsgebuehr: `fee = (qty_base * price) * fee_rate` (Orderwert × Rate).
- Konfiguration: `ContractConfigProvider` im Modus `fixture` laedt zuerst `fixtures/contract_config_{fam}_{symbol}.json` bzw. `contract_config_{symbol}.json`, sonst Legacy-Fallback `contract_config_btcusdt.json`. Beispiele: `contract_config_btcusdt.json`, `contract_config_ethusdt.json`.
  Modus `live`: oeffentlicher REST `GET /api/v2/mix/market/contracts`, Snapshot in `paper.contract_config_snapshots`.
- Fallback: `PAPER_FEE_SOURCE=env` nutzt `PAPER_DEFAULT_MAKER_FEE` / `PAPER_DEFAULT_TAKER_FEE`.
- Der Paper-Pfad zieht Preis-/Mengenpraezision, max. Hebel und weitere Instrumentgrenzen aus dem zentralen Instrumentenkatalog, soweit vorhanden.

## Funding

- Betrag: `raw = position_value_usdt * funding_rate` mit `position_value_usdt = |qty * mark|`.
- Cashflow je Position: `funding_usdt = -raw` fuer **Long**, `+raw` fuer **Short**
  (positiver Satz → Long zahlt; negativer Satz → Long erhaelt / Short zahlt).
- Zeitplan: aus `events:funding_update` (Market-Stream) bzw. SIM `POST /paper/sim/funding`
  oder spaeter REST `current-fund-rate` (Prompt-Hinweis; optional erweiterbar).

## Preise

1. **SIM**: `POST /paper/sim/market` setzt Bid/Ask/Last/Mark.
2. **TSDB**: letzter `tsdb.ticker`, optional `tsdb.orderbook_levels` fuer Slippage (Top-N).
3. **REST**: `GET /api/v2/mix/market/symbol-price` (public).

## Slippage (deterministisch)

- Vorhandenes Orderbuch: „Walk the book“ (Buy → Asks, Sell → Bids), bis `PAPER_ORDERBOOK_LEVELS`.
- Sonst synthetische Tiefe aus Best Bid/Ask + `priceEndStep` aus Contract-Config.
- Fallback: Mark/Last ± `PAPER_DEFAULT_SLIPPAGE_BPS`.

## Liquidation (**Approx**)

Kein 1:1 Bitget-Tiering. Konfigurierbar:

- `maintenance_margin_rate = PAPER_MMR_BASE` (Default 0.005)
- `equity = isolated_margin + unrealized_pnl - sum(fees) + sum(funding_ledger)`  
  (Fees reduzieren Margin-Puffer; Funding-Summe signed wie gebucht.)
- Liquidation wenn  
  `equity <= notional * maintenance_margin_rate + PAPER_LIQ_FEE_BUFFER_USDT`
- State `liquidated`, Event `trade_closed` mit `reason=LIQUIDATED_APPROX`.

## Datenbank

Migration `110_paper_broker_core.sql`, Schema `paper.*` (Accounts, Positions, Orders, Fills,
`fee_ledger`, `funding_ledger`, Contract-Snapshots).

## HTTP

| Methode | Pfad                          | Zweck                                      |
| ------- | ----------------------------- | ------------------------------------------ |
| GET     | `/health`                     | DB + Redis                                 |
| POST    | `/paper/accounts/bootstrap`   | Account anlegen                            |
| POST    | `/paper/positions/open`       | Position oeffnen                           |
| POST    | `/paper/positions/{id}/close` | Teil-/Vollschluss                          |
| POST    | `/paper/process_tick`         | MTM, Funding-Zeit, Liquidation (SIM/Tests) |
| POST    | `/paper/sim/market`           | SIM-Preise                                 |
| POST    | `/paper/sim/funding`          | SIM-Funding-Schedule                       |

## Events (Redis)

- `events:trade_opened`, `events:trade_updated`, `events:trade_closed`, `events:funding_booked`
- Worker (wenn `PAPER_SIM_MODE=false`): konsumiert `events:market_tick`, `events:funding_update`.

## Sicherheit

Keine API-Keys im Repo. Nur oeffentliche Bitget-Endpoints optional. Secrets via `.env.local` / spaeter Vault.

## Offener Major-Blocker

Der Paper-Broker enthaelt weiterhin einen prod-nah problematischen Fixture-Fallback im Contract-Pfad. Das ist im aktuellen Audit bewusst als **major** offen markiert und muss fuer ein voll release-grade Produktionsziel noch entfernt oder haerter gegated werden.
