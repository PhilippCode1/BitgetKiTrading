from __future__ import annotations

from llm_orchestrator.agents.tsfm_semantics import synthesize_tsfm_signal
from llm_orchestrator.agents.tsfm_types import TsfmSignalCandidatePayloadV1


def test_tsfm_payload_validate_and_synthesis() -> None:
    raw = {
        "schema": "tsfm_signal_candidate/v1",
        "source_ts_ms": 1_700_000_000_000,
        "context_len": 512,
        "forecast_horizon": 64,
        "forecast_sha256": "a" * 64,
        "forecast_preview": [100.0, 100.1, 100.4],
        "prep_meta": {},
        "confidence_0_1": 0.88,
        "patch_variance": 0.01,
        "patch_incr_std": 0.012,
        "model_id": "timesfm-test",
    }
    m = TsfmSignalCandidatePayloadV1.from_envelope_payload(raw)
    assert m is not None
    syn = synthesize_tsfm_signal(m)
    assert syn.directional_bias == "long"
    assert "Zero-Shot Pattern Recognition" in syn.narrative_de
    assert 0.0 <= syn.synthesis_confidence_0_1 <= 1.0
