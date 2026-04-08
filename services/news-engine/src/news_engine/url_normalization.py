"""Kanonisierung von News-URLs fuer stabilere Dedupe (Tracking-Parameter entfernen)."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_STRIP_QUERY_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "gclid",
        "fbclid",
        "mc_cid",
        "mc_eid",
        "igshid",
    }
)


def canonical_news_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return raw
    p = urlparse(raw)
    if not p.scheme or not p.netloc:
        return raw
    pairs = [
        (k, v)
        for k, v in parse_qsl(p.query, keep_blank_values=False)
        if k.lower() not in _STRIP_QUERY_KEYS
    ]
    pairs.sort(key=lambda kv: (kv[0], kv[1]))
    query = urlencode(pairs) if pairs else ""
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return urlunparse((p.scheme.lower(), host, p.path or "", "", query, ""))
