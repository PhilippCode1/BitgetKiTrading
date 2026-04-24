"""
Unit-Test-Defaults: schnellere Redis-Init-Reconnects (kein 1+2+4+10s-Backoff in CI).
"""

from __future__ import annotations

import os

os.environ.setdefault("REDIS_INIT_RECONNECT_FAST", "1")

