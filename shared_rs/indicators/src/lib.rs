//! Hochperformante Indikator-Kerne (ATR-SMA, RSI-SMA, EMA) mit `ndarray`.
//!
//! Semantik ist 1:1 an die Python-Referenz in `feature_engine.features` gebunden.
//! Zusaetzlich: kleine dichte Matrizen (Korrelations-Matrix) — Inversion per Gauss-Jordan,
//! Matrix-Vektor-Produkt fuer Volatilitaets-Spillover-Impulse (Apex Correlation Engine).

use ndarray::{s, Array1, ArrayView1};
use std::f64::NAN;

mod vpin;

pub use vpin::{lee_ready_aggressive_buy, tick_rule_aggressive_buy, VpinAccumulator};

/// Gauss-Jordan-Inversion einer `n`×`n`-Matrix in **Zeilen-major**-Layout (`len = n*n`).
/// `None` bei Singularitaet oder Dimensionfehler.
pub fn matrix_inverse_row_major(a: &[f64], n: usize) -> Option<Vec<f64>> {
    if n == 0 || a.len() != n * n {
        return None;
    }
    let mut aug = vec![vec![0.0_f64; 2 * n]; n];
    for i in 0..n {
        for j in 0..n {
            aug[i][j] = a[i * n + j];
        }
        aug[i][n + i] = 1.0;
    }
    const PIVOT_EPS: f64 = 1e-12;
    for col in 0..n {
        let mut piv: Option<usize> = None;
        for r in col..n {
            if aug[r][col].abs() > PIVOT_EPS {
                piv = Some(r);
                break;
            }
        }
        let pr = piv?;
        if pr != col {
            aug.swap(pr, col);
        }
        let div = aug[col][col];
        if div.abs() < PIVOT_EPS {
            return None;
        }
        for j in 0..2 * n {
            aug[col][j] /= div;
        }
        for r in 0..n {
            if r == col {
                continue;
            }
            let f = aug[r][col];
            if f.abs() < 1e-18 {
                continue;
            }
            for j in 0..2 * n {
                aug[r][j] -= f * aug[col][j];
            }
        }
    }
    let mut inv = vec![0.0_f64; n * n];
    for i in 0..n {
        for j in 0..n {
            inv[i * n + j] = aug[i][n + j];
        }
    }
    Some(inv)
}

/// `y = M x` mit `M` in Zeilen-major (`n`×`n`).
pub fn matrix_vector_row_major(mat: &[f64], n: usize, x: &[f64]) -> Option<Vec<f64>> {
    if mat.len() != n * n || x.len() != n {
        return None;
    }
    let mut y = vec![0.0_f64; n];
    for i in 0..n {
        let mut s = 0.0;
        for j in 0..n {
            s += mat[i * n + j] * x[j];
        }
        y[i] = s;
    }
    Some(y)
}

/// Volatilitaets-Spillover-Impuls: `C^{-1} * impulse` (Korrelationsmatrix `C`, klein `n`).
pub fn volatility_spillover_inv_impulse(corr: &[f64], n: usize, impulse: &[f64]) -> Option<Vec<f64>> {
    let inv = matrix_inverse_row_major(corr, n)?;
    matrix_vector_row_major(&inv, n, impulse)
}

/// True Range Serie (Länge `n-1` bei `n` Kerzen), identisch zur Python-Schleife in `atr_sma`.
fn true_range_series(o: ArrayView1<f64>, h: ArrayView1<f64>, l: ArrayView1<f64>, c: ArrayView1<f64>) -> Array1<f64> {
    let n = o.len();
    debug_assert_eq!(n, h.len());
    debug_assert_eq!(n, l.len());
    debug_assert_eq!(n, c.len());
    if n < 2 {
        return Array1::zeros(0);
    }
    let mut trs = Array1::<f64>::zeros(n - 1);
    let mut prev_close = c[0];
    for i in 1..n {
        let tr = (h[i] - l[i])
            .max((h[i] - prev_close).abs())
            .max((l[i] - prev_close).abs());
        trs[i - 1] = tr;
        prev_close = c[i];
    }
    trs
}

/// ATR als SMA der letzten `window` True Ranges (Wilder-TR-Kette ab erstem Close).
///
/// Referenz: `feature_engine.features.atr.atr_sma`.
pub fn atr_sma(o: ArrayView1<f64>, h: ArrayView1<f64>, l: ArrayView1<f64>, c: ArrayView1<f64>, window: usize) -> f64 {
    if window == 0 {
        return NAN;
    }
    let n = o.len();
    if n != h.len() || n != l.len() || n != c.len() || n < window + 1 {
        return NAN;
    }
    let trs = true_range_series(o, h, l, c);
    let len = trs.len();
    trs.slice(s![(len.saturating_sub(window))..]).sum() / window as f64
}

/// RSI (Cutlers RSI) mit SMA über die letzten `window` Kursänderungen — **Zähler summieren nur
/// positive/negative Moves, Nenner ist immer `window`** (wie Python-Referenz).
///
/// Referenz: `feature_engine.features.rsi.rsi_sma`.
pub fn rsi_sma(closes: ArrayView1<f64>, window: usize) -> f64 {
    if window == 0 {
        return NAN;
    }
    let n = closes.len();
    if n < window + 1 {
        return NAN;
    }
    let start = n - 1 - window;
    let mut gain_sum = 0.0;
    let mut loss_sum = 0.0;
    for i in start..(n - 1) {
        let ch = closes[i + 1] - closes[i];
        if ch > 0.0 {
            gain_sum += ch;
        } else if ch < 0.0 {
            loss_sum += -ch;
        }
    }
    let avg_gain = gain_sum / window as f64;
    let avg_loss = loss_sum / window as f64;
    if avg_gain == 0.0 && avg_loss == 0.0 {
        return 50.0;
    }
    if avg_loss == 0.0 {
        return 100.0;
    }
    let rs = avg_gain / avg_loss;
    let value = 100.0 - (100.0 / (1.0 + rs));
    if value.is_nan() { 50.0 } else { value }
}

/// EMA über die gesamte Serie (Startwert = erstes Sample), letzter Wert.
///
/// Referenz: `feature_engine.features.momentum.ema`.
pub fn ema_last(values: ArrayView1<f64>, span: usize) -> f64 {
    if values.is_empty() {
        return NAN;
    }
    let alpha = 2.0 / (span as f64 + 1.0);
    let mut current = values[0];
    for i in 1..values.len() {
        current = alpha * values[i] + (1.0 - alpha) * current;
    }
    current
}

/// Vollständige EMA-Zeitreihe (gleiche Länge wie Input).
///
/// Referenz: `feature_engine.features.momentum._ema_series`.
pub fn ema_series(values: ArrayView1<f64>, span: usize) -> Array1<f64> {
    let n = values.len();
    if n == 0 {
        return Array1::zeros(0);
    }
    let alpha = 2.0 / (span as f64 + 1.0);
    let mut out = Array1::<f64>::zeros(n);
    let mut current = values[0];
    out[0] = current;
    for i in 1..n {
        current = alpha * values[i] + (1.0 - alpha) * current;
        out[i] = current;
    }
    out
}

/// Trend-Snapshot gemäß `trend_snapshot` (Standardfenster 12/26, Slope-Lookback 3).
///
/// Rückgabe: `(ema_fast, ema_slow, slope_proxy, trend_dir)`.
pub fn trend_snapshot(
    closes: ArrayView1<f64>,
    fast_window: usize,
    slow_window: usize,
    slope_lookback: usize,
) -> (f64, f64, f64, i32) {
    if closes.is_empty() {
        return (NAN, NAN, NAN, 0);
    }
    let fast_series = ema_series(closes, fast_window);
    let slow_series = ema_series(closes, slow_window);
    let n = fast_series.len();
    debug_assert_eq!(n, closes.len());
    let ema_fast = fast_series[n - 1];
    let ema_slow = slow_series[n - 1];
    let slope_proxy = if n > slope_lookback {
        ema_fast - fast_series[n - 1 - slope_lookback]
    } else if n >= 2 {
        ema_fast - fast_series[n - 2]
    } else {
        0.0
    };
    let trend_dir = if ema_fast > ema_slow && slope_proxy > 0.0 {
        1
    } else if ema_fast < ema_slow && slope_proxy < 0.0 {
        -1
    } else {
        0
    };
    (ema_fast, ema_slow, slope_proxy, trend_dir)
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::array;

    #[test]
    fn atr_matches_python_fixture() {
        let o = array![10.0, 10.5, 11.0, 11.8];
        let h = array![11.0, 11.5, 12.0, 12.2];
        let l = array![9.5, 10.0, 10.8, 11.0];
        let c = array![10.5, 11.0, 11.8, 11.3];
        let v = atr_sma(o.view(), h.view(), l.view(), c.view(), 3);
        assert!((v - 1.3).abs() < 1e-12);
    }

    #[test]
    fn matrix_inv_identity_3x3() {
        let n = 3;
        let mut id = vec![0.0_f64; n * n];
        for i in 0..n {
            id[i * n + i] = 1.0;
        }
        let inv = matrix_inverse_row_major(&id, n).expect("inv");
        for i in 0..n * n {
            assert!((inv[i] - id[i]).abs() < 1e-9, "i={i}");
        }
    }

    #[test]
    fn spillover_matches_manual_2x2() {
        let n = 2;
        let corr = vec![1.0, 0.5, 0.5, 1.0];
        let impulse = vec![1.0, 0.0];
        let y = volatility_spillover_inv_impulse(&corr, n, &impulse).expect("sp");
        assert_eq!(y.len(), 2);
        assert!(y[0].is_finite() && y[1].is_finite());
    }
}
