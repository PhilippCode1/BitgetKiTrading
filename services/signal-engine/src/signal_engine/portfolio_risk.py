"""
Portfolio- / Kontext-Risiko fuer **Live-Execution** (optional, snapshot-getrieben).

Paper und Shadow duerfen bei reiner Konto-/Portfolio-Ueberlastung weiterlernen, solange
`RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY=true` und keine universalen Hard-Blocks greifen.

Keine Fantasiewerte: alle Schwellen greifen nur, wenn die jeweiligen Felder im Snapshot gesetzt sind.
"""

from __future__ import annotations

from typing import Any

PORTFOLIO_RISK_POLICY_VERSION = "portfolio-risk-v2"


def _f(x: Any) -> float | None:
    if x in (None, ""):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _i(x: Any) -> int | None:
    if x in (None, ""):
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def extract_portfolio_risk(acct: dict[str, Any]) -> dict[str, Any]:
    """Liest verschachteltes portfolio_risk_json aus risk_account_snapshot."""
    pr = acct.get("portfolio_risk_json")
    return dict(pr) if isinstance(pr, dict) else {}


def calculate_bot_grid_exposure(
    *,
    lower_bound: float,
    upper_bound: float,
    grid_count: int,
    notional_size: float,
) -> float:
    """
    Berechnet das maximale kumulierte Risiko (Maximum Drawdown Exposure) aller Gitterlinien
    eines Grid-Bots, falls der Markt die gesamte Range nach unten durchbricht.
    Ein klassisches Direktionalhandel-Notional-Exposure schuetzt sich ueber einen Single-Stop,
    waehrend Grid-Bots Kapital ueber die gesamte Range blockieren.
    """
    if grid_count <= 1 or upper_bound <= lower_bound or notional_size <= 0:
        return notional_size * 0.1  # Fallback: 10% des Notional-Volumens als Exposure

    # Berechne die Abstaende und die Groesse pro Grid-Linie
    interval = (upper_bound - lower_bound) / (grid_count - 1)
    size_per_grid = notional_size / grid_count

    total_exposure = 0.0
    for i in range(grid_count):
        entry_price = lower_bound + i * interval
        # Verlust pro Linie, wenn der Kurs bis auf das untere Limit (lower_bound) faellt
        loss = max(0.0, entry_price - lower_bound)
        # Exposure-Beitrag dieser Linie (Verlust relativ zum Einstiegspreis mal die anteilige Positionsgroesse)
        total_exposure += (loss / entry_price) * size_per_grid

    return total_exposure


def build_portfolio_synthesis(
    *,
    acct: dict[str, Any],
    pr: dict[str, Any],
    signal_row: dict[str, Any],
    portfolio_live_reasons: list[str],
    account_stress_live_reasons: list[str],
) -> dict[str, Any]:
    mf = (
        str(signal_row.get("market_family") or pr.get("symbol_family") or "")
        .strip()
        .lower()
    )
    dd_kill = [
        str(x)
        for x in account_stress_live_reasons
        if isinstance(x, str)
        and ("drawdown" in x.lower() or "loss" in x.lower() or "dd_" in x.lower())
    ]
    return {
        "version": PORTFOLIO_RISK_POLICY_VERSION,
        "market_family_context": mf or None,
        "account_stress_live_reasons_json": list(account_stress_live_reasons),
        "portfolio_structural_live_reasons_json": list(portfolio_live_reasons),
        "drawdown_kill_switch_triggers_json": dd_kill,
        "echo_margin_utilization_0_1": acct.get("margin_utilization_0_1"),
        "echo_gross_exposure_ratio_0_1": acct.get("gross_exposure_ratio_0_1"),
        "echo_open_positions_count": acct.get("open_positions_count"),
        "echo_portfolio_correlation_stress_0_1": acct.get(
            "portfolio_correlation_stress_0_1"
        ),
        "portfolio_risk_json_keys": sorted(pr.keys()) if pr else [],
        "policy_note_de": (
            "Universal-Hard-Blocks (z. B. uncertainty blocked, exchange_health_ok=false) gelten "
            "signalweit. Konto-Stress und Portfolio-Felder blockieren nur Echtgeld-Pfade, wenn "
            "RISK_GOVERNOR_ACCOUNT_STRESS_LIVE_ONLY=true."
        ),
    }


def assess_portfolio_structural_live_blocks(
    *,
    settings: Any,
    acct: dict[str, Any],
    signal_row: dict[str, Any],
) -> list[str]:
    """
    Reine Portfolio-/Venue-Struktur ohne klassische Kontokennzahlen (die bleiben im Governor).
    """
    reasons: list[str] = []
    pr = extract_portfolio_risk(acct)
    mf = (
        str(signal_row.get("market_family") or pr.get("symbol_family") or "")
        .strip()
        .lower()
    )

    mode = (
        str(
            pr.get("venue_operational_mode") or acct.get("venue_operational_mode") or ""
        )
        .strip()
        .lower()
    )
    if bool(getattr(settings, "risk_portfolio_live_block_venue_degraded", True)):
        if mode == "degraded":
            reasons.append("portfolio_live_venue_degraded")

    # --- Aggregations-Limit für Gitter-Bots (Echtzeit-Risikosteuerung) ---
    exec_mode = signal_row.get("execution_mode") or "STANDARD_FUTURES"
    active_grid_margin_sum = _f(pr.get("active_grid_bots_margin_sum")) or _f(acct.get("active_grid_bots_margin_sum")) or 0.0
    heat_threshold = _f(getattr(settings, "leverage_account_heat_margin_soft_threshold_0_1", 0.50)) or 0.50

    new_bot_margin = 0.0
    if exec_mode == "BOT_GRID":
        bp = signal_row.get("bot_params")
        if isinstance(bp, dict):
            # Berechne kumulierte Grid-Exposure
            notional = _f(signal_row.get("notional_size")) or _f(acct.get("equity")) or 1000.0
            grid_exposure = calculate_bot_grid_exposure(
                lower_bound=float(bp.get("lower_bound", 0.0)),
                upper_bound=float(bp.get("upper_bound", 0.0)),
                grid_count=int(bp.get("grid_count", 20)),
                notional_size=notional,
            )
            # Schaetze benoetigte Margin unter Beruecksichtigung des Hebel-Caps
            leverage = _f(signal_row.get("allowed_leverage")) or 22.0
            new_bot_margin = grid_exposure / max(leverage, 1.0)

    # Wenn die Summe der blockierten Margins der Grid-Bots das Limit ueberschreitet, Trade blockieren
    if (active_grid_margin_sum + new_bot_margin) > heat_threshold:
        reasons.append("portfolio_live_grid_aggregate_margin_heat_exceeded")

    fam_map = pr.get("family_exposure_fraction_0_1")
    lim_f = float(
        getattr(settings, "risk_portfolio_live_max_family_exposure_0_1", 0.58)
    )
    if isinstance(fam_map, dict) and mf:
        v = _f(fam_map.get(mf))
        if v is not None and v > lim_f:
            reasons.append("portfolio_live_family_exposure_exceeded")

    dne = _f(pr.get("direction_net_exposure_0_1"))
    lim_d = float(
        getattr(settings, "risk_portfolio_live_max_direction_net_exposure_0_1", 0.72)
    )
    if dne is not None and dne > lim_d:
        reasons.append("portfolio_live_direction_concentration_exceeded")

    cex = _f(pr.get("correlated_cluster_largest_exposure_0_1"))
    lim_c = float(
        getattr(settings, "risk_portfolio_live_max_cluster_exposure_0_1", 0.48)
    )
    if cex is not None and cex > lim_c:
        reasons.append("portfolio_live_correlated_cluster_exceeded")

    fd = _f(pr.get("funding_drag_bps_next_8h"))
    lim_fd = float(getattr(settings, "risk_portfolio_live_max_funding_drag_bps", 95.0))
    if fd is not None and fd > lim_fd:
        reasons.append("portfolio_live_funding_drag_exceeded")

    bs = _f(pr.get("basis_stress_0_1"))
    lim_bs = float(getattr(settings, "risk_portfolio_live_max_basis_stress_0_1", 0.62))
    if bs is not None and bs > lim_bs:
        reasons.append("portfolio_live_basis_stress_exceeded")

    sc = _f(pr.get("session_event_concentration_0_1"))
    lim_sc = float(
        getattr(settings, "risk_portfolio_live_max_session_concentration_0_1", 0.88)
    )
    if sc is not None and sc > lim_sc:
        reasons.append("portfolio_live_session_event_concentration_exceeded")

    oo = _f(pr.get("open_orders_notional_to_equity_0_1"))
    lim_oo = float(
        getattr(
            settings, "risk_portfolio_live_max_open_orders_notional_ratio_0_1", 0.42
        )
    )
    if oo is not None and oo > lim_oo:
        reasons.append("portfolio_live_open_orders_stress")

    pm = _i(pr.get("pending_mirror_trades_count"))
    lim_pm = int(getattr(settings, "risk_portfolio_live_max_pending_mirror_trades", 4))
    if pm is not None and pm > lim_pm:
        reasons.append("portfolio_live_pending_mirror_trades_exceeded")

    return reasons
