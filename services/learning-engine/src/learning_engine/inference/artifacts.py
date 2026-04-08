from __future__ import annotations

from pathlib import Path
from typing import Any

from joblib import load


def load_joblib_artifact(path: str | Path) -> Any:
    """Laedt ein persistiertes Modell-Artefakt (Inferenzpfad, kein Training)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Modell-Artefakt fehlt: {p}")
    return load(p)
