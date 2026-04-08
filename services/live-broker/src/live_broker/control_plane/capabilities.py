from __future__ import annotations

from typing import Any, Literal

from shared_py.bitget.instruments import BitgetEndpointProfile

CONTROL_PLANE_MATRIX_VERSION = "bitget-control-plane-v1"

ControlCategory = Literal[
    "instrument_discovery",
    "account_balance",
    "positions",
    "open_orders",
    "order_history",
    "fills",
    "order_create",
    "order_replace",
    "order_cancel",
    "cancel_all",
    "reduce_only",
    "leverage_config",
    "private_ws",
    "rest_reconcile_snapshot",
]

_WRITE_CATEGORIES: frozenset[str] = frozenset(
    {
        "order_create",
        "order_replace",
        "order_cancel",
        "cancel_all",
        "reduce_only",
        "leverage_config",
    }
)


def _path(p: str | None) -> str | None:
    s = str(p or "").strip()
    return s or None


def _row(
    category: str,
    *,
    supported: bool,
    execution_disabled: bool,
    reason: str,
    write: bool,
) -> dict[str, Any]:
    return {
        "category": category,
        "status": "supported" if supported else "execution_disabled",
        "execution_disabled": execution_disabled,
        "reason": reason,
        "write": write,
    }


def capability_matrix_for_profile(profile: BitgetEndpointProfile) -> list[dict[str, Any]]:
    """Explizite Matrix je Kategorie — keine stillschweigenden No-Ops."""
    rows: list[dict[str, Any]] = []

    disc = _path(profile.public_symbol_config_path)
    rows.append(
        _row(
            "instrument_discovery",
            supported=bool(disc),
            execution_disabled=not bool(disc),
            reason="ok" if disc else "missing_public_symbol_config_path",
            write=False,
        )
    )

    acct = _path(profile.private_account_assets_path)
    rows.append(
        _row(
            "account_balance",
            supported=bool(acct),
            execution_disabled=not bool(acct),
            reason="ok" if acct else "missing_private_account_assets_path",
            write=False,
        )
    )

    pos = _path(profile.private_positions_path)
    rows.append(
        _row(
            "positions",
            supported=bool(pos),
            execution_disabled=not bool(pos),
            reason="ok" if pos else "missing_private_positions_path",
            write=False,
        )
    )

    oo = _path(profile.private_open_orders_path)
    rows.append(
        _row(
            "open_orders",
            supported=bool(oo),
            execution_disabled=not bool(oo),
            reason="ok" if oo else "missing_private_open_orders_path",
            write=False,
        )
    )

    oh = _path(profile.private_order_history_path)
    rows.append(
        _row(
            "order_history",
            supported=bool(oh),
            execution_disabled=not bool(oh),
            reason="ok" if oh else "missing_private_order_history_path",
            write=False,
        )
    )

    fh = _path(profile.private_fill_history_path)
    rows.append(
        _row(
            "fills",
            supported=bool(fh),
            execution_disabled=not bool(fh),
            reason="ok" if fh else "missing_private_fill_history_path",
            write=False,
        )
    )

    po = _path(profile.private_place_order_path)
    rows.append(
        _row(
            "order_create",
            supported=bool(po),
            execution_disabled=not bool(po),
            reason="ok" if po else "missing_private_place_order_path",
            write=True,
        )
    )

    mo = _path(profile.private_modify_order_path)
    rows.append(
        _row(
            "order_replace",
            supported=bool(mo),
            execution_disabled=not bool(mo),
            reason="ok" if mo else "missing_private_modify_order_path",
            write=True,
        )
    )

    co = _path(profile.private_cancel_order_path)
    rows.append(
        _row(
            "order_cancel",
            supported=bool(co),
            execution_disabled=not bool(co),
            reason="ok" if co else "missing_private_cancel_order_path",
            write=True,
        )
    )

    ca = _path(profile.private_cancel_all_orders_path)
    rows.append(
        _row(
            "cancel_all",
            supported=bool(ca),
            execution_disabled=not bool(ca),
            reason="ok" if ca else "missing_private_cancel_all_orders_path",
            write=True,
        )
    )

    ro_ok = bool(po) and bool(profile.supports_reduce_only)
    rows.append(
        _row(
            "reduce_only",
            supported=ro_ok,
            execution_disabled=not ro_ok,
            reason="ok"
            if ro_ok
            else (
                "missing_place_order"
                if not po
                else "family_does_not_support_reduce_only_flag"
            ),
            write=True,
        )
    )

    lev_ok = bool(_path(profile.private_set_leverage_path)) and bool(profile.supports_leverage)
    rows.append(
        _row(
            "leverage_config",
            supported=lev_ok,
            execution_disabled=not lev_ok,
            reason="ok"
            if lev_ok
            else (
                "missing_private_set_leverage_path"
                if not _path(profile.private_set_leverage_path)
                else "family_does_not_support_leverage_api"
            ),
            write=True,
        )
    )

    ws = _path(profile.private_ws_inst_type)
    rows.append(
        _row(
            "private_ws",
            supported=bool(ws),
            execution_disabled=not bool(ws),
            reason="ok" if ws else "missing_private_ws_inst_type",
            write=False,
        )
    )

    rec_ok = bool(oo) and (bool(pos) or bool(acct))
    rec_reason = "ok"
    if not oo:
        rec_reason = "missing_open_orders_for_reconcile"
    elif not pos and not acct:
        rec_reason = "missing_positions_and_account_paths"
    rows.append(
        _row(
            "rest_reconcile_snapshot",
            supported=rec_ok,
            execution_disabled=not rec_ok,
            reason=rec_reason,
            write=False,
        )
    )

    return rows


def _find_row(matrix: list[dict[str, Any]], category: str) -> dict[str, Any] | None:
    for row in matrix:
        if row.get("category") == category:
            return row
    return None


def assert_read_capability(profile: BitgetEndpointProfile, category: ControlCategory) -> None:
    if category in _WRITE_CATEGORIES:
        raise ValueError(f"use assert_write_capability for {category}")
    _assert_capability(profile, category)


def assert_write_capability(profile: BitgetEndpointProfile, category: ControlCategory) -> None:
    if category not in _WRITE_CATEGORIES:
        raise ValueError(f"not a write category: {category}")
    _assert_capability(profile, category)


def _assert_capability(profile: BitgetEndpointProfile, category: str) -> None:
    from live_broker.private_rest import BitgetRestError

    row = _find_row(capability_matrix_for_profile(profile), category)
    if row is None:
        raise BitgetRestError(
            classification="validation",
            message=f"control_plane:unknown_category:{category}",
            retryable=False,
        )
    if row.get("status") == "supported" and not row.get("execution_disabled"):
        return
    reason = str(row.get("reason") or "execution_disabled")
    raise BitgetRestError(
        classification="service_disabled",
        message=f"control_plane:{category}:execution_disabled:{reason}",
        retryable=False,
        payload={"control_plane_matrix_version": CONTROL_PLANE_MATRIX_VERSION, "category": category},
    )
