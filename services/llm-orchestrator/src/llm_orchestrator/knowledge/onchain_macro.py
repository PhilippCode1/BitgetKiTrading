"""
On-Chain-Makro: letzte signifikante Whale-Events aus dem Eventbus-Stream (onchain-sniffer).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared_py.eventbus.envelope import STREAM_ONCHAIN_WHALE_DETECTION
from shared_py.redis_client import create_sync_connection_pool, sync_redis_from_pool

logger = logging.getLogger("llm_orchestrator.knowledge.onchain_macro")

# Optional: Zusatzfilter; 0 = letzte N Events aus dem Stream (Sniffer setzt min_notional selbst).
_DEFAULT_MIN_NOTIONAL_USD = 0.0


def _format_whale_line_de(payload: dict[str, Any]) -> str:
    """Eine lesbare DE-Zeile pro Event (Audit / operator_explain)."""
    p = payload if isinstance(payload, dict) else {}
    usd = float(p.get("estimated_volume_usd") or 0.0)
    dex = str(p.get("dex") or "?")
    pair = str(p.get("token_pair") or "?")
    direction = str(p.get("direction") or "?").lower()
    chain = str(p.get("source_chain") or "?")
    if direction in ("sell", "short", "abverkauf"):
        flow = "Abverkaufs-/Swap-Druck (sell-lastend)"
    elif direction in ("buy", "long", "einkauf"):
        flow = "Kauf-/Swap-Dynamik (buy-lastend)"
    else:
        flow = f"Richtung={direction}"
    m_usd = usd / 1_000_000.0
    if m_usd >= 0.1:
        vol = f"~{m_usd:.2f}M USD-Äquivalent"
    else:
        vol = f"~{usd:,.0f} USD-Äquivalent"
    return (
        f"On-Chain / Whale: {flow}, Paar {pair} auf {dex} ({chain}), {vol}."
    )


def _format_whale_line_en(payload: dict[str, Any]) -> str:
    """
    EN-Zeile (DoD: explizit „Whale“ + On-Chain-Kontext; ggf. CEX-artige Namen aus dex).
    """
    p = payload if isinstance(payload, dict) else {}
    usd = float(p.get("estimated_volume_usd") or 0.0)
    dex = str(p.get("dex") or "unknown_venue")
    pair = str(p.get("token_pair") or "unknown")
    direction = str(p.get("direction") or "unknown").lower()
    chain = str(p.get("source_chain") or "")
    m_usd = usd / 1_000_000.0
    vol = f"{m_usd:.2f}M USD" if m_usd >= 0.1 else f"{usd:,.0f} USD"
    inflow = direction in ("sell", "short")  # in DEX-Frame: eingebrachte Verkaufsseite
    act = "Whale inflow / heavy sell-side activity" if inflow else "Whale activity / large DEX notional"
    cex = dex.lower()
    venue = dex
    if "binance" in cex:
        venue = "Binance (router label)"
    to_part = f" to {venue}" if venue else ""
    return (
        f"On-Chain: {act} detected: est. {vol} notional, {pair}{to_part} "
        f"({chain}) [direction={direction}]."
    )


def build_readonly_onchain_text(ctx: dict[str, Any]) -> str:
    """
    Baut den sichtbaren onchain_macro-Text aus Kontext
    (nach merge in operator_explain / BFF-JSON).
    """
    if not isinstance(ctx, dict):
        return ""
    om = ctx.get("onchain_macro")
    if isinstance(om, dict):
        s = _format_bullet_lines_de_en(om)
        if s.strip():
            return s
    octx = ctx.get("onchain_context")
    if not isinstance(octx, dict):
        return ""
    evs = octx.get("recent_onchain_whale_events_json") or []
    if not isinstance(evs, list) or not evs:
        return ""
    de: list[str] = []
    en: list[str] = []
    for e in evs:
        if not isinstance(e, dict):
            continue
        de.append(_format_whale_line_de(e))
        en.append(_format_whale_line_en(e))
    return _format_bullet_lines_de_en({"lines_de": de, "lines_en": en})


def _format_bullet_lines_de_en(om: dict[str, Any]) -> str:
    de = [str(x).strip() for x in (om.get("lines_de") or []) if str(x).strip()]
    en = [str(x).strip() for x in (om.get("lines_en") or []) if str(x).strip()]
    if not de and not en:
        return ""
    out: list[str] = []
    n = max(len(de), len(en))
    for i in range(n):
        d = de[i] if i < len(de) else ""
        e = en[i] if i < len(en) else ""
        if d and e:
            out.append(f"- {d}\n  (en) {e}")
        elif d:
            out.append(f"- {d}")
        elif e:
            out.append(f"- (en) {e}")
    return "\n".join(out)


def merge_fetched_onchain_into_context(
    target: dict[str, Any] | None,
    fetched: dict[str, Any] | None,
) -> dict[str, Any]:
    """Ergänzt / überschreibt onchain_context + onchain_macro, Druck = max(alt, neu)."""
    out: dict[str, Any] = (
        {**target} if isinstance(target, dict) else {}
    )
    if not isinstance(fetched, dict):
        return out
    octx_f = fetched.get("onchain_context") or {}
    if not isinstance(octx_f, dict) or not octx_f.get("recent_onchain_whale_events_json"):
        return out
    prev = out.get("onchain_context")
    if not isinstance(prev, dict):
        prev = {}
    p_old = float(prev.get("onchain_whale_pressure_0_1") or 0.0)
    p_new = float(octx_f.get("onchain_whale_pressure_0_1") or 0.0)
    octx = {**prev, **octx_f}
    octx["onchain_whale_pressure_0_1"] = max(p_old, p_new)
    out["onchain_context"] = octx
    om_prev = out.get("onchain_macro")
    if not isinstance(om_prev, dict):
        om_prev = {}
    om_f = fetched.get("onchain_macro")
    if isinstance(om_f, dict) and om_f.get("lines_de"):
        out["onchain_macro"] = {**om_prev, **om_f}
    return out


def _pressure_from_events(events: list[dict[str, Any]]) -> float:
    if not events:
        return 0.0
    vol = 0.0
    for e in events:
        if not isinstance(e, dict):
            continue
        try:
            vol += float(e.get("estimated_volume_usd") or 0.0)
        except (TypeError, ValueError):
            continue
    return max(0.0, min(1.0, vol / 5_000_000.0))


def _envelope_to_inner_payload(
    data_obj: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(data_obj, dict):
        return None
    p = data_obj.get("payload")
    if not isinstance(p, dict):
        return None
    if p.get("event_name") == "ONCHAIN_WHALE_DETECTION" or "estimated_volume_usd" in p:
        return p
    return None


def fetch_onchain_macro_context(
    redis_url: str,
    *,
    limit: int = 5,
    min_notional_usd: float = _DEFAULT_MIN_NOTIONAL_USD,
) -> dict[str, Any]:
    """
    Liest die letzten ``limit`` Whale-Events aus ``events:onchain_whale_detection``
    (Redis Stream), filtert signifikant nach Notional, liefert Struktur für
    ``onchain_context`` + lesbare Zeilen.
    """
    empty: dict[str, Any] = {
        "onchain_context": {
            "onchain_whale_pressure_0_1": 0.0,
            "recent_onchain_whale_events_json": [],
            "onchain_fetch_source": "empty",
        },
        "onchain_macro": {
            "lines_de": [],
            "lines_en": [],
        },
    }
    if not (redis_url or "").strip():
        empty["onchain_context"]["onchain_fetch_source"] = "skip_no_redis"
        return empty

    pool: Any = None
    r: Any = None
    items: list[tuple[str, dict[str, str]]] = []
    try:
        pool = create_sync_connection_pool(
            redis_url,
            decode_responses=True,
            max_connections=4,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        r = sync_redis_from_pool(pool, health_check_interval=30)
        items = r.xrevrange(
            STREAM_ONCHAIN_WHALE_DETECTION,
            max="+",
            min="-",
            count=max(1, min(50, limit * 3)),
        )
    except Exception as exc:
        logger.warning("onchain_macro: redis: %s", exc)
        out = dict(empty)
        out["onchain_context"] = {**out["onchain_context"], "onchain_fetch_source": "error"}
        return out
    finally:
        if r is not None:
            try:
                r.close()
            except Exception:  # pragma: no cover
                pass
        if pool is not None:
            try:
                pool.disconnect()
            except Exception:  # pragma: no cover
                pass

    collected: list[dict[str, Any]] = []
    for _msg_id, fields in items or []:
        if not isinstance(fields, dict):
            continue
        raw = fields.get("data") or ""
        if not raw:
            continue
        try:
            data_obj = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            continue
        inner = _envelope_to_inner_payload(
            data_obj if isinstance(data_obj, dict) else None
        )
        if not inner:
            continue
        try:
            u = float(inner.get("estimated_volume_usd") or 0.0)
        except (TypeError, ValueError):
            u = 0.0
        if min_notional_usd > 0 and u < min_notional_usd:
            continue
        collected.append(inner)
        if len(collected) >= limit:
            break

    if not collected:
        return empty

    pr = _pressure_from_events(collected)
    lines_de = [_format_whale_line_de(x) for x in collected]
    lines_en = [_format_whale_line_en(x) for x in collected]
    return {
        "onchain_context": {
            "onchain_whale_pressure_0_1": pr,
            "recent_onchain_whale_events_json": collected,
            "onchain_fetch_source": "redis_stream",
        },
        "onchain_macro": {
            "lines_de": lines_de,
            "lines_en": lines_en,
        },
    }
