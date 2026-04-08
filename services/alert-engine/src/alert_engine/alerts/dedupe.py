from __future__ import annotations

from alert_engine.storage.repo_dedupe import RepoDedupe


def should_send_with_dedupe(
    repo: RepoDedupe, dedupe_key: str | None, ttl_minutes: int
) -> bool:
    if not dedupe_key:
        return True
    return repo.try_acquire(dedupe_key, ttl_minutes)
