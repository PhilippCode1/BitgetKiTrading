from __future__ import annotations

import numpy as np

import pytest

torch = pytest.importorskip("torch")

from adversarial_engine.models.wgan_gp import AdversarialMarketSimulator, wgan_gp_training_step


def test_generate_paths_high_toxicity_heavy_tails() -> None:
    sim = AdversarialMarketSimulator(latent_dim=32, seq_len=512, rho=0.7, device="cpu")
    paths, _meta = sim.generate_paths(batch=4, toxicity_0_1=0.95, seed=42)
    x = paths[0, :, 0].detach().cpu().numpy()
    m = float(x.mean())
    s = float(x.std()) or 1e-9
    skew = float(np.mean(((x - m) / s) ** 3))
    kurt = float(np.mean(((x - m) / s) ** 4) - 3.0)
    assert abs(skew) > 0.05 or kurt > 0.2


def test_wgan_gp_step_runs() -> None:
    sim = AdversarialMarketSimulator(latent_dim=16, seq_len=64, rho=0.65, device="cpu")
    real = torch.randn(8, 64, 2) * 0.3
    losses = wgan_gp_training_step(sim.critic, sim.generator, real, lambda_gp=10.0)
    assert "loss_c" in losses and "loss_g" in losses
