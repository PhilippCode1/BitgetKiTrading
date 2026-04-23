//! VPIN-ähnliche Orderflow-Toxizität: volumensynchronisierte Buckets, Lee-Ready vs. Mid,
//! optional Taker-Side-Fallback (Bulk-Proxy), rollierendes Fenster über N Buckets.
//!
//! ToxicityScore ≈ Mittelwert von `|V_buy - V_sell| / V_bucket` über die letzten N
//! **vollständigen** Buckets — Werte in **[0, 1]**.

use std::collections::VecDeque;

const EPS: f64 = 1e-12;

/// Lee-Ready-Klassifikation: aggressiver Kauf genau dann, wenn `price > mid`.
/// Bei `price == mid`: Tick-Test gegen `last_price` (bei erstem Trade neutrales `last_sign`).
#[inline]
pub fn lee_ready_aggressive_buy(
    price: f64,
    mid: f64,
    last_price: Option<f64>,
    last_sign: &mut i8,
) -> bool {
    if price > mid {
        *last_sign = 1;
        true
    } else if price < mid {
        *last_sign = -1;
        false
    } else if let Some(lp) = last_price {
        if price > lp {
            *last_sign = 1;
            true
        } else if price < lp {
            *last_sign = -1;
            false
        } else {
            *last_sign >= 0
        }
    } else {
        *last_sign >= 0
    }
}

/// Reiner Tick-Test (kein Mid): `price` vs. letztem Trade-Preis.
#[inline]
pub fn tick_rule_aggressive_buy(price: f64, last_price: Option<f64>, last_sign: &mut i8) -> bool {
    match last_price {
        None => *last_sign >= 0,
        Some(lp) if price > lp => {
            *last_sign = 1;
            true
        }
        Some(lp) if price < lp => {
            *last_sign = -1;
            false
        }
        Some(_) => *last_sign >= 0,
    }
}

/// VPIN-/Toxizitäts-Akkumulator (Hot-Path: nur primitive Ops, begrenzte Allokation am Bucket-Abschluss).
#[derive(Debug, Clone)]
pub struct VpinAccumulator {
    v_bucket: f64,
    window_n: usize,
    /// Letzte N Bucket-Imbalance-Ratios `|B-S|/V_bucket`, ältestes hinten oder vorne?
    /// Wir nutzen `VecDeque`: push_back neu, pop_front wenn len > window_n.
    completed: VecDeque<f64>,
    cur_buy: f64,
    cur_sell: f64,
    mid: Option<f64>,
    last_trade_price: Option<f64>,
    last_sign: i8,
}

impl VpinAccumulator {
    pub fn new(bucket_volume: f64, window_buckets: usize) -> Self {
        let vb = bucket_volume.max(EPS);
        let wn = window_buckets.max(1);
        Self {
            v_bucket: vb,
            window_n: wn,
            completed: VecDeque::with_capacity(wn),
            cur_buy: 0.0,
            cur_sell: 0.0,
            mid: None,
            last_trade_price: None,
            last_sign: 1,
        }
    }

    #[inline]
    pub fn set_mid_from_bid_ask(&mut self, best_bid: f64, best_ask: f64) {
        if best_bid.is_finite() && best_ask.is_finite() && best_ask >= best_bid {
            self.mid = Some(0.5 * (best_bid + best_ask));
        }
    }

    #[inline]
    pub fn set_mid(&mut self, mid: f64) {
        if mid.is_finite() && mid > 0.0 {
            self.mid = Some(mid);
        }
    }

    #[inline]
    pub fn clear_mid(&mut self) {
        self.mid = None;
    }

    /// `taker_is_buy`: `Some(true)` = aggressiver Kauf, `Some(false)` = Verkauf, `None` = Tick-Regel.
    pub fn push_trade(&mut self, price: f64, volume: f64, taker_is_buy: Option<bool>) {
        if !price.is_finite() || !volume.is_finite() || volume <= EPS {
            return;
        }
        let aggressive_buy = if let Some(m) = self.mid {
            lee_ready_aggressive_buy(price, m, self.last_trade_price, &mut self.last_sign)
        } else if let Some(tb) = taker_is_buy {
            if tb {
                self.last_sign = 1;
            } else {
                self.last_sign = -1;
            }
            tb
        } else {
            tick_rule_aggressive_buy(price, self.last_trade_price, &mut self.last_sign)
        };
        self.last_trade_price = Some(price);
        self.absorb_classified_volume(volume, aggressive_buy);
    }

    fn absorb_classified_volume(&mut self, mut vol: f64, aggressive_buy: bool) {
        while vol > EPS {
            let filled = self.cur_buy + self.cur_sell;
            let room = (self.v_bucket - filled).max(0.0);
            if room < EPS {
                self.close_bucket();
                continue;
            }
            let take = vol.min(room);
            if aggressive_buy {
                self.cur_buy += take;
            } else {
                self.cur_sell += take;
            }
            vol -= take;
            if self.cur_buy + self.cur_sell >= self.v_bucket - 1e-9 {
                self.close_bucket();
            }
        }
    }

    fn close_bucket(&mut self) {
        let tot = self.cur_buy + self.cur_sell;
        if tot < EPS {
            return;
        }
        let imb = (self.cur_buy - self.cur_sell).abs() / self.v_bucket;
        let ratio = imb.clamp(0.0, 1.0);
        self.completed.push_back(ratio);
        while self.completed.len() > self.window_n {
            self.completed.pop_front();
        }
        self.cur_buy = 0.0;
        self.cur_sell = 0.0;
    }

    /// Rollierender VPIN / ToxicityScore in **[0, 1]** (Mittelwert der letzten abgeschlossenen Buckets).
    pub fn toxicity_score(&self) -> f64 {
        if self.completed.is_empty() {
            return 0.0;
        }
        let s: f64 = self.completed.iter().copied().sum();
        s / self.completed.len() as f64
    }

    #[inline]
    pub fn completed_bucket_count(&self) -> usize {
        self.completed.len()
    }

    #[inline]
    pub fn bucket_volume(&self) -> f64 {
        self.v_bucket
    }

    #[inline]
    pub fn window_buckets(&self) -> usize {
        self.window_n
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vpin_rises_on_one_sided_cascade() {
        let mut v = VpinAccumulator::new(10.0, 30);
        // Ausgeglichene Taker-Seiten: je Bucket ca. gleich viel Buy/Sell -> niedrige Toxizität
        for _ in 0..40 {
            v.push_trade(100.0, 5.0, Some(true));
            v.push_trade(100.0, 5.0, Some(false));
        }
        let low = v.toxicity_score();
        // Einseitige Kaskade aggressiver Käufe
        for _ in 0..120 {
            v.push_trade(101.0, 2.0, Some(true));
        }
        let high = v.toxicity_score();
        assert!(
            high > low + 0.25,
            "VPIN soll nach einseitiger Kaskade deutlich steigen: low={low:.4} high={high:.4}"
        );
        assert!(high > 0.65, "erwartet hohe Toxizitaet nahe 1.0, got {high:.4}");
    }

    #[test]
    fn lee_ready_respects_mid() {
        let mut v = VpinAccumulator::new(10.0, 5);
        v.set_mid(100.0);
        for _ in 0..10 {
            v.push_trade(100.5, 10.0, Some(false)); // Taker sagt sell, aber Preis > Mid -> Buy
        }
        assert!(
            v.toxicity_score() > 0.9,
            "Lee-Ready soll Taker-Side ueberstimmen wenn Mid gesetzt"
        );
    }
}
