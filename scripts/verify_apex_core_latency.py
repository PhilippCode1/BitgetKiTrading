"""Kurztest: ``apex_core.check_core_latency()`` bzw. Bridge-Fallback.

Ausführung (Repo-Root)::

    python scripts/verify_apex_core_latency.py

Mit gebauter Extension (nach ``maturin develop`` in ``shared_rs/apex_core``) sollte
``apex_core`` direkt importierbar sein.

Hinweis: Dieses Skript lädt ``rust_core_bridge`` per ``importlib``, um **nicht** das
gesamte ``shared_py``-Paket (``__init__.py``) zu aktivieren — das vermeidet fehlende
Runtime-Pfade wie ``config`` bei einem schlanken Host-Checkout.
"""

from __future__ import annotations

import importlib.util
import os
import sys


def _load_rust_core_bridge():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.join(root, "shared", "python", "src", "shared_py", "rust_core_bridge.py")
    spec = importlib.util.spec_from_file_location("rust_core_bridge", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Konnte rust_core_bridge nicht laden.")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    try:
        import apex_core  # type: ignore[import-not-found]

        value = int(apex_core.check_core_latency())
        source = "apex_core (Rust)"
    except ImportError:
        bridge = _load_rust_core_bridge()
        value = int(bridge.check_core_latency())
        source = "rust_core_bridge (Python-Fallback)"

    if value <= 0:
        print("Unerwarteter Zeitstempel:", value, file=sys.stderr)
        return 1
    print(source, value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
