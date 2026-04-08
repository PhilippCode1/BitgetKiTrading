from __future__ import annotations

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
