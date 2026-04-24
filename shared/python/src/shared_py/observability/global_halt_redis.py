"""
Redis-Key / Parsing fuer system:global_halt (Prompt 21), ohne live_broker-Import.
"""

from __future__ import annotations

REDIS_KEY_GLOBAL_HALT = "system:global_halt"
PUB_CHANNEL_GLOBAL_HALT = "system:global_halt:pub"


def parse_global_halt_value(raw: str | None) -> bool:
    if raw is None:
        return False
    s = str(raw).strip().lower()
    if s in ("", "0", "false", "no", "off", "ok", "release", "go"):
        return False
    return s in (
        "1",
        "true",
        "yes",
        "on",
        "halt",
        "stop",
        "global_halt",
        "emergency",
    ) or s.startswith("halt")
