from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger("inference_server.timesfm")


class TimesFmModelEngine:
    """
    Laedt optional TimesFM; fehlt die Library oder die Gewichte, laeuft ein deterministischer Stub.

    Echter Pfad (Platzhalter — Dependencies im Image nachziehen):
        from timesfm import TimesFM  # Paketname je nach Release anpassen
        self._model = TimesFM.from_pretrained("google/timesfm-1.0-200m")
    """

    def __init__(self, *, model_id: str) -> None:
        self.model_id = model_id
        self._backend = "stub"
        self._model: Any = None
        self._try_load_real()

    def _try_load_real(self) -> None:
        try:
            # Platzhalter: echte Integration z. B. pip install google-timesfm / timesfm
            # und GPU-spezifische Initialisierung hier.
            import importlib.util

            if importlib.util.find_spec("timesfm") is None:
                logger.info(
                    "timesfm-Paket nicht installiert — Backend=stub (Modell %s)",
                    self.model_id,
                )
                return
            # Beispiel fuer spaeteren Echtbetrieb (bewusst auskommentiert):
            # import timesfm  # type: ignore[import-not-found]
            # self._model = timesfm.TimesFM.from_pretrained(self.model_id)
            # self._backend = "timesfm"
            logger.info(
                "timesfm gefunden, aber Echt-Laden noch deaktiviert — Backend=stub (%s)",
                self.model_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("TimesFM-Load fehlgeschlagen: %s — Backend=stub", exc)

    @property
    def backend_name(self) -> str:
        return self._backend

    def predict_batch(
        self,
        arrays: list[np.ndarray],
        *,
        horizon: int,
    ) -> list[np.ndarray]:
        if self._model is not None and self._backend == "timesfm":
            # Platzhalter fuer echtes Batch-Inferenz-API
            raise NotImplementedError("TimesFM Echt-Inferenz noch nicht angebunden")
        out: list[np.ndarray] = []
        h = max(1, int(horizon))
        for arr in arrays:
            a = np.asarray(arr, dtype=np.float64).reshape(-1)
            if a.size == 0:
                out.append(np.zeros(h, dtype=np.float32))
                continue
            tail = float(a[-1])
            d = float(a[-1] - a[-2]) if a.size >= 2 else 0.0
            fc = np.array(
                [tail + d * float(i + 1) for i in range(h)],
                dtype=np.float32,
            )
            out.append(fc)
        return out
