"""
P75: Runtime-Safety-Oracle — Axiom-Pruefungen (DB/Redis) unabhaengig von Geschaeftslogik.

Diese Schicht dient als letzte Verteidigungslinie: Verletzungen triggern ``system:global_halt`` und
einen kritischen Operator-/System-Alert (Telegram-Pipeline via alert-engine, sobald gepubliziert).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable, Mapping

import psycopg
from psycopg import errors as pg_errors
from redis import Redis
from redis.exceptions import RedisError

def _d_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None

logger = logging.getLogger("shared_py.runtime_safety_oracle")


@dataclass(frozen=True, slots=True)
class RuntimeSafetyConfig:
    """Axiom-Grenzen (institutionell, konservativ)."""

    notional_to_equity_max: Decimal = Decimal("10")
    max_position_leverage: Decimal = Decimal("125")
    poll_interval_sec: float = 0.5
    """Default 500ms-Takt (Prompt 75)."""
    telegram_dedupe_sec: float = 60.0


@dataclass(frozen=True, slots=True)
class SafetyAxiom:
    id: str
    message: str
    details: dict[str, Any]


def _dec(v: Any) -> Decimal | None:
    return _d_decimal(v)


def _parse_account_equity_usd(raw: Mapping[str, Any] | None) -> Decimal | None:
    """
    Liest Konto-Equity (USDT-Familie) aus exchange_snapshots.raw_data (reconcile-Format).
    """
    if not raw or not isinstance(raw, dict):
        return None
    for key in (
        "usdtEquity",
        "accountEquity",
        "equity",
        "accountEquityUsd",
        "totalEquity",
        "equityUSD",
    ):
        if key in raw:
            d = _dec(raw.get(key))
            if d is not None and d > 0:
                return d
    items = raw.get("items")
    if not isinstance(items, list) or not items:
        return None
    for it in items:
        if not isinstance(it, dict):
            continue
        ch = str(it.get("marginCoin") or it.get("coin") or "").upper()
        if ch and ch != "USDT" and "USD" not in ch:
            continue
        d = _dec(
            it.get("equity")
            or it.get("accountEquity")
            or it.get("usdtEquity")
            or it.get("totalEquity")
            or it.get("available")
        )
        if d is not None and d > 0:
            return d
    return None


def _latest_account_raw(conn: Any) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT raw_data
        FROM live.exchange_snapshots
        WHERE snapshot_type = 'account'
        ORDER BY created_ts DESC
        LIMIT 1
        """,
    ).fetchone()
    if row is None:
        return None
    m = row.get("raw_data")
    if isinstance(m, str):
        try:
            m = json.loads(m)
        except Exception:
            return None
    if not isinstance(m, dict):
        return None
    return m


def check_axiom_notional_equity_breach(
    rows: list[Mapping[str, Any]], *, equity: Decimal | None, max_mult: Decimal
) -> SafetyAxiom | None:
    total = Decimal("0")
    for r in rows:
        n = _dec(r.get("notional_value"))
        if n is not None:
            total += abs(n)
    if equity is None or equity <= 0:
        return None
    if max_mult > 0 and total > equity * max_mult:
        return SafetyAxiom(
            id="AXIOM_NOTIONAL_EQUITY_BREACH",
            message="Summe |Notional| uebersteigt Equity * Faktor (Axiom).",
            details={
                "total_notional": str(total),
                "equity_usd": str(equity),
                "max_mult": str(max_mult),
            },
        )
    return None


def check_axiom_nonpositive_balance_proxy(
    equity: Decimal | None, *, has_open_risk: bool
) -> SafetyAxiom | None:
    if not has_open_risk or equity is None:
        return None
    if equity < 0:
        return SafetyAxiom(
            id="AXIOM_NONPOSITIVE_EQUITY",
            message="Geparste Equity <= 0 bei riskanter Positionslast.",
            details={"equity": str(equity)},
        )
    return None


def check_axiom_negative_position_numerics(rows: list[Mapping[str, Any]]) -> SafetyAxiom | None:
    for r in rows:
        row = dict(r) if not isinstance(r, dict) else r
        sz = _dec(row.get("size_base"))
        n = _dec(row.get("notional_value"))
        for label, d in (("size_base", sz), ("notional_value", n)):
            if d is not None and d < 0:
                return SafetyAxiom(
                    id="AXIOM_NEGATIVE_POSITION_NUMERIC",
                    message=f"Negativer {label} in live.positions (inkonsistenter Zustand).",
                    details={"row": {k: str(v) for k, v in row.items() if k in ("inst_id", "hold_side", label)}},
                )
    return None


def check_axiom_excess_margin_leverage(
    rows: list[Mapping[str, Any]], *, max_lev: Decimal
) -> SafetyAxiom | None:
    for r in rows:
        m = _dec(r.get("margin"))
        n = _dec(r.get("notional_value"))
        if m is None or n is None or m <= 0:
            continue
        if abs(n) / m > max_lev + Decimal("0.0001"):
            return SafetyAxiom(
                id="AXIOM_EXCESS_LEVERAGE",
                message="|Notional|/Margin > erlaubtes Max-Hebel (Axiom).",
                details={"inst_id": r.get("inst_id"), "ratio": str(abs(n) / m), "max": str(max_lev)},
            )
    return None


def check_axiom_ghost_futures_order(rows: list[Mapping[str, Any]]) -> SafetyAxiom | None:
    """
    Live-Order in Arbeit ohne Execution-Bindung: futures mit exchange_order_id aber
    source_execution_decision_id IS NULL.
    """
    for r in rows:
        if str(r.get("market_family") or "").lower() != "futures":
            continue
        if not r.get("exchange_order_id"):
            continue
        if r.get("source_execution_decision_id") is not None:
            continue
        st = str(r.get("status") or "").lower()
        if st in {
            "canceled",
            "filled",
            "error",
            "replaced",
            "flattened",
            "flatten_failed",
            "timed_out",
        }:
            continue
        return SafetyAxiom(
            id="AXIOM_GHOST_FUTURES_ORDER",
            message="Aktive Futures-Order mit Exchange-Id ohne source_execution_decision_id.",
            details={
                "internal_order_id": str(r.get("internal_order_id")),
                "client_oid": str(r.get("client_oid") or "")[:64],
            },
        )
    return None


def check_axiom_absurd_notional(
    rows: list[Mapping[str, Any]], *, cap: Decimal
) -> SafetyAxiom | None:
    for r in rows:
        n = _dec(r.get("notional_value"))
        if n is not None and abs(n) > cap:
            return SafetyAxiom(
                id="AXIOM_ABSOLUTE_NOTIONAL_CAP",
                message="Einzel-Position Notional > absolutes Sicherheits-Limit (Manipulation/Drift).",
                details={"inst_id": r.get("inst_id"), "notional_value": str(n), "cap": str(cap)},
            )
    return None


def _fingerprint_violation(v: SafetyAxiom) -> str:
    j = json.dumps(
        {"id": v.id, "details": v.details},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(j.encode()).hexdigest()[:24]


def _load_positions(conn: Any) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT notional_value, size_base, margin, inst_id, product_type, hold_side, entry_price, source, raw_json
            FROM live.positions
            """
        ).fetchall()
    except (pg_errors.Error, OSError) as exc:
        logger.debug("safety-oracle: live.positions skipped: %s", exc)
        return []
    return [dict(x) for x in rows]


def _load_suspect_orders(conn: Any) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT internal_order_id, market_family, exchange_order_id, source_execution_decision_id, status, client_oid
            FROM live.orders
            WHERE LOWER(COALESCE(status, '')) NOT IN (
                'canceled', 'filled', 'error', 'replaced', 'flattened', 'flatten_failed', 'timed_out'
            )
            AND exchange_order_id IS NOT NULL
            """
        ).fetchall()
    except (pg_errors.Error, OSError) as exc:
        logger.debug("safety-oracle: live.orders skip: %s", exc)
        return []
    return [dict(x) for x in rows]


class RuntimeSafetyOracle:
    """
    Unabhaengige Axiom-Pruefung. ``run`` erwartet eine offene :class:`psycopg.Connection`.
    """

    def __init__(self, *, config: RuntimeSafetyConfig = RuntimeSafetyConfig()) -> None:
        self._cfg = config
        self._last_tg_at: float = 0.0
        self._halted_fp: set[str] = set()
        self._max_abs_notional: Decimal = Decimal("100_000_000")  # 100M USDT — Doomsday-Cap

    def evaluate_invariants(
        self,
        conn: Any,
        *,
        equity_override: Decimal | None = None,
    ) -> list[SafetyAxiom]:
        out: list[SafetyAxiom] = []
        positions = _load_positions(conn)
        orders = _load_suspect_orders(conn)
        eq = equity_override
        if eq is None:
            ar = _latest_account_raw(conn)
            if ar is not None:
                eq = _parse_account_equity_usd(ar)
        nneg = check_axiom_negative_position_numerics(positions)
        if nneg:
            out.append(nneg)
        gho = check_axiom_ghost_futures_order(orders)
        if gho:
            out.append(gho)
        exl = check_axiom_excess_margin_leverage(
            positions, max_lev=self._cfg.max_position_leverage
        )
        if exl:
            out.append(exl)
        absv = check_axiom_absurd_notional(positions, cap=self._max_abs_notional)
        if absv:
            out.append(absv)
        nxb = check_axiom_notional_equity_breach(
            positions, equity=eq, max_mult=self._cfg.notional_to_equity_max
        )
        if nxb:
            out.append(nxb)
        has_open = any(
            (abs(_dec(p.get("notional_value")) or Decimal("0")) > 0)
            or (abs(_dec(p.get("size_base")) or Decimal("0")) > 0)
            for p in positions
        )
        npb = check_axiom_nonpositive_balance_proxy(eq, has_open_risk=has_open)
        if npb:
            out.append(npb)
        return out

    def maybe_emit_side_effects(
        self,
        violations: list[SafetyAxiom],
        *,
        now: float | None = None,
        redis_url: str = "",
        publish_halt: Callable[[bool], None] | None,
        force_latch: Callable[[str], None] | None,
        publish_system_alert: Callable[..., None] | None = None,
        publish_operator_intel: Callable[..., None] | None = None,
        bus: Any = None,
        symbol: str = "SAFETY",
    ) -> None:
        if not violations:
            return
        t = now if now is not None else time.time()
        fp0 = _fingerprint_violation(violations[0])
        is_new_halt = fp0 not in self._halted_fp
        if is_new_halt and publish_halt is not None:
            try:
                publish_halt(True)
            except Exception as exc:
                logger.critical("safety-oracle: publish_halt failed: %s", exc)
        if is_new_halt and force_latch is not None:
            rsn = f"runtime_safety_oracle:{violations[0].id}"
            try:
                force_latch(rsn)
            except Exception as exc:
                logger.critical("safety-oracle: force_latch failed: %s", exc)
        u = (redis_url or "").strip()
        if is_new_halt and u and publish_halt is None:
            try:
                r = Redis.from_url(u, socket_connect_timeout=1, socket_timeout=2, decode_responses=True)
                r.set("system:global_halt", "1")
                r.publish("system:global_halt:pub", "1")
            except (RedisError, OSError) as exc:
                logger.critical("safety-oracle: direct redis SET failed: %s", exc)
        if is_new_halt:
            self._halted_fp.add(fp0)
        v0 = violations[0]
        can_telegram = t - self._last_tg_at >= float(self._cfg.telegram_dedupe_sec)
        if not can_telegram:
            return
        self._last_tg_at = t
        if publish_system_alert and bus is not None:
            try:
                publish_system_alert(
                    bus,
                    alert_key=f"CRITICAL_SAFETY_VIOLATION:{v0.id}",
                    severity="critical",
                    title="CRITICAL_SAFETY_VIOLATION",
                    message=v0.message,
                    details={**v0.details, "axiom_id": v0.id, "all": [x.id for x in violations[:8]]},
                )
            except Exception as exc:
                logger.warning("safety-oracle: system_alert: %s", exc)
        if publish_operator_intel and bus is not None:
            try:
                from shared_py.operator_intel import build_operator_intel_envelope_payload

                pl = build_operator_intel_envelope_payload(
                    intel_kind="CRITICAL_SAFETY_VIOLATION",
                    symbol=symbol,
                    severity="critical",
                    market_family="futures",
                    reasons=[v.message for v in violations[:5]],
                    dedupe_key=f"oracle:{fp0}",
                    extra={"violations": [v.id for v in violations]},
                )
                publish_operator_intel(
                    bus,
                    symbol=symbol,
                    payload=pl,
                    timeframe=None,
                    trace={"source": "runtime_safety_oracle", "axiom_fingerprint": fp0},
                )
            except Exception as exc:
                logger.warning("safety-oracle: operator_intel: %s", exc)
