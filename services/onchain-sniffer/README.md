# onchain-sniffer (Apex On-Chain Sniffer)

Echtzeit-Mempool-Listener (Ethereum `newPendingTransactions` + parallele `eth_getTransactionByHash` über HTTP), Filter auf bekannte DEX-Router, Schätzung des Handelsvolumens und Publish von `onchain_whale_detection` (`ONCHAIN_WHALE_DETECTION`-Payload) auf den Redis-Eventbus.

## Konfiguration (ENV)

| Variable | Beschreibung |
|----------|----------------|
| `ETH_WS_URL` | WebSocket-RPC (Alchemy/QuickNode/eigener Node) |
| `ETH_HTTP_URL` | HTTPS-RPC für schnelle Tx-Fetches (parallel) |
| `SOLANA_WS_URL` | Optional; Solana-Deep-Subscribe ist noch Platzhalter |
| `ONCHAIN_MIN_NOTIONAL_USD` | Mindest-Notional in USD (Default 500000) |
| `ONCHAIN_ETH_USD_MARK` | ETH-USD-Mark für grobe Bewertung |
| `ONCHAIN_POOL_TVL_USD_HINT` | TVL-Hinweis für Rust-/Heuristik-Impact (Slippage bps) |
| `ONCHAIN_IMPACT_LIB_PATH` | Optional: `libonchain_impact.so` / `.dll` aus `shared_rs/onchain_impact` |
| `REDIS_URL` | Eventbus |

## Impact-Analyse (Rust)

Crate `shared_rs/onchain_impact`: CPMM-Slippage (`onchain_impact_cpmm_slippage_bps`) und Heuristik (`onchain_impact_heuristic_slippage_bps`).

## Endpoints

- `GET /health` — Prozess lebt
- `GET /ready` — Settings + Listener-Flags
- `GET /metrics` — Prometheus (inkl. Publish-Latenz-Histogramm)

## Latenz

Ziel &lt; 100 ms vom Pending-Eintreffen bis Redis-Publish: hängt stark von RPC-RTT und `eth_getTransactionByHash` ab; parallele Fetches (`ONCHAIN_MAX_PENDING_FETCH_CONCURRENCY`) und dedizierte HTTP-URL helfen.
