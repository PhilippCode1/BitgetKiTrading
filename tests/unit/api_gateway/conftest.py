"""API-Gateway-Unit: kein lokaler Postgres/Redis fuer App-Lifespan noetig."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _unit_api_gateway_skip_migration_latch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verhindert DB-Connect im FastAPI-Lifespan (siehe shared_py.migration_latch).

    Integrationstests mit echtem Stack nutzen eigene Fixtures/URLs; hier geht es um
    Routen- und Auth-Verhalten ohne laufende Datenbank.
    """
    monkeypatch.setenv("BITGET_SKIP_MIGRATION_LATCH", "1")
