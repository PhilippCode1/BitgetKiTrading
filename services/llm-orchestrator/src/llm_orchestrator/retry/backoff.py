from __future__ import annotations

import time


def sleep_backoff(
    attempt: int,
    *,
    base_sec: float,
    max_sec: float,
    jitter_ratio: float = 0.0,
) -> None:
    """
    Exponentielles Backoff. Ohne Jitter (Default jitter_ratio=0) voll deterministisch.
    Bei jitter_ratio>0: fester Anteil exp*jitter_ratio*0.5 (kein RNG, kein Thundering-Herd-
    Chaos im Handelskern).
    """
    exp = min(max_sec, base_sec * (2**attempt))
    jitter = exp * jitter_ratio * 0.5
    time.sleep(exp + jitter)


def is_retryable_http_status(status: int | None) -> bool:
    if status is None:
        return False
    if status == 429:
        return True
    return 500 <= status <= 599


def openai_circuit_trip_on_status(status: int | None) -> bool:
    """
    Zaehlt Fehler in ein Fenster zur OPEN-Entscheidung: 5xx, Gateway-Timeout (504).
    429 (Rate-Limit) oeffnet den nicht-Circuit-Blocker; 4xx (ausser 504) nicht.
    """
    if status is None:
        return True
    if status == 429:
        return False
    if status == 504:
        return True
    return 500 <= status <= 599
