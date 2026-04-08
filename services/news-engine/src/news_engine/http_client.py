from __future__ import annotations

from urllib.parse import urlparse

import httpx

from news_engine.config import NewsEngineSettings


def assert_url_allowed(url: str, allowed_hosts: set[str]) -> None:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        raise ValueError("URL ohne Host")
    allowed_l = {h.lower() for h in allowed_hosts}
    if host in allowed_l:
        return
    for a in allowed_l:
        if host.endswith("." + a):
            return
    raise ValueError("Host nicht in NEWS_HTTP_ALLOWED_HOSTS")


def http_get_text(url: str, settings: NewsEngineSettings) -> str:
    assert_url_allowed(url, settings.allowed_hosts_set())
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
    return resp.text
