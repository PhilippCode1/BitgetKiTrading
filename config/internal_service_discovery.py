"""
Reine Hilfen fuer interne Service-Discovery (Gateway -> Worker).

Basis-URLs werden aus vollstaendigen Health-URLs (z. B. `http://llm-orchestrator:8070/ready`)
als `scheme://netloc` abgeleitet — ohne Pfad, Query oder Fragment, ohne trailing slash.

Siehe API_INTEGRATION_STATUS.md: `INTERNAL_API_KEY` + Header `X-Internal-Service-Key`
(shared_py.service_auth.INTERNAL_SERVICE_HEADER). Nicht verwechseln mit
`GATEWAY_INTERNAL_API_KEY` / `X-Gateway-Internal-Key` (Gateway-internes Admin-Auth).
"""

from __future__ import annotations

from urllib.parse import urlparse


def http_base_from_health_or_ready_url(url: str) -> str:
    """
    Extrahiert die HTTP(S)-Basis-URL aus einer Health-/Ready-URL.

    Gueltig: scheme + netloc (Host/Port). IPv6 in netloc wird von urlparse unterstuetzt.
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
