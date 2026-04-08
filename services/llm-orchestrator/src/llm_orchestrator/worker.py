"""
Internes Worker-Modul (Prompt 16): Platzhalter fuer zukuenftige Queue-Verarbeitung.

RPM/TPM-Throttling und asynchrone Jobs koennen hier angebunden werden, ohne die
synchrone HTTP-API zu blockieren. Aktuell erfolgt Retry/Backoff im Request-Pfad.
"""

from __future__ import annotations

import asyncio
from typing import Any

# Reserviert fuer Prompt 17+ (News-Scoring Batch)
_task_queue: asyncio.Queue[dict[str, Any]] | None = None


def get_internal_queue() -> asyncio.Queue[dict[str, Any]]:
    global _task_queue
    if _task_queue is None:
        _task_queue = asyncio.Queue()
    return _task_queue
