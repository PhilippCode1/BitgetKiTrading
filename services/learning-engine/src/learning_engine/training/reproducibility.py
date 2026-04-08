"""
Reproduzierbarkeit: Laufzeit, Code-Revision, optional Hash ueber Learning-Engine-Quellen.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def _learning_engine_package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def try_git_revision() -> str | None:
    root = _learning_engine_package_root().parents[2]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def learning_engine_source_bundle_hash(*, max_files: int = 400) -> str:
    """
    SHA256 ueber sortierte .py-Dateien unter learning_engine (ohne __pycache__).
    Stabil bei unveraendertem Quellbaum; aendert sich bei jedem Code-Edit.
    """
    root = _learning_engine_package_root()
    paths = sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    h = hashlib.sha256()
    count = 0
    for path in paths:
        if count >= max_files:
            h.update(b"<<truncated>>")
            break
        try:
            rel = path.relative_to(root).as_posix().encode()
            h.update(rel)
            h.update(b"\0")
            h.update(path.read_bytes())
            h.update(b"\0")
        except OSError:
            continue
        count += 1
    return h.hexdigest()[:40]


def collect_reproducibility_context() -> dict[str, Any]:
    numpy_ver = ""
    sklearn_ver = ""
    try:
        import numpy as np

        numpy_ver = str(np.__version__)
    except Exception:
        pass
    try:
        import sklearn

        sklearn_ver = str(sklearn.__version__)
    except Exception:
        pass
    revision = os.environ.get("LEARNING_CODE_REVISION") or try_git_revision()
    return {
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED"),
        "code_revision_git_or_env": revision,
        "learning_engine_source_bundle_sha256_40": learning_engine_source_bundle_hash(),
        "numpy_version": numpy_ver or None,
        "sklearn_version": sklearn_ver or None,
        "notes_de": (
            "Gleiche DB-Zeilen + gleicher TRAIN_RANDOM_STATE + gleiche Package-Versionen "
            "und PYTHONHASHSEED=0 ergeben typischerweise identische joblib-Seeds; "
            "kleine numerische Drifts durch BLAS/Threading sind moeglich."
        ),
    }
