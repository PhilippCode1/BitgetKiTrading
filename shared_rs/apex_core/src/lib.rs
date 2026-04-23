//! Native Python-Erweiterung **`apex_core`** (PyO3 + Maturin).
//!
//! Tick-/OHLC-Pfade nutzen `numpy::PyReadonlyArray1<f64>` → **Zero-Copy** aus Python-Sicht,
//! solange die Arrays **C-contiguous float64** sind (siehe `shared_py.rust_core_bridge.assert_float64_c_contiguous`).
//!
//! # Lokale Entwicklung
//!
//! Voraussetzungen: **Rust (stable)** und **Python 3.11+**, dazu **Maturin** im aktiven venv.
//!
//! ```text
//! pip install "maturin>=1.7,<2"
//! cd shared_rs/apex_core
//! maturin develop --release
//! ```
//!
//! `maturin develop` baut die Extension und installiert sie in die aktuelle Umgebung, sodass
//! `import apex_core` sowie `apex_core.check_core_latency()` nativ funktionieren.
//!
//! Alternativ (Wheel bauen und installieren — Workspace-`target` unter ``shared_rs/target``):
//!
//! ```text
//! maturin build --release --interpreter python
//! pip install ../target/wheels/apex_core-*.whl
//! ```

use ndarray::Array1;
use ndarray::Ix1;
use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList, PyTuple};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

/// VPIN-/Orderflow-Toxizität (volumensynchronisierte Buckets).
#[pyclass(name = "VpinEngine")]
struct VpinEngine {
    inner: Mutex<indicators::VpinAccumulator>,
}

#[pymethods]
impl VpinEngine {
    #[new]
    #[pyo3(signature = (bucket_volume, window_buckets))]
    fn new(bucket_volume: f64, window_buckets: usize) -> Self {
        Self {
            inner: Mutex::new(indicators::VpinAccumulator::new(
                bucket_volume,
                window_buckets,
            )),
        }
    }

    fn set_mid_from_bid_ask(&self, bid: f64, ask: f64) {
        let mut g = self.inner.lock().expect("vpin mutex poisoned");
        g.set_mid_from_bid_ask(bid, ask);
    }

    fn set_mid(&self, mid: f64) {
        let mut g = self.inner.lock().expect("vpin mutex poisoned");
        g.set_mid(mid);
    }

    fn clear_mid(&self) {
        let mut g = self.inner.lock().expect("vpin mutex poisoned");
        g.clear_mid();
    }

    #[pyo3(signature = (price, volume, taker_is_buy=None))]
    fn push_trade(&self, price: f64, volume: f64, taker_is_buy: Option<bool>) {
        let mut g = self.inner.lock().expect("vpin mutex poisoned");
        g.push_trade(price, volume, taker_is_buy);
    }

    fn toxicity_score(&self) -> f64 {
        let g = self.inner.lock().expect("vpin mutex poisoned");
        g.toxicity_score()
    }

    fn completed_bucket_count(&self) -> usize {
        let g = self.inner.lock().expect("vpin mutex poisoned");
        g.completed_bucket_count()
    }
}

fn as_ix1<'a>(name: &str, arr: &'a PyReadonlyArray1<f64>) -> PyResult<ndarray::ArrayView1<'a, f64>> {
    arr.as_array()
        .into_dimensionality::<Ix1>()
        .map_err(|e| PyValueError::new_err(format!("{name}: erwartet 1D float64 ndarray ({e})")))
}

/// Liefert einen **UTC-Wanduhr-Zeitstempel in Nanosekunden** seit UNIX_EPOCH.
#[pyfunction]
fn check_core_latency() -> PyResult<u128> {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("SystemTime-Fehler: {e}")))?
        .as_nanos();
    Ok(nanos)
}

/// ATR (SMA der True Range, identisch `feature_engine.features.atr.atr_sma`).
///
/// Erwartet **C-contiguous** `float64` Arrays gleicher Länge (OHLC pro Bar).
#[pyfunction]
#[pyo3(signature = (opens, highs, lows, closes, window))]
fn compute_atr_sma(
    opens: PyReadonlyArray1<f64>,
    highs: PyReadonlyArray1<f64>,
    lows: PyReadonlyArray1<f64>,
    closes: PyReadonlyArray1<f64>,
    window: usize,
) -> PyResult<f64> {
    let o = as_ix1("opens", &opens)?;
    let h = as_ix1("highs", &highs)?;
    let l = as_ix1("lows", &lows)?;
    let c = as_ix1("closes", &closes)?;
    let n = o.len();
    if n != h.len() || n != l.len() || n != c.len() {
        return Err(PyValueError::new_err(format!(
            "opens/highs/lows/closes Längen stimmen nicht überein: {} {} {} {}",
            o.len(),
            h.len(),
            l.len(),
            c.len()
        )));
    }
    Ok(indicators::atr_sma(o, h, l, c, window))
}

/// RSI (SMA-Variante wie `feature_engine.features.rsi.rsi_sma`).
#[pyfunction]
#[pyo3(signature = (closes, window))]
fn compute_rsi_sma(closes: PyReadonlyArray1<f64>, window: usize) -> PyResult<f64> {
    let v = as_ix1("closes", &closes)?;
    Ok(indicators::rsi_sma(v, window))
}

/// Letzter EMA-Wert über die gesamte Serie (`feature_engine.features.momentum.ema`).
#[pyfunction]
#[pyo3(signature = (values, span))]
fn compute_ema_last(values: PyReadonlyArray1<f64>, span: usize) -> PyResult<f64> {
    let v = as_ix1("values", &values)?;
    Ok(indicators::ema_last(v, span))
}

/// EMA-Zeitreihe (`feature_engine.features.momentum._ema_series`).
#[pyfunction]
#[pyo3(signature = (values, span))]
fn compute_ema_series<'py>(
    py: Python<'py>,
    values: PyReadonlyArray1<f64>,
    span: usize,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let v = as_ix1("values", &values)?;
    let out = indicators::ema_series(v, span);
    Ok(out.into_pyarray(py))
}

/// Trend-Snapshot (`feature_engine.features.momentum.trend_snapshot`).
#[pyfunction]
#[pyo3(signature = (closes, fast_window=12, slow_window=26, slope_lookback=3))]
fn compute_trend_snapshot(
    closes: PyReadonlyArray1<f64>,
    fast_window: usize,
    slow_window: usize,
    slope_lookback: usize,
) -> PyResult<(f64, f64, f64, i32)> {
    let v = as_ix1("closes", &closes)?;
    Ok(indicators::trend_snapshot(
        v,
        fast_window,
        slow_window,
        slope_lookback,
    ))
}

/// `C^{-1} * impulse` mit Korrelationsmatrix `C` (Zeilen-major, symmetrisch erwartet).
/// Bei Singularitaet: Nullvektor gleicher Laenge.
#[pyfunction]
#[pyo3(signature = (corr, n, impulse))]
fn compute_corr_inv_impulse<'py>(
    py: Python<'py>,
    corr: PyReadonlyArray1<f64>,
    n: usize,
    impulse: PyReadonlyArray1<f64>,
) -> PyResult<Bound<'py, PyArray1<f64>>> {
    let c = corr.as_slice()?;
    let x = impulse.as_slice()?;
    if c.len() != n * n {
        return Err(PyValueError::new_err(format!(
            "corr len {} != n*n {}",
            c.len(),
            n * n
        )));
    }
    if x.len() != n {
        return Err(PyValueError::new_err(format!(
            "impulse len {} != n {}",
            x.len(),
            n
        )));
    }
    let y = indicators::volatility_spillover_inv_impulse(c, n, x).unwrap_or_else(|| vec![0.0_f64; n]);
    Ok(Array1::from_vec(y).into_pyarray(py))
}

fn parse_level_pairs(obj: &Bound<'_, PyAny>) -> PyResult<Vec<(f64, f64)>> {
    let list = obj.downcast::<PyList>()?;
    let mut v = Vec::with_capacity(list.len());
    for item in list.iter() {
        let tup = item.downcast::<PyTuple>()?;
        if tup.len() != 2 {
            return Err(PyValueError::new_err("orderbook level tuple muss Laenge 2 haben"));
        }
        let p: f64 = tup.get_item(0)?.extract()?;
        let s: f64 = tup.get_item(1)?.extract()?;
        v.push((p, s));
    }
    Ok(v)
}

fn orderbook_py_err(e: orderbook::OrderBookError) -> PyErr {
    match e {
        orderbook::OrderBookError::ChecksumMismatch { expected, actual } => PyValueError::new_err(
            format!("OrderbookInconsistency: checksum expected={expected} actual={actual}"),
        ),
        orderbook::OrderBookError::SeqRegression { prev, cur } => PyValueError::new_err(format!(
            "OrderbookInconsistency: seq regression prev={prev} cur={cur}"
        )),
    }
}

/// CRC32 (zlib-kompatibel, signed int32) fuer rohen Checksum-String wie `market_stream.orderbook.checksum`.
#[pyfunction]
fn orderbook_crc32_signed(checksum_utf8: &str) -> i32 {
    orderbook::crc32_signed_zlib(checksum_utf8.as_bytes())
}

/// Apex L2/L3 Orderbuch (Rust); Bids/Asks als `BTreeMap<OrderedFloat<f64>, f64>` (Bids: Key = -Preis).
#[pyclass(name = "ApexOrderBook")]
struct ApexOrderBook {
    inner: Mutex<orderbook::OrderBook>,
}

#[pymethods]
impl ApexOrderBook {
    #[new]
    #[pyo3(signature = (max_levels=50, checksum_levels=25))]
    fn new(max_levels: usize, checksum_levels: usize) -> Self {
        Self {
            inner: Mutex::new(orderbook::OrderBook::new(max_levels, checksum_levels)),
        }
    }

    fn reset(&self) {
        let mut g = self.inner.lock().expect("orderbook mutex poisoned");
        g.reset();
    }

    fn set_ingest_ts_ns(&self, ns: u64) {
        let g = self.inner.lock().expect("orderbook mutex poisoned");
        g.set_ingest_now_ns(ns);
    }

    #[pyo3(signature = (side, price, size))]
    fn update(&self, side: u8, price: f64, size: f64) -> PyResult<()> {
        let mut g = self.inner.lock().expect("orderbook mutex poisoned");
        g.update(side, price, size).map_err(orderbook_py_err)
    }

    #[pyo3(signature = (bids, asks, seq=None, checksum=None, ingest_ts_ns=None))]
    fn apply_snapshot_levels(
        &self,
        bids: &Bound<'_, PyAny>,
        asks: &Bound<'_, PyAny>,
        seq: Option<i64>,
        checksum: Option<i32>,
        ingest_ts_ns: Option<u64>,
    ) -> PyResult<()> {
        let bl = parse_level_pairs(bids)?;
        let al = parse_level_pairs(asks)?;
        let mut g = self.inner.lock().expect("orderbook mutex poisoned");
        g.apply_snapshot_levels(&bl, &al, seq, checksum, ingest_ts_ns)
            .map_err(orderbook_py_err)
    }

    #[pyo3(signature = (bids, asks, seq=None, checksum=None, ingest_ts_ns=None, require_seq_increase=false))]
    fn apply_update_levels(
        &self,
        bids: &Bound<'_, PyAny>,
        asks: &Bound<'_, PyAny>,
        seq: Option<i64>,
        checksum: Option<i32>,
        ingest_ts_ns: Option<u64>,
        require_seq_increase: bool,
    ) -> PyResult<()> {
        let bl = parse_level_pairs(bids)?;
        let al = parse_level_pairs(asks)?;
        let mut g = self.inner.lock().expect("orderbook mutex poisoned");
        g.apply_update_levels(
            &bl,
            &al,
            seq,
            checksum,
            ingest_ts_ns,
            require_seq_increase,
        )
        .map_err(orderbook_py_err)
    }

    fn current_checksum(&self) -> i32 {
        let g = self.inner.lock().expect("orderbook mutex poisoned");
        g.current_checksum()
    }

    fn snapshot_dict<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let g = self.inner.lock().expect("orderbook mutex poisoned");
        let d = PyDict::new_bound(py);
        let (bd25, ad25) = g.depth_snapshot(25);
        let list_b = PyList::empty_bound(py);
        for (p, s) in &bd25 {
            list_b.append(PyTuple::new_bound(py, [*p, *s]))?;
        }
        let list_a = PyList::empty_bound(py);
        for (p, s) in &ad25 {
            list_a.append(PyTuple::new_bound(py, [*p, *s]))?;
        }
        d.set_item("bids_top25", list_b)?;
        d.set_item("asks_top25", list_a)?;
        d.set_item("best_bid", g.best_bid().unwrap_or(f64::NAN))?;
        d.set_item("best_ask", g.best_ask().unwrap_or(f64::NAN))?;
        d.set_item("spread_bps", g.spread_bps().unwrap_or(f64::NAN))?;
        if let Some(x) = g.orderflow_imbalance(5) {
            d.set_item("orderflow_imbalance_5", x)?;
        } else {
            d.set_item("orderflow_imbalance_5", py.None())?;
        }
        if let Some(x) = g.orderflow_imbalance(10) {
            d.set_item("orderflow_imbalance_10", x)?;
        } else {
            d.set_item("orderflow_imbalance_10", py.None())?;
        }
        if let Some(x) = g.orderflow_imbalance(20) {
            d.set_item("orderflow_imbalance_20", x)?;
        } else {
            d.set_item("orderflow_imbalance_20", py.None())?;
        }
        d.set_item("spread_variance_100", g.spread_variance_last_100())?;
        d.set_item(
            "latency_process_minus_ingest_ns",
            g.latency_process_minus_ingest_ns(),
        )?;
        Ok(d)
    }
}

#[pymodule]
fn apex_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(check_core_latency, m)?)?;
    m.add_function(wrap_pyfunction!(compute_atr_sma, m)?)?;
    m.add_function(wrap_pyfunction!(compute_rsi_sma, m)?)?;
    m.add_function(wrap_pyfunction!(compute_ema_last, m)?)?;
    m.add_function(wrap_pyfunction!(compute_ema_series, m)?)?;
    m.add_function(wrap_pyfunction!(compute_trend_snapshot, m)?)?;
    m.add_function(wrap_pyfunction!(compute_corr_inv_impulse, m)?)?;
    m.add_function(wrap_pyfunction!(orderbook_crc32_signed, m)?)?;
    m.add_class::<ApexOrderBook>()?;
    m.add_class::<VpinEngine>()?;
    Ok(())
}
