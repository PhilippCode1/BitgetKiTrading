"""Ethereum: WS `newPendingTransactions` + parallele HTTP `eth_getTransactionByHash`."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import OrderedDict

import httpx
import websockets
from prometheus_client import Counter, Histogram
from web3 import AsyncWeb3

try:
    from web3.providers.rpc import AsyncHTTPProvider
except ImportError:  # pragma: no cover
    try:
        from web3.providers.async_http import AsyncHTTPProvider
    except ImportError:
        AsyncHTTPProvider = None  # type: ignore[misc, assignment]

from onchain_sniffer.config import OnchainSnifferSettings
from onchain_sniffer.dex_routers import ETH_MAINNET_DEX_ROUTERS
from onchain_sniffer.eth_decode import decode_swap_context, selector_of
from onchain_sniffer.impact_rs import estimate_slippage_bps
from onchain_sniffer.publish import publish_onchain_whale_detection

logger = logging.getLogger("onchain_sniffer.eth_listener")

PENDING_SEEN = Counter("onchain_eth_pending_seen_total", "Rohe Pending-Hashes")
ROUTER_MATCH = Counter("onchain_eth_router_match_total", "Tx an DEX-Router")
WHALE_PUBLISH = Counter("onchain_eth_whale_publish_total", "Veroeffentlichte Wal-Events")
LATENCY_MS = Histogram(
    "onchain_eth_publish_latency_ms",
    "Zeit Pending-Erkennung bis Redis-Publish",
    buckets=(1, 2, 5, 10, 25, 50, 100, 250, 500, 2000),
)


class _Dedupe:
    def __init__(self, max_size: int) -> None:
        self._max = max_size
        self._m: OrderedDict[str, bool] = OrderedDict()

    def is_dup(self, h: str) -> bool:
        if h in self._m:
            self._m.move_to_end(h)
            return True
        self._m[h] = True
        self._m.move_to_end(h)
        while len(self._m) > self._max:
            self._m.popitem(last=False)
        return False


def _wei_value(tx: dict) -> int:
    v = tx.get("value")
    if v is None:
        return 0
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if s.startswith("0x"):
        return int(s, 16)
    return int(s)


async def _eth_get_tx(client: httpx.AsyncClient, http_url: str, tx_hash: str) -> dict | None:
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_getTransactionByHash",
        "params": [tx_hash],
    }
    try:
        r = await client.post(http_url, json=body, timeout=4.0)
        r.raise_for_status()
        data = r.json()
        res = data.get("result")
        return res if isinstance(res, dict) else None
    except Exception as exc:
        logger.debug("eth_getTransactionByHash failed hash=%s err=%s", tx_hash[:12], exc)
        return None


async def _process_hash(
    *,
    settings: OnchainSnifferSettings,
    client: httpx.AsyncClient,
    bus,
    dedupe: _Dedupe,
    tx_hash: str,
    t_seen_ms: int,
) -> None:
    if dedupe.is_dup(tx_hash):
        return
    tx = await _eth_get_tx(client, settings.eth_http_url or "", tx_hash)
    if not tx:
        return
    to_raw = tx.get("to")
    if not to_raw:
        return
    to_addr = str(to_raw).strip().lower()
    if to_addr not in ETH_MAINNET_DEX_ROUTERS:
        return
    ROUTER_MATCH.inc()
    ctx = decode_swap_context(tx, settings.eth_usd_mark)
    if not ctx:
        sel = selector_of(str(tx.get("input") or ""))
        wv = _wei_value(tx)
        if wv == 0 and sel:
            return
        if wv == 0:
            return
        vol = (wv / 1e18) * settings.eth_usd_mark
        ctx = {
            "dex": "router_unknown_decode",
            "token_pair": "ETH",
            "estimated_volume_usd": vol,
            "direction": "unknown",
        }
    vol = float(ctx.get("estimated_volume_usd") or 0.0)
    if vol < settings.min_notional_usd:
        return
    slip = estimate_slippage_bps(settings, vol)
    extra = {k: v for k, v in ctx.items() if k not in ("dex", "token_pair", "estimated_volume_usd", "direction")}
    publish_onchain_whale_detection(
        bus,
        source_chain="ethereum",
        dex=str(ctx.get("dex") or "unknown"),
        token_pair=str(ctx.get("token_pair") or "unknown"),
        estimated_volume_usd=vol,
        direction=str(ctx.get("direction") or "unknown"),
        tx_hash=tx_hash,
        estimated_slippage_bps=slip,
        t_discovered_ms=t_seen_ms,
        extra=extra,
    )
    WHALE_PUBLISH.inc()
    t_done = int(time.time() * 1000)
    LATENCY_MS.observe(max(0.0, float(t_done - t_seen_ms)))


async def run_eth_mempool_listener(settings: OnchainSnifferSettings, bus) -> None:
    if not settings.has_eth_stack:
        logger.warning("ETH WS/HTTP nicht gesetzt — Ethereum-Mempool-Sniffer deaktiviert")
        return
    dedupe = _Dedupe(settings.dedupe_cache_size)
    sem = asyncio.Semaphore(settings.max_pending_fetch_concurrency)
    assert settings.eth_ws_url and settings.eth_http_url

    async with httpx.AsyncClient() as shared_http:

        async def bounded(h: str, t_ms: int) -> None:
            async with sem:
                await _process_hash(
                    settings=settings,
                    client=shared_http,
                    bus=bus,
                    dedupe=dedupe,
                    tx_hash=h,
                    t_seen_ms=t_ms,
                )

        backoff = 1.0
        while True:
            try:
                async with websockets.connect(
                    settings.eth_ws_url,
                    max_size=32 * 1024 * 1024,
                    ping_interval=20,
                    ping_timeout=20,
                ) as ws:
                    await ws.send(
                        json.dumps(
                            {
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "eth_subscribe",
                                "params": ["newPendingTransactions"],
                            }
                        )
                    )
                    raw = await ws.recv()
                    sub_ack = json.loads(raw)
                    if sub_ack.get("error"):
                        raise RuntimeError(str(sub_ack["error"]))
                    logger.info("Ethereum pending subscription ok: %s", sub_ack.get("result"))
                    try:
                        if AsyncHTTPProvider is None:
                            raise RuntimeError("AsyncHTTPProvider nicht verfuegbar")
                        w3 = AsyncWeb3(AsyncHTTPProvider(settings.eth_http_url))
                        try:
                            cid = await w3.eth.chain_id
                        finally:
                            disc = getattr(w3.provider, "disconnect", None)
                            if disc is not None:
                                await disc()
                        logger.info("web3.py chain_id=%s (HTTP-Probe)", cid)
                    except Exception as exc:
                        logger.warning("web3.py chain probe failed: %s", exc)
                    backoff = 1.0
                    while True:
                        msg_raw = await ws.recv()
                        t_seen = int(time.time() * 1000)
                        msg = json.loads(msg_raw)
                        if msg.get("method") != "eth_subscription":
                            continue
                        params = msg.get("params") or {}
                        h = params.get("result")
                        if not isinstance(h, str) or not h.startswith("0x"):
                            continue
                        PENDING_SEEN.inc()
                        asyncio.create_task(bounded(h, t_seen))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("ETH mempool WS reconnect in %.1fs: %s", backoff, exc)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60.0)
