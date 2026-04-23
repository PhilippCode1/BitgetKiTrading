"""Brücke zum nativen Modul ``apex_core`` (Rust/PyO3, gebaut mit **Maturin**).

**Zero-Copy / Buffer-Protocol:** Kernfunktionen in ``apex_core`` nutzen ``numpy.PyReadonlyArray1``
(1D ``float64``, C-contiguous) — keine Kopie aus Python-Listen; ndarray-Views werden direkt in
Rust/ndarray eingelesen. Vor Aufrufen ``assert_float64_c_contiguous`` nutzen, um implizite
``astype``/Reorders zu vermeiden.

Dieses Paket kann **ohne** kompilierte Extension importiert werden. Fehlt die Binärdatei,
wird eine **Warnung** geloggt und ein Python-Fallback für ``check_core_latency()`` genutzt.

**Lokale Kompilierung (Entwickler:innen)**

1. Virtuelle Umgebung mit **Python 3.11+** aktivieren.
2. Maturin installieren, z. B.::

       pip install "maturin>=1.7,<2"

3. Im Verzeichnis ``shared_rs/apex_core`` ausführen::

       maturin develop --release

   Damit landet die Extension in der aktuellen Umgebung; anschließend funktioniert
   ``import apex_core`` und ``apex_core.check_core_latency()`` nativ.

4. Optional Release-Wheel (Workspace-``target`` unter ``shared_rs/target``)::

       maturin build --release --interpreter python
       pip install ../target/wheels/apex_core-*.whl
"""

from __future__ import annotations

import logging
import time
from types import ModuleType
from typing import Final, Optional

logger = logging.getLogger(__name__)

_apex_core: Optional[ModuleType] = None
try:
    import apex_core as _native_apex_core  # type: ignore[import-not-found]
except ImportError:
    logger.warning(
        "Native Erweiterung `apex_core` nicht gefunden (Rust-Build fehlt?). "
        "Bitte in `shared_rs/apex_core` mit Maturin bauen: `maturin develop --release`. "
        "Verwende Python-Fallback für `check_core_latency()`.",
    )
else:
    _apex_core = _native_apex_core

APEX_CORE_AVAILABLE: Final[bool] = _apex_core is not None


def assert_float64_c_contiguous(name: str, arr: object) -> None:
    """
    Harte Vorbedingung fuer Rust-FFI ohne zusaetzliche Kopie.

    Raises:
        TypeError / ValueError: wenn nicht ``numpy.ndarray`` dtype float64 und C-contiguous.
    """
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("numpy erforderlich fuer apex_core Array-Interop") from exc
    if not isinstance(arr, np.ndarray):
        raise TypeError(f"{name}: ndarray float64 erwartet, got {type(arr).__name__}")
    if arr.dtype != np.float64:
        raise ValueError(f"{name}: dtype float64 erforderlich, ist {arr.dtype}")
    if not arr.flags.c_contiguous:
        raise ValueError(f"{name}: C-contiguous ndarray erforderlich (np.ascontiguousarray)")


def get_apex_core() -> Optional[ModuleType]:
    """Gibt das importierte ``apex_core``-Modul zurück oder ``None``, falls nicht gebaut."""
    return _apex_core


def check_core_latency() -> int:
    """Nanosekunden-Zeitstempel (UTC seit UNIX_EPOCH): nativ oder per ``time.time_ns()``."""
    if _apex_core is not None:
        return int(_apex_core.check_core_latency())
    return time.time_ns()
