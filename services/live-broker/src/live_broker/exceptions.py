"""Bewusst sichtbare Laufzeit-Exceptions (nicht Bitget-Transportfehler)."""

from __future__ import annotations


class SecurityException(RuntimeError):
    """
    Sperrung laut Sicherheits- / Vertragspolicy (LIVE-Execution, Firewall).

    Wird u. a. ausgeloest, wenn ``assert_execution_allowed`` (Modul-Mate) LIVE
    ablehnt oder die Policy-DB nicht pruefbar ist.
    """

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = str(reason or "").strip() or "unknown"


class GlobalHaltException(RuntimeError):
    """
    Sofort-Stopp: Redis-Key system:global_halt + In-Process-Latch, kein Order-Write.
    """

    def __init__(
        self, message: str = "Global Halt — Exchange-Mutationen gesperrt"
    ) -> None:
        super().__init__(message)


class ShadowDivergenceError(RuntimeError):
    """
    Echtgeld-Submit ohne erfolgreiche Shadow-Redis-Latch-Quittung
    (``REQUIRE_SHADOW_MATCH_BEFORE_LIVE`` + ``shadow:match:{execution_id}`` fehlt/abgelaufen).
    """

    def __init__(self, message: str, *, reason: str = "shadow_match_latch") -> None:
        super().__init__(message)
        self.reason = str(reason or "shadow_match_latch").strip()
