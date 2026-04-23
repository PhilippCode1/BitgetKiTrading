from __future__ import annotations

import logging
import time
from typing import Any

from shared_py.eventbus import RedisStreamBus
from shared_py.eventbus.envelope import STREAM_ONCHAIN_WHALE_DETECTION, EventEnvelope

logger = logging.getLogger("onchain_sniffer.publish")


def publish_onchain_whale_detection(
    bus: RedisStreamBus,
    *,
    source_chain: str,
    dex: str,
    token_pair: str,
    estimated_volume_usd: float,
    direction: str,
    tx_hash: str,
    estimated_slippage_bps: float,
    t_discovered_ms: int,
    extra: dict[str, Any] | None = None,
) -> str:
    t1 = int(time.time() * 1000)
    latency_ms = max(0, t1 - t_discovered_ms)
    sym = token_pair.replace("/", "-").replace("→", "-")[:32] or "ONCHAIN"
    env = EventEnvelope(
        event_type="onchain_whale_detection",
        symbol=sym.upper()[:32],
        dedupe_key=f"{source_chain}:{tx_hash}",
        payload={
            "event_name": "ONCHAIN_WHALE_DETECTION",
            "source_chain": source_chain,
            "dex": dex,
            "token_pair": token_pair,
            "estimated_volume_usd": round(float(estimated_volume_usd), 2),
            "direction": direction,
            "timestamp_ms": t_discovered_ms,
            "tx_hash": tx_hash,
            "estimated_slippage_bps": round(float(estimated_slippage_bps), 4),
            **(extra or {}),
        },
        trace={
            "source": "onchain-sniffer",
            "latency_discovery_to_publish_ms": latency_ms,
            "published_ts_ms": t1,
        },
    )
    mid = bus.publish(STREAM_ONCHAIN_WHALE_DETECTION, env)
    logger.info(
        "ONCHAIN_WHALE_DETECTION chain=%s vol_usd=%.0f slip_bps=%.2f latency_ms=%s id=%s",
        source_chain,
        estimated_volume_usd,
        estimated_slippage_bps,
        latency_ms,
        mid,
    )
    return str(mid)
