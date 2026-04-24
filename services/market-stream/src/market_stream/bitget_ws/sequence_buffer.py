"""
Sequenz-Puffer fuer Bitget Public-WS: erkennt Luecken, buffert, Timer max. gap_buffer_ms
(seit letztem Armieren), loest sonst Timeout-Callback aus.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from market_stream.normalization.models import extract_sequence

OnGapTimeout = Callable[[str, int], Awaitable[None]]


@dataclass
class _PerKeyState:
    last_published: int | None = None
    pending: dict[int, dict[str, Any]] = field(default_factory=dict)
    timer: asyncio.Task[None] | None = None
    gap_started_monotonic: float | None = None


def lost_sequence_tick_count(
    last_published: int, pending: dict[int, dict[str, Any]]
) -> int:
    """Fehlende Sequenz-IDs bis max(pending), die nicht in pending vorkommen."""
    if not pending or last_published < 0:
        return 0
    m = max(pending)
    return sum(1 for i in range(last_published + 1, m + 1) if i not in pending)


class BitgetWsSequenceBuffer:
    def __init__(
        self,
        *,
        gap_buffer_ms: float = 500.0,
        on_gap_timeout: OnGapTimeout,
        logger: logging.Logger | None = None,
    ) -> None:
        self._gap_s = max(0.01, gap_buffer_ms / 1000.0)
        self._on_gap_timeout = on_gap_timeout
        self._log = logger or logging.getLogger("market_stream.ws.seqbuf")
        self._by_key: dict[str, _PerKeyState] = {}

    def clear(self) -> None:
        for st in self._by_key.values():
            self._cancel_timer(st, drop_task_ref=True)
        self._by_key.clear()

    def _cancel_timer(self, st: _PerKeyState, *, drop_task_ref: bool) -> None:
        if st.timer is not None and not st.timer.done():
            st.timer.cancel()
        if drop_task_ref:
            st.timer = None
        st.gap_started_monotonic = None

    def _arm_or_reset_timer(self, key: str, st: _PerKeyState) -> None:
        """Frist neu ab jetzt, solange noch gepufferte Nachrichten eine Luecke erzwingen."""
        if st.last_published is None or not st.pending:
            self._cancel_timer(st, drop_task_ref=True)
            return
        m = min(st.pending)
        if m == st.last_published + 1:
            return
        self._cancel_timer(st, drop_task_ref=True)
        st.gap_started_monotonic = time.monotonic()
        st.timer = asyncio.create_task(
            self._gap_timer_after_delay(key), name=f"seqbuf-gap:{key[:32]}"
        )

    async def feed(
        self,
        key: str | None,
        message: dict[str, Any],
    ) -> list[dict[str, Any]]:
        if key is None:
            return [message]
        seq = extract_sequence(message)
        if seq is None:
            return [message]

        st = self._by_key.setdefault(key, _PerKeyState())
        lcurr = st.last_published
        if lcurr is None:
            st.last_published = seq
            more = self._drain_in_order_from_pending(st, new_last=seq)
            out = [message, *more]
            self._arm_or_reset_timer(key, st)
            return out

        if seq <= lcurr:
            return []

        if seq == lcurr + 1:
            st.last_published = seq
            st.gap_started_monotonic = None
            out: list[dict[str, Any]] = [message]
            out.extend(self._drain_in_order_from_pending(st, new_last=seq))
            if not st.pending:
                self._cancel_timer(st, drop_task_ref=True)
            else:
                self._arm_or_reset_timer(key, st)
            return out

        st.pending[seq] = message
        self._arm_or_reset_timer(key, st)
        return []

    def _drain_in_order_from_pending(
        self, st: _PerKeyState, *, new_last: int
    ) -> list[dict[str, Any]]:
        res: list[dict[str, Any]] = []
        nxt = new_last + 1
        while nxt in st.pending:
            m = st.pending.pop(nxt)
            st.last_published = nxt
            res.append(m)
            nxt = st.last_published + 1
        return res

    async def _gap_timer_after_delay(self, key: str) -> None:
        try:
            await asyncio.sleep(self._gap_s)
            await self._handle_timeout_on_key(key)
        except asyncio.CancelledError:
            return

    async def _handle_timeout_on_key(self, key: str) -> None:
        st = self._by_key.get(key)
        if st is None or not st.pending:
            if st is not None:
                st.timer = None
            return

        lpub = st.last_published
        if lpub is None:
            st.pending.clear()
            self._cancel_timer(st, drop_task_ref=True)
            return

        lost = lost_sequence_tick_count(lpub, st.pending)
        st.pending.clear()
        self._cancel_timer(st, drop_task_ref=True)
        st.last_published = None
        if key in self._by_key:
            del self._by_key[key]
        self._log.debug("sequence buffer gap timeout key=%s lost=%s", key, lost)
        try:
            await self._on_gap_timeout(key, lost)
        except Exception as exc:  # noqa: BLE001
            self._log.warning("on_gap_timeout failed key=%s: %s", key, exc)
