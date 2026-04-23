//! Black-Swan-artige Regime-Disruption: Score + Hysterese fuer Safe-Exit.
//! C-ABI fuer Python (ctypes), damit der Kern auch bei gehaengtem Interpreter
//! aus einem separaten Rust-Binaerprozess geladen werden kann.

#[repr(C)]
#[derive(Clone, Copy, Debug, Default)]
pub struct SurvivalKernelParams {
    pub enter_threshold: f64,
    pub exit_threshold: f64,
    pub exit_hysteresis_ticks: u32,
}

impl SurvivalKernelParams {
    pub fn default_params() -> Self {
        Self {
            enter_threshold: 6.0,
            exit_threshold: 3.5,
            exit_hysteresis_ticks: 5,
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct SurvivalKernelIo {
    pub drift_z: f64,
    pub tsfm_residual_z: f64,
    pub ams_toxicity_0_1: f64,
    /// 0 = aus, 1 = aktiv (FFI: u32 statt u8 wegen ctypes-Alignment)
    pub in_survival_prev: u32,
    pub consec_low_score_ticks: u32,
    pub score_out: f64,
    pub in_survival_out: u32,
    pub enter_event: u32,
    pub exit_event: u32,
    pub execution_lock_out: u32,
}

impl Default for SurvivalKernelIo {
    fn default() -> Self {
        Self {
            drift_z: 0.0,
            tsfm_residual_z: 0.0,
            ams_toxicity_0_1: 0.0,
            in_survival_prev: 0,
            consec_low_score_ticks: 0,
            score_out: 0.0,
            in_survival_out: 0,
            enter_event: 0,
            exit_event: 0,
            execution_lock_out: 0,
        }
    }
}

#[inline]
fn clamp01(x: f64) -> f64 {
    x.clamp(0.0, 1.0)
}

#[inline]
pub fn disruption_score(drift_z: f64, tsfm_residual_z: f64, ams_toxicity_0_1: f64) -> f64 {
    let t = clamp01(ams_toxicity_0_1);
    (drift_z.abs() + tsfm_residual_z.abs() + 4.0 * t).clamp(0.0, 1.0e6)
}

/// Reiner Rust-Schritt (Tests + Python-Spiegelung).
pub fn survival_step(
    prev_in_survival: bool,
    consec_low: u32,
    drift_z: f64,
    tsfm_residual_z: f64,
    ams_toxicity_0_1: f64,
    params: &SurvivalKernelParams,
) -> (bool, u32, f64, bool, bool) {
    let score = disruption_score(drift_z, tsfm_residual_z, ams_toxicity_0_1);
    let mut in_survival = prev_in_survival;
    let mut consec = consec_low;
    let mut enter = false;
    let mut exit = false;

    if prev_in_survival {
        if score < params.exit_threshold {
            consec = consec.saturating_add(1);
        } else {
            consec = 0;
        }
        if consec >= params.exit_hysteresis_ticks {
            in_survival = false;
            consec = 0;
            exit = true;
        }
    } else if score >= params.enter_threshold {
        in_survival = true;
        consec = 0;
        enter = true;
    } else {
        consec = 0;
    }

    (in_survival, consec, score, enter, exit)
}

/// # Safety
/// `io` und `params` muessen gueltige Zeiger sein.
#[no_mangle]
pub unsafe extern "C" fn survival_kernel_evaluate_io(
    io: *mut SurvivalKernelIo,
    params: *const SurvivalKernelParams,
) {
    if io.is_null() || params.is_null() {
        return;
    }
    let p = &*params;
    let mut slot = std::ptr::read(io);
    let prev = slot.in_survival_prev != 0;
    let (in_survival, consec, score, enter, exit) = survival_step(
        prev,
        slot.consec_low_score_ticks,
        slot.drift_z,
        slot.tsfm_residual_z,
        slot.ams_toxicity_0_1,
        p,
    );
    slot.score_out = score;
    slot.in_survival_out = u32::from(in_survival);
    slot.enter_event = u32::from(enter);
    slot.exit_event = u32::from(exit);
    slot.execution_lock_out = u32::from(in_survival);
    slot.consec_low_score_ticks = consec;
    std::ptr::write(io, slot);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extreme_anomaly_enters_immediately() {
        let p = SurvivalKernelParams::default_params();
        let (in_s, _, score, enter, _) = survival_step(false, 0, 9.0, 2.0, 0.2, &p);
        assert!(score > p.enter_threshold);
        assert!(in_s);
        assert!(enter);
    }

    #[test]
    fn safe_exit_requires_low_score_ticks() {
        let p = SurvivalKernelParams::default_params();
        let mut ins = true;
        let mut c = 0u32;
        let mut exited = false;
        for i in 0..10 {
            let (next_ins, next_c, _, _, ex) =
                survival_step(ins, c, 1.0, 0.5, 0.05, &p);
            ins = next_ins;
            c = next_c;
            if ex {
                assert!(i >= 4, "Hysterese: mindestens fuenf tiefe Scores");
                exited = true;
                break;
            }
        }
        assert!(exited);
        assert!(!ins);
    }
}
