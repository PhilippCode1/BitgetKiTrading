//! Uniswap-V2-artige Constant-Product-Formel + heuristische Slippage ohne Live-Reserves.

/// `x*y=k`, `amount_out = amount_in * reserve_out / (reserve_in + amount_in)`.
/// Slippage vs Mid-Preis in Basispunkten (1 BPS = 0.01%).
#[inline]
pub fn cpmm_slippage_bps(reserve_in: f64, reserve_out: f64, amount_in: f64) -> f64 {
    if !(reserve_in > 0.0 && reserve_out > 0.0 && amount_in > 0.0) {
        return f64::NAN;
    }
    let mid = reserve_out / reserve_in;
    let amount_out = amount_in * reserve_out / (reserve_in + amount_in);
    let exec = amount_out / amount_in;
    if !(mid > 0.0 && exec.is_finite()) {
        return f64::NAN;
    }
    (1.0 - exec / mid) * 10_000.0
}

/// Wenn keine Pool-Reserves aus dem Mempool bekannt sind: grobe Impact-Schaetzung aus Notional vs. TVL.
#[inline]
pub fn heuristic_slippage_bps(notional_usd: f64, pool_tvl_usd: f64) -> f64 {
    let tvl = pool_tvl_usd.max(1.0);
    let r = (notional_usd / tvl).min(1.0);
    10_000.0 * r * 0.55
}

#[no_mangle]
pub extern "C" fn onchain_impact_cpmm_slippage_bps(
    reserve_in: f64,
    reserve_out: f64,
    amount_in: f64,
) -> f64 {
    cpmm_slippage_bps(reserve_in, reserve_out, amount_in)
}

#[no_mangle]
pub extern "C" fn onchain_impact_heuristic_slippage_bps(notional_usd: f64, pool_tvl_usd: f64) -> f64 {
    heuristic_slippage_bps(notional_usd, pool_tvl_usd)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cpmm_small_trade_low_slip() {
        let bps = cpmm_slippage_bps(1_000_000.0, 1_000_000.0, 1_000.0);
        assert!(bps >= 0.0 && bps < 15.0, "bps={bps}");
    }

    #[test]
    fn heuristic_scales_with_notional() {
        let a = heuristic_slippage_bps(500_000.0, 50_000_000.0);
        let b = heuristic_slippage_bps(1_000_000.0, 50_000_000.0);
        assert!(b > a);
    }
}
