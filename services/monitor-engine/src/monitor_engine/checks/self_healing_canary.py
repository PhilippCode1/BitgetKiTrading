"""
Optionaler Canary: simuliert CRITICAL_RUNTIME_EXCEPTION fuer die Self-Healing-Pipeline.

Nur mit ``MONITOR_SELF_HEALING_CANARY_ENABLED=true`` (typisch local/test).
"""

from __future__ import annotations

from monitor_engine.alerts.rules import AlertSpec
from monitor_engine.config import MonitorEngineSettings


def collect_self_healing_canary_alerts(settings: MonitorEngineSettings) -> list[AlertSpec]:
    if not settings.monitor_self_healing_canary_enabled:
        return []
    wrong = "wrong-mix/market/tickers"
    ok = "mix/market/tickers"
    stack = (
        "Traceback (most recent call last):\n"
        '  File "services/api-gateway/src/api_gateway/foo.py", line 42, in probe\n'
        f"    raise httpx.HTTPStatusError('404', request=None, response=None)\n"
        f"httpx.HTTPStatusError: Client error '404 Not Found' for url "
        f"'https://api.bitget.com/api/v2/{wrong}'\n"
    )
    return [
        AlertSpec(
            alert_key="CRITICAL_RUNTIME_EXCEPTION",
            severity="critical",
            title="Canary: Bitget REST-Pfad (simuliert)",
            message=f"404 auf falsch konfiguriertem Pfadsegment ({wrong})",
            details={
                "stacktrace": stack,
                "expected_path_segment": ok,
                "wrong_path_segment": wrong,
                "origin": "monitor_self_healing_canary",
                "repository_refs": ["shared/python/src/shared_py/bitget/"],
            },
            priority=2,
        )
    ]
