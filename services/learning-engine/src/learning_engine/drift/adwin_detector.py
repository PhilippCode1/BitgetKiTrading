from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass, field


@dataclass
class SimpleAdwin:
    """Vereinfachtes adaptives Windowing (ADWIN-Idee): Split-Mean-Test auf dem Buffer.

    Kein vollständiges ADWIN aus dem Paper, aber echte Drift-Signale bei Mittelwertverschiebung.
    """

    delta: float = 0.002
    min_window: int = 20
    max_window: int = 200
    window: deque[float] = field(default_factory=deque)

    def update(self, x: float) -> bool:
        self.window.append(float(x))
        if len(self.window) > self.max_window:
            self.window.popleft()
        if len(self.window) < self.min_window:
            return False
        w = list(self.window)
        mid = max(1, len(w) // 2)
        first, second = w[:mid], w[mid:]
        if len(second) < 1:
            return False
        m1 = statistics.mean(first)
        m2 = statistics.mean(second)
        return abs(m1 - m2) > self.delta


def run_adwin_on_series(
    values: list[float],
    *,
    delta: float = 0.002,
    min_window: int = 20,
    max_window: int = 200,
) -> list[int]:
    """Gibt Indizes (0-basiert, nach update) zurück, an denen Drift erkannt wurde."""
    det = SimpleAdwin(delta=delta, min_window=min_window, max_window=max_window)
    hits: list[int] = []
    for i, v in enumerate(values):
        if det.update(v):
            hits.append(i)
    return hits


def _norm_sf(x: float) -> float:
    """1 - Phi(x) mit Phi Standardnormal-CDF; grosses x => kleine Tail-Wahrscheinlichkeit."""
    if x < -10:
        return 1.0
    if x > 10:
        return 0.0
    return 0.5 * math.erfc(x / math.sqrt(2.0))


def welch_t_two_sided_pvalue(
    a: list[float], b: list[float]
) -> float:
    """Grob: zwei Stichproben, ungleiche Varianz (Welch); Normalapproximation fuer grosse n."""
    if len(a) < 2 or len(b) < 2:
        return 1.0
    m1 = statistics.mean(a)
    m2 = statistics.mean(b)
    v1 = statistics.pvariance(a) if len(a) > 1 else 0.0
    v2 = statistics.pvariance(b) if len(b) > 1 else 0.0
    n1, n2 = float(len(a)), float(len(b))
    se2 = (v1 / n1) + (v2 / n2)
    if se2 <= 1e-20:
        return 1.0 if abs(m1 - m2) < 1e-15 else 0.0
    t = (m1 - m2) / math.sqrt(se2)
    p_two = 2.0 * min(1.0, _norm_sf(abs(t)))
    return max(0.0, min(1.0, p_two))


@dataclass(frozen=True)
class MseDriftStep:
    """Eine beobachtete MSE-Zeitpunkt-Auswertung (Live-Inferenz-Fehlerrate)."""

    index: int
    drift: bool
    p_value: float
    """Zweiseitiger p-Wert fuer H0: kein Verschiebung in den Fensterhalften."""
    confidence: float
    """1 - p_value; gross wenn Evidenz stark."""


@dataclass
class MseAdwinDriftMonitor:
    """
    ADWIN-ahnliches Split-Fenster (SimpleAdwin) auf MSE-Werten + p-Wert-Konfidenz (Prompt 46).

    Ausloeser: SimpleAdwin meldet Split-Drift **und** 1 - p > min_confidence (näherungsweise >99% Konfidenz).
    """

    delta: float = 0.002
    min_window: int = 20
    max_window: int = 200
    min_confidence: float = 0.99
    adwin: SimpleAdwin = field(
        default_factory=lambda: SimpleAdwin(
            delta=0.002, min_window=20, max_window=200
        )
    )

    def __post_init__(self) -> None:
        if self.adwin.delta != self.delta:
            self.adwin = SimpleAdwin(
                delta=self.delta,
                min_window=self.min_window,
                max_window=self.max_window,
            )

    def update(self, mse: float) -> MseDriftStep | None:
        """
        MSE-Beobachtung. ``drift=True`` nur bei SimpleAdwin-Alarm **und**
        statistischer Konfidenz oberhalb ``min_confidence`` (1 - p-Wert).
        """
        split_hit = self.adwin.update(float(mse))
        n = len(self.adwin.window)
        if n < self.min_window:
            return None
        w = list(self.adwin.window)
        mid = max(1, n // 2)
        first, second = w[:mid], w[mid:]
        p = (
            welch_t_two_sided_pvalue(first, second)
            if (len(first) > 1 and len(second) > 1)
            else 1.0
        )
        conf = 1.0 - p
        if not split_hit:
            return MseDriftStep(
                index=n - 1, drift=False, p_value=p, confidence=conf
            )
        if conf > self.min_confidence:
            return MseDriftStep(
                index=n - 1, drift=True, p_value=p, confidence=conf
            )
        return MseDriftStep(
            index=n - 1, drift=False, p_value=p, confidence=conf
        )
