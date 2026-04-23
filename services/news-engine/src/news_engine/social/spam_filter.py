from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("news_engine.social.spam_filter")


def allow_social_message(
    *,
    author_id: str,
    followers: int | None,
    redis: Any | None,
    min_followers: int,
    max_posts_per_window: int,
    window_sec: int = 600,
    reject_missing_followers: bool = False,
) -> bool:
    if reject_missing_followers and followers is None:
        logger.debug("spam_filter: missing followers author=%s", author_id)
        return False
    if min_followers > 0 and followers is not None and followers < min_followers:
        logger.debug("spam_filter: followers %s < %s author=%s", followers, min_followers, author_id)
        return False
    if redis is None or not author_id:
        return True
    key = f"social:rate:{author_id}"
    try:
        n = int(redis.incr(key))
        if n == 1:
            redis.expire(key, window_sec)
        if n > max_posts_per_window:
            logger.debug("spam_filter: rate limit author=%s n=%s", author_id, n)
            return False
    except Exception as exc:
        logger.debug("spam_filter redis: %s", exc)
    return True
