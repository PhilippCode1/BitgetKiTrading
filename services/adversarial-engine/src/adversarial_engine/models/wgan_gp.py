"""
WGAN-GP (Wasserstein GAN + Gradient Penalty) fuer bivariate Finanz-Zeitreihen.

Kanaele (pro Zeitschritt): [log_return, depth_imbalance] mit fixierbarer Ziel-Korrelation
(Pearson) zwischen Preisbewegung und Orderbuch-Tiefen-Proxy (L3-aggregiert als Bid/Ask-Size-Imbalance).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn


class WGANGenerator(nn.Module):
    """MLP-Generator: Rauschen + Giftigkeit -> Sequenz (B, T, 2)."""

    def __init__(self, *, latent_dim: int, seq_len: int, hidden: int = 256) -> None:
        super().__init__()
        self.seq_len = int(seq_len)
        self.latent_dim = int(latent_dim)
        out_dim = self.seq_len * 2
        self.net = nn.Sequential(
            nn.Linear(self.latent_dim + 1, hidden),
            nn.LeakyReLU(0.2),
            nn.Linear(hidden, hidden),
            nn.LeakyReLU(0.2),
            nn.Linear(hidden, out_dim),
        )

    def forward(self, z: torch.Tensor, toxicity: torch.Tensor) -> torch.Tensor:
        # z: (B, Dz), toxicity: (B, 1)
        x = torch.cat([z, toxicity.clamp(0.0, 1.0)], dim=-1)
        h = self.net(x)
        return h.view(-1, 2, self.seq_len).transpose(1, 2)  # (B, T, 2)


class WGANCritic(nn.Module):
    """1-Lipschitz approximierender Critic auf flachen Sequenzen."""

    def __init__(self, *, seq_len: int, hidden: int = 256) -> None:
        super().__init__()
        flat = seq_len * 2
        self.net = nn.Sequential(
            nn.Linear(flat, hidden),
            nn.LeakyReLU(0.2),
            nn.Linear(hidden, hidden),
            nn.LeakyReLU(0.2),
            nn.Linear(hidden, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, 2)
        b = x.shape[0]
        return self.net(x.reshape(b, -1))


def gradient_penalty(
    critic: WGANCritic,
    real: torch.Tensor,
    fake: torch.Tensor,
) -> torch.Tensor:
    """WGAN-GP nach Gulrajani et al."""
    b = real.size(0)
    eps = torch.rand(b, 1, 1, device=real.device, dtype=real.dtype)
    interp = eps * real + (1.0 - eps) * fake
    interp = interp.detach().requires_grad_(True)
    out = critic(interp)
    grad = torch.autograd.grad(
        outputs=out.sum(),
        inputs=interp,
        create_graph=True,
        retain_graph=True,
        only_inputs=True,
    )[0]
    gn = grad.reshape(b, -1).norm(2, dim=1)
    return ((gn - 1.0) ** 2).mean()


def _cholesky_correlated_noise(
    batch: int,
    seq_len: int,
    rho: float,
    device: torch.device,
    dtype: torch.dtype,
) -> torch.Tensor:
    """Univariate weiss -> Korrelation rho zwischen Spalte 0 und 1 (Pearson ~ rho)."""
    r = max(-0.95, min(0.95, float(rho)))
    cov = torch.tensor([[1.0, r], [r, 1.0]], device=device, dtype=dtype)
    l = torch.linalg.cholesky(cov)
    z = torch.randn(batch, seq_len, 2, device=device, dtype=dtype)
    return z @ l.T


def _analytic_stress_envelope(seq_len: int, toxicity: torch.Tensor, device: torch.device) -> torch.Tensor:
    """
    Deterministische Crash-/Austrocknungs-Huelle (B, T, 2).
    toxicity: (B,1) skaliert Amplitude.
    """
    t = torch.linspace(0.0, 1.0, seq_len, device=device, dtype=toxicity.dtype)
    # Flash-crash-aehnlicher negativer Driftcluster in der Sequenzmitte
    mid = torch.exp(-((t - 0.55) ** 2) / (2 * 0.08**2))
    ret_env = -2.5 * mid * toxicity.view(-1, 1)
    # Orderbuch-Austrocknung: Imbalance kippt (gebrochene Liquiditaet)
    dry = torch.sin(math.pi * t) ** 3
    depth_env = -1.8 * dry * toxicity.view(-1, 1)
    return torch.stack([ret_env, depth_env], dim=-1)


class AdversarialMarketSimulator:
    """
    Haelt Generator/Critic; erzeugt Stress-Pfade.

    Ohne Checkpoint: zufaellig initialisierte Gewichte + analytische Stress-Huelle
    erzeugen statistisch schwere Verteilungen (Hohe Kurtosis / Skew).
    """

    def __init__(
        self,
        *,
        latent_dim: int,
        seq_len: int,
        rho: float,
        device: str | torch.device | None = None,
        checkpoint_path: str | None = None,
    ) -> None:
        self.latent_dim = int(latent_dim)
        self.seq_len = int(seq_len)
        self.rho = float(rho)
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.generator = WGANGenerator(latent_dim=self.latent_dim, seq_len=self.seq_len).to(self.device)
        self.critic = WGANCritic(seq_len=self.seq_len).to(self.device)
        self.generator.train(False)
        self.critic.train(False)
        if checkpoint_path:
            p = Path(checkpoint_path)
            if p.is_file():
                try:
                    blob = torch.load(p, map_location=self.device, weights_only=True)
                except TypeError:
                    blob = torch.load(p, map_location=self.device)
                if isinstance(blob, dict):
                    if "generator" in blob:
                        self.generator.load_state_dict(blob["generator"], strict=False)
                    if "critic" in blob:
                        self.critic.load_state_dict(blob["critic"], strict=False)

    def generate_paths(
        self,
        *,
        batch: int,
        toxicity_0_1: float,
        seed: int | None,
        rho: float | None = None,
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """
        Gibt Tensor (B, T, 2) zurueck: [:,:,0] log-Returns, [:,:,1] Tiefen-Imbalance (zentriert).
        """
        if seed is not None:
            torch.manual_seed(int(seed))
        b = max(1, int(batch))
        tox = float(max(0.0, min(1.0, toxicity_0_1)))
        toxicity = torch.full((b, 1), tox, device=self.device, dtype=torch.float32)
        z = torch.randn(b, self.latent_dim, device=self.device, dtype=torch.float32)
        r = self.rho if rho is None else float(rho)
        base = _cholesky_correlated_noise(b, self.seq_len, r, self.device, z.dtype)
        g_res = torch.tanh(self.generator(z, toxicity))
        env = _analytic_stress_envelope(self.seq_len, toxicity, self.device)
        # Mische korreliertes Rauschen, GAN-Residual und analytische Extremform
        mix = (0.35 + 0.65 * tox) * base + tox * (0.55 * g_res) + (0.45 + 0.55 * tox) * env
        meta = {
            "latent_dim": self.latent_dim,
            "seq_len": self.seq_len,
            "rho_target": r,
            "toxicity": tox,
            "device": str(self.device),
        }
        return mix.detach(), meta


def wgan_gp_training_step(
    critic: WGANCritic,
    generator: WGANGenerator,
    real_data: torch.Tensor,
    *,
    lambda_gp: float = 10.0,
    lr: float = 1e-4,
) -> dict[str, float]:
    """
    Ein kombinierter Trainings-Schritt (Demo / Offline-Training).

    real_data: (B, T, 2) echte oder historische Extremfaelle.
    """
    device = next(critic.parameters()).device
    b = real_data.size(0)
    opt_c = torch.optim.Adam(critic.parameters(), lr=lr, betas=(0.5, 0.9))
    opt_g = torch.optim.Adam(generator.parameters(), lr=lr, betas=(0.5, 0.9))

    z = torch.randn(b, generator.latent_dim, device=device)
    tox = torch.rand(b, 1, device=device)
    fake = (
        _cholesky_correlated_noise(b, generator.seq_len, 0.7, device, real_data.dtype)
        + 0.4
        * torch.tanh(generator(z, tox))
        + 0.35 * _analytic_stress_envelope(generator.seq_len, tox, device)
    )

    opt_c.zero_grad(set_to_none=True)
    c_real = critic(real_data).mean()
    c_fake = critic(fake.detach()).mean()
    gp = gradient_penalty(critic, real_data, fake.detach())
    loss_c = -(c_real - c_fake) + float(lambda_gp) * gp
    loss_c.backward()
    opt_c.step()

    opt_g.zero_grad(set_to_none=True)
    z2 = torch.randn(b, generator.latent_dim, device=device)
    tox2 = torch.rand(b, 1, device=device)
    fake2 = (
        _cholesky_correlated_noise(b, generator.seq_len, 0.7, device, real_data.dtype)
        + 0.4 * torch.tanh(generator(z2, tox2))
        + 0.35 * _analytic_stress_envelope(generator.seq_len, tox2, device)
    )
    loss_g = -critic(fake2).mean()
    loss_g.backward()
    opt_g.step()

    return {"loss_c": float(loss_c.detach().cpu()), "loss_g": float(loss_g.detach().cpu())}
