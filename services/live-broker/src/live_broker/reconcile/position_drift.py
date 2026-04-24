"""Aktive Positions-Drift: DB live.positions vs. Bitget GET all_positions (Reconcile-Zyklus)."""

from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Any

from live_broker.config import LiveBrokerSettings
from live_broker.events import publish_system_alert
from live_broker.global_halt_latch import publish_global_halt_state
from live_broker.persistence.repo import LiveBrokerRepository
from live_broker.private_rest import BitgetPrivateRestClient
from live_broker.reconcile.rest_catchup import _positions_items_from_payload
from shared_py.eventbus import RedisStreamBus

logger = logging.getLogger("live_broker.reconcile.position_drift")


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def notional_from_bitget_item(item: dict[str, Any]) -> Decimal | None:
    """Schaetzwert in Quote (z. B. USDT) fuer Prozent-Drift; linear futures: size * open."""
    total = _to_decimal(item.get("total")) or _to_decimal(item.get("available"))
    px = _to_decimal(item.get("openPriceAvg") or item.get("openAvgPrice") or item.get("markPrice"))
    if total is not None and px is not None and total != 0 and px != 0:
        return (total * px).copy_abs()
    margin = _to_decimal(item.get("margin") or item.get("marginSize"))
    lev = _to_decimal(item.get("leverage")) or Decimal("1")
    if margin is not None and lev is not None and lev > 0 and margin > 0:
        return (margin * lev).copy_abs()
    return None


def position_key_from_bitget_item(item: dict[str, Any]) -> tuple[str, str, str] | None:
    inst = str(item.get("instId") or item.get("symbol") or "").strip().upper()
    if not inst:
        return None
    side = str(item.get("holdSide") or item.get("posSide") or "").strip().lower()
    if side not in ("long", "short"):
        return None
    ptype = str(item.get("productType") or item.get("product_type") or "").strip().upper()
    return (inst, ptype, side)


def run_position_drift_once(
    *,
    settings: LiveBrokerSettings,
    repo: LiveBrokerRepository,
    private: BitgetPrivateRestClient,
    bus: RedisStreamBus | None,
) -> dict[str, Any]:
    if not settings.private_exchange_access_enabled:
        return {"skipped": True, "reason": "private_exchange_access_disabled"}
    started = time.monotonic()
    try:
        presp = private.list_all_positions(priority=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("position drift: list_all_positions failed: %s", exc)
        return {
            "ok": False,
            "error": str(exc)[:300],
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    ex_items = _positions_items_from_payload(presp.payload)
    local_rows = repo.list_live_positions()
    local_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in local_rows:
        k = (
            str(row.get("inst_id") or "").strip().upper(),
            str(row.get("product_type") or "").strip().upper(),
            str(row.get("hold_side") or "").strip().lower(),
        )
        if k[0] and k[2] in ("long", "short"):
            local_map[k] = row

    ex_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for it in ex_items:
        k = position_key_from_bitget_item(it)
        if k is not None:
            ex_map[k] = it

    ha_ratio = Decimal(str(settings.live_broker_position_notional_halt_ratio))
    ghosts: list[dict[str, str]] = []
    notional_mismatches: list[dict[str, Any]] = []

    for k, it in ex_map.items():
        n_ex = notional_from_bitget_item(it)
        if k not in local_map:
            repo.upsert_live_position_from_bitget(
                {
                    "inst_id": k[0],
                    "product_type": k[1],
                    "hold_side": k[2],
                    "raw_json": it,
                    "source": "reconcile_shadow_sync",
                },
                notional_value=n_ex,
            )
            ghosts.append(
                {
                    "inst_id": k[0],
                    "hold_side": k[2],
                    "product_type": k[1],
                }
            )
            if bus is not None:
                try:
                    publish_system_alert(
                        bus,
                        alert_key="live-broker:GHOST_POSITION_DETECTED",
                        severity="critical",
                        title="GHOST position — exchange ja, DB nein (Shadow-Sync ausgefuehrt)",
                        message=(
                            f"Reconcile: Position {k[0]} {k[2]} (product={k[1] or 'n/a'}) auf Bitget, "
                            "fehlte in live.positions — DB-Zeile angelegt."
                        ),
                        details={
                            "inst_id": k[0],
                            "product_type": k[1],
                            "hold_side": k[2],
                            "notional_estimate": str(n_ex) if n_ex is not None else None,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("GHOST alert publish failed: %s", exc)
            continue

        n_loc = _to_decimal(local_map[k].get("notional_value"))
        if n_ex is not None and n_loc is not None and n_ex > 0 and n_loc > 0:
            diff = (n_ex - n_loc).copy_abs()
            denom = max(n_ex, n_loc)
            if denom > 0 and (diff / denom) > ha_ratio:
                notional_mismatches.append(
                    {
                        "key": list(k),
                        "exchange_notional": str(n_ex),
                        "local_notional": str(n_loc),
                    }
                )
                u = (settings.redis_url or "").strip()
                if u:
                    try:
                        publish_global_halt_state(u, True)
                    except Exception as exc:  # noqa: BLE001
                        logger.error("global_halt publish failed: %s", exc)
                    if bus is not None:
                        try:
                            publish_system_alert(
                                bus,
                                alert_key="live-broker:POSITION_NOTIONAL_DIVERGENCE_HALT",
                                severity="critical",
                                title="Global halt — Positions-Notional-Drift > Schwellwert",
                                message=(
                                    f"Notional-Differenz > {float(ha_ratio) * 100:.1f}% fuer {k[0]} — "
                                    "system:global_halt aktiviert."
                                ),
                                details=notional_mismatches[-1] if notional_mismatches else {},
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("notional halt alert failed: %s", exc)
                else:
                    logger.critical("notional halt needed but redis_url leer")

        repo.upsert_live_position_from_bitget(
            {
                "inst_id": k[0],
                "product_type": k[1],
                "hold_side": k[2],
                "raw_json": it,
                "source": "reconcile_shadow_sync",
            },
            notional_value=n_ex,
        )

    removed = 0
    for k, loc in list(local_map.items()):
        if k in ex_map:
            continue
        t = _to_decimal(loc.get("size_base"))
        if t is not None and t != 0 and repo.delete_live_position(k[0], k[1], k[2]):
            removed += 1

    return {
        "ok": True,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "exchange_open_count": len(ex_map),
        "local_count_before": len(local_map),
        "ghosts_repaired": len(ghosts),
        "notional_mismatch_triggers": len(notional_mismatches),
        "zombie_local_rows_removed": removed,
        "ghosts": ghosts,
    }
