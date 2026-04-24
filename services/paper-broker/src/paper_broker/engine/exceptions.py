from __future__ import annotations

from shared_py.bitget import UnknownInstrumentError


class InstrumentNotFoundError(UnknownInstrumentError):
    """Symbol fehlt in app.instrument_catalog (Postgres)."""


__all__ = ["InstrumentNotFoundError"]
