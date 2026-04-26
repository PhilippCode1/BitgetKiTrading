"""MagicMock-Sequenzen fuer assert_execution_allowed(..., mode='LIVE').

fetch_tenant_modul_mate_gates und tenant_has_active_live_commercial_contract rufen
je apply_tenant_rls_guc auf (2x set_config-execute), danach je ein SELECT mit fetchone.
"""

from __future__ import annotations

from unittest.mock import MagicMock


def _rls_execute_stub() -> MagicMock:
    """Rueckgabe von conn.execute fuer set_config; fetchone wird nicht aufgerufen."""
    return MagicMock()


def live_mode_conn_execute_sequence(ex_g: MagicMock, ex_c: MagicMock) -> list[MagicMock]:
    """Reihenfolge: RLS, RLS, Gates-SELECT, RLS, RLS, tenant_contract-SELECT."""
    return [
        _rls_execute_stub(),
        _rls_execute_stub(),
        ex_g,
        _rls_execute_stub(),
        _rls_execute_stub(),
        ex_c,
    ]
