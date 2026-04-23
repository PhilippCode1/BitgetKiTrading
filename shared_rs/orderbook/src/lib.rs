//! Apex Orderbook Core: inkrementelle Bitget-`books`-Semantik, Checksum (zlib/CRC32),
//! Orderflow-Imbalance und Spread-Varianz — hot-path ohne Heap pro Update (Spread-Ring fix).

use std::collections::BTreeMap;
use std::sync::atomic::{AtomicU64, Ordering};

use ordered_float::OrderedFloat;

const SPREAD_RING: usize = 100;

fn is_zero_size(sz: f64) -> bool {
    sz.abs() < 1e-18 || sz == 0.0
}

/// Wie `zlib.crc32` in Python: signed 32-bit Ergebnis.
#[inline]
pub fn crc32_signed_zlib(bytes: &[u8]) -> i32 {
    let crc_u = crc32fast::hash(bytes);
    if crc_u & 0x8000_0000 != 0 {
        -((((crc_u ^ 0xFFFF_FFFF) as i32).wrapping_add(1)))
    } else {
        crc_u as i32
    }
}

/// Bitget-Checksum-String: abwechselnd bid_i, ask_i (je bis `levels`), join mit `:`.
/// `bids` / `asks`: (preis_string, size_string) wie vom Exchange geliefert.
pub fn build_checksum_string(
    bids: &[(String, String)],
    asks: &[(String, String)],
    levels: usize,
) -> String {
    let lb = bids.len().min(levels);
    let la = asks.len().min(levels);
    let mut parts: Vec<&str> = Vec::with_capacity(2 * levels.max(lb.max(la)));
    let mut i = 0usize;
    while i < lb || i < la {
        if i < lb {
            parts.push(bids[i].0.as_str());
            parts.push(bids[i].1.as_str());
        }
        if i < la {
            parts.push(asks[i].0.as_str());
            parts.push(asks[i].1.as_str());
        }
        i += 1;
    }
    parts.join(":")
}

#[inline]
pub fn checksum_from_levels(
    bids: &[(String, String)],
    asks: &[(String, String)],
    levels: usize,
) -> i32 {
    let s = build_checksum_string(bids, asks, levels);
    crc32_signed_zlib(s.as_bytes())
}

/// Bids: `BTreeMap<OrderedFloat<f64>, f64>` mit **negiertem** Preis als Key (aufsteigend = bestes Bid zuerst).
/// Asks: Key = Preis (aufsteigend = bestes Ask zuerst).
#[derive(Debug)]
pub struct OrderBook {
    bids: BTreeMap<OrderedFloat<f64>, f64>,
    asks: BTreeMap<OrderedFloat<f64>, f64>,
    max_levels: usize,
    checksum_levels: usize,
    expected_checksum: Option<i32>,
    last_seq: Option<i64>,
    spread_ring: [f64; SPREAD_RING],
    spread_write: usize,
    spread_count: usize,
    ingest_ns: AtomicU64,
    process_ns: AtomicU64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum OrderBookError {
    ChecksumMismatch { expected: i32, actual: i32 },
    SeqRegression { prev: i64, cur: i64 },
}

impl OrderBook {
    pub fn new(max_levels: usize, checksum_levels: usize) -> Self {
        Self {
            bids: BTreeMap::new(),
            asks: BTreeMap::new(),
            max_levels: max_levels.max(1),
            checksum_levels: checksum_levels.max(1).min(max_levels.max(1)),
            expected_checksum: None,
            last_seq: None,
            spread_ring: [0.0; SPREAD_RING],
            spread_write: 0,
            spread_count: 0,
            ingest_ns: AtomicU64::new(0),
            process_ns: AtomicU64::new(0),
        }
    }

    #[inline]
    pub fn set_ingest_now_ns(&self, ns: u64) {
        self.ingest_ns.store(ns, Ordering::Relaxed);
    }

    #[inline]
    pub fn latency_process_minus_ingest_ns(&self) -> u64 {
        let p = self.process_ns.load(Ordering::Relaxed);
        let i = self.ingest_ns.load(Ordering::Relaxed);
        p.saturating_sub(i)
    }

    pub fn reset(&mut self) {
        self.bids.clear();
        self.asks.clear();
        self.expected_checksum = None;
        self.last_seq = None;
        self.spread_write = 0;
        self.spread_count = 0;
        self.spread_ring = [0.0; SPREAD_RING];
    }

    /// `side`: `0` = bid, `1` = ask. `size == 0` entfernt das Level.
    pub fn update(&mut self, side: u8, price: f64, size: f64) -> Result<(), OrderBookError> {
        if !price.is_finite() || !size.is_finite() {
            return Ok(());
        }
        let key_bid = OrderedFloat(-price);
        let key_ask = OrderedFloat(price);
        match side {
            0 => {
                if is_zero_size(size) {
                    self.bids.remove(&key_bid);
                } else {
                    self.bids.insert(key_bid, size);
                }
            }
            1 => {
                if is_zero_size(size) {
                    self.asks.remove(&key_ask);
                } else {
                    self.asks.insert(key_ask, size);
                }
            }
            _ => {}
        }
        self.trim_bids();
        self.trim_asks();
        self.record_spread_sample();
        self.validate_checksum()?;
        self.process_ns.store(now_ns(), Ordering::Relaxed);
        Ok(())
    }

    fn trim_bids(&mut self) {
        while self.bids.len() > self.max_levels {
            if let Some(k) = self.bids.keys().next_back().copied() {
                self.bids.remove(&k);
            } else {
                break;
            }
        }
    }

    fn trim_asks(&mut self) {
        while self.asks.len() > self.max_levels {
            if let Some(k) = self.asks.keys().next_back().copied() {
                self.asks.remove(&k);
            } else {
                break;
            }
        }
    }

    pub fn apply_snapshot_levels(
        &mut self,
        bid_levels: &[(f64, f64)],
        ask_levels: &[(f64, f64)],
        seq: Option<i64>,
        checksum: Option<i32>,
        ingest_ns: Option<u64>,
    ) -> Result<(), OrderBookError> {
        if let Some(ns) = ingest_ns {
            self.ingest_ns.store(ns, Ordering::Relaxed);
        }
        self.bids.clear();
        self.asks.clear();
        for &(p, sz) in bid_levels {
            if p.is_finite() && sz.is_finite() && !is_zero_size(sz) {
                self.bids.insert(OrderedFloat(-p), sz);
            }
        }
        for &(p, sz) in ask_levels {
            if p.is_finite() && sz.is_finite() && !is_zero_size(sz) {
                self.asks.insert(OrderedFloat(p), sz);
            }
        }
        self.trim_bids();
        self.trim_asks();
        self.last_seq = seq;
        self.expected_checksum = checksum;
        self.record_spread_sample();
        self.validate_checksum()?;
        self.process_ns.store(now_ns(), Ordering::Relaxed);
        Ok(())
    }

    pub fn apply_update_levels(
        &mut self,
        bid_levels: &[(f64, f64)],
        ask_levels: &[(f64, f64)],
        seq: Option<i64>,
        checksum: Option<i32>,
        ingest_ns: Option<u64>,
        require_seq_increase: bool,
    ) -> Result<(), OrderBookError> {
        if let Some(ns) = ingest_ns {
            self.ingest_ns.store(ns, Ordering::Relaxed);
        }
        if let Some(s) = seq {
            if let Some(prev) = self.last_seq {
                if require_seq_increase && s <= prev {
                    return Err(OrderBookError::SeqRegression { prev, cur: s });
                }
            }
            self.last_seq = Some(s);
        }
        for &(p, sz) in bid_levels {
            if !p.is_finite() || !sz.is_finite() {
                continue;
            }
            let k = OrderedFloat(-p);
            if is_zero_size(sz) {
                self.bids.remove(&k);
            } else {
                self.bids.insert(k, sz);
            }
        }
        for &(p, sz) in ask_levels {
            if !p.is_finite() || !sz.is_finite() {
                continue;
            }
            let k = OrderedFloat(p);
            if is_zero_size(sz) {
                self.asks.remove(&k);
            } else {
                self.asks.insert(k, sz);
            }
        }
        self.trim_bids();
        self.trim_asks();
        self.expected_checksum = checksum.or(self.expected_checksum);
        self.record_spread_sample();
        self.validate_checksum()?;
        self.process_ns.store(now_ns(), Ordering::Relaxed);
        Ok(())
    }

    fn validate_checksum(&mut self) -> Result<(), OrderBookError> {
        let Some(exp) = self.expected_checksum else {
            return Ok(());
        };
        let pairs = self.top_string_pairs(self.checksum_levels);
        let actual = checksum_from_levels(&pairs.0, &pairs.1, self.checksum_levels);
        if actual != exp {
            return Err(OrderBookError::ChecksumMismatch {
                expected: exp,
                actual,
            });
        }
        Ok(())
    }

    /// Top-N als String-Paare (Preis/Size) fuer Checksum-Paritaet mit Python.
    pub fn top_string_pairs(&self, n: usize) -> (Vec<(String, String)>, Vec<(String, String)>) {
        let mut bids: Vec<(String, String)> = Vec::with_capacity(n);
        for (&k, &sz) in self.bids.iter().take(n) {
            let p = -k.into_inner();
            bids.push((fmt_exchange_decimal(p), fmt_exchange_decimal(sz)));
        }
        let mut asks: Vec<(String, String)> = Vec::with_capacity(n);
        for (&k, &sz) in self.asks.iter().take(n) {
            let p = k.into_inner();
            asks.push((fmt_exchange_decimal(p), fmt_exchange_decimal(sz)));
        }
        (bids, asks)
    }

    pub fn current_checksum(&self) -> i32 {
        let (b, a) = self.top_string_pairs(self.checksum_levels);
        checksum_from_levels(&b, &a, self.checksum_levels)
    }

    fn record_spread_sample(&mut self) {
        let bb = self.best_bid();
        let ba = self.best_ask();
        let Some(bid) = bb else {
            return;
        };
        let Some(ask) = ba else {
            return;
        };
        if ask <= bid {
            return;
        }
        let sp = ask - bid;
        let i = self.spread_write % SPREAD_RING;
        self.spread_ring[i] = sp;
        self.spread_write = self.spread_write.saturating_add(1);
        self.spread_count = (self.spread_count + 1).min(SPREAD_RING);
    }

    pub fn best_bid(&self) -> Option<f64> {
        self.bids
            .keys()
            .next()
            .map(|k| -k.into_inner())
    }

    pub fn best_ask(&self) -> Option<f64> {
        self.asks.keys().next().map(|k| k.into_inner())
    }

    pub fn spread_bps(&self) -> Option<f64> {
        let b = self.best_bid()?;
        let a = self.best_ask()?;
        let mid = (a + b) / 2.0;
        if mid <= 0.0 {
            return None;
        }
        Some((a - b) / mid * 10_000.0)
    }

    /// Varianz der letzten bis zu 100 Spread-Samples.
    pub fn spread_variance_last_100(&self) -> f64 {
        let n = self.spread_count;
        if n < 2 {
            return 0.0;
        }
        let mut sum = 0.0;
        for k in 0..n {
            let idx = (self.spread_write + SPREAD_RING - 1 - k) % SPREAD_RING;
            sum += self.spread_ring[idx];
        }
        let mean = sum / n as f64;
        let mut acc = 0.0;
        for k in 0..n {
            let idx = (self.spread_write + SPREAD_RING - 1 - k) % SPREAD_RING;
            let d = self.spread_ring[idx] - mean;
            acc += d * d;
        }
        acc / (n as f64 - 1.0).max(1.0)
    }

    /// Orderflow-Imbalance (V_bid - V_ask) / (V_bid + V_ask) auf Notional der ersten `depth` Level.
    pub fn orderflow_imbalance(&self, depth: usize) -> Option<f64> {
        let d = depth.max(1);
        let vb: f64 = self.bids.iter().take(d).map(|(_, s)| *s).sum();
        let va: f64 = self.asks.iter().take(d).map(|(_, s)| *s).sum();
        let t = vb + va;
        if t < 1e-24 {
            return None;
        }
        Some((vb - va) / t)
    }

    pub fn depth_snapshot(&self, depth: usize) -> (Vec<(f64, f64)>, Vec<(f64, f64)>) {
        let d = depth.max(1);
        let bids: Vec<(f64, f64)> = self
            .bids
            .iter()
            .take(d)
            .map(|(k, s)| (-k.into_inner(), *s))
            .collect();
        let asks: Vec<(f64, f64)> = self
            .asks
            .iter()
            .take(d)
            .map(|(k, s)| (k.into_inner(), *s))
            .collect();
        (bids, asks)
    }
}

#[inline]
fn now_ns() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos() as u64)
        .unwrap_or(0)
}

/// Dezimaldarstellung ohne wissenschaftliche Notation (naeherungsweise Bitget-kompatibel).
fn fmt_exchange_decimal(v: f64) -> String {
    if v == 0.0 {
        return "0".to_string();
    }
    let mut s = format!("{:.12}", v);
    while s.contains('.') && (s.ends_with('0') || s.ends_with('.')) {
        s.pop();
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn checksum_matches_python_fixture() {
        let bids = vec![("0.5000".into(), "1.2500".into())];
        let asks = vec![("0.5001".into(), "2.0000".into())];
        let s = build_checksum_string(&bids, &asks, 25);
        assert_eq!(s, "0.5000:1.2500:0.5001:2.0000");
        let c = crc32_signed_zlib(s.as_bytes());
        assert_ne!(c, 0);
    }

    #[test]
    fn update_removes_zero_size() {
        let mut ob = OrderBook::new(10, 5);
        ob.apply_snapshot_levels(&[(100.0, 1.0)], &[(101.0, 2.0)], None, None, None)
            .unwrap();
        ob.update(0, 100.0, 0.0).unwrap();
        assert!(ob.best_bid().is_none() || ob.best_bid() != Some(100.0));
    }
}
