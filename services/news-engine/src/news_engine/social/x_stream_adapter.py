from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx

from news_engine.social.types import SocialIncomingMessage

logger = logging.getLogger("news_engine.social.x_stream")

RULES_URL = "https://api.twitter.com/2/tweets/search/stream/rules"
STREAM_URL = "https://api.twitter.com/2/tweets/search/stream"


class XStreamAdapter:
    """Twitter API v2 Filtered Stream — Bearer-only; Rules optional ersetzbar."""

    def __init__(
        self,
        *,
        bearer_token: str,
        rule_value: str,
        replace_rules_on_start: bool,
    ) -> None:
        self._bearer = bearer_token.strip()
        self._rule = rule_value.strip()
        self._replace = replace_rules_on_start

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._bearer}"}

    async def _sync_rules(self, client: httpx.AsyncClient) -> None:
        r = await client.get(RULES_URL, headers=self._headers())
        r.raise_for_status()
        body = r.json()
        existing = body.get("data") or []
        ids = [str(x.get("id")) for x in existing if isinstance(x, dict) and x.get("id")]
        if self._replace and ids:
            del_body = {"delete": {"ids": ids}}
            dr = await client.post(RULES_URL, headers=self._headers(), json=del_body)
            dr.raise_for_status()
            logger.info("XStreamAdapter: %s alte Rules geloescht", len(ids))
        elif not self._replace and existing:
            for row in existing:
                if isinstance(row, dict) and str(row.get("value", "")).strip() == self._rule:
                    logger.info("XStreamAdapter: Rule bereits aktiv id=%s", row.get("id"))
                    return
        add_body = {"add": [{"value": self._rule, "tag": "apex_social"}]}
        ar = await client.post(RULES_URL, headers=self._headers(), json=add_body)
        if ar.status_code == 400:
            logger.warning("XStreamAdapter: Rule add HTTP 400 body=%s", ar.text[:500])
        ar.raise_for_status()

    async def run(self, queue: asyncio.Queue[SocialIncomingMessage], stop: asyncio.Event) -> None:
        params = {
            "tweet.fields": "lang,public_metrics",
            "expansions": "author_id",
            "user.fields": "public_metrics,username",
        }
        buf = ""
        backoff = 1.0
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=None)) as client:
            while not stop.is_set():
                try:
                    await self._sync_rules(client)
                    async with client.stream(
                        "GET",
                        STREAM_URL,
                        headers=self._headers(),
                        params=params,
                    ) as resp:
                        if resp.status_code != 200:
                            txt = (await resp.aread())[:800].decode(errors="ignore")
                            logger.error("X stream HTTP %s: %s", resp.status_code, txt)
                            await asyncio.sleep(min(60.0, backoff))
                            backoff = min(60.0, backoff * 1.7)
                            continue
                        backoff = 1.0
                        async for chunk in resp.aiter_bytes():
                            if stop.is_set():
                                break
                            buf += chunk.decode("utf-8", errors="ignore")
                            while "\n" in buf:
                                line, buf = buf.split("\n", 1)
                                line = line.strip()
                                if not line or line.startswith(":"):
                                    continue
                                try:
                                    payload = json.loads(line)
                                except json.JSONDecodeError:
                                    continue
                                await self._dispatch_payload(queue, payload)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.exception("XStreamAdapter Schleife: %s", exc)
                    await asyncio.sleep(min(30.0, backoff))
                    backoff = min(60.0, backoff * 1.5)

    async def _dispatch_payload(
        self,
        queue: asyncio.Queue[SocialIncomingMessage],
        payload: dict[str, Any],
    ) -> None:
        data = payload.get("data")
        tweets: list[dict[str, Any]] = []
        if isinstance(data, dict):
            tweets = [data]
        elif isinstance(data, list):
            tweets = [x for x in data if isinstance(x, dict)]
        includes = payload.get("includes") or {}
        users_raw = includes.get("users") if isinstance(includes, dict) else None
        users: dict[str, dict[str, Any]] = {}
        if isinstance(users_raw, list):
            for u in users_raw:
                if isinstance(u, dict) and u.get("id"):
                    users[str(u["id"])] = u
        for tw in tweets:
            tid = str(tw.get("id") or "")
            text = str(tw.get("text") or "").strip()
            aid = str(tw.get("author_id") or tid or "unknown")
            followers: int | None = None
            u = users.get(aid)
            if isinstance(u, dict):
                pm = u.get("public_metrics")
                if isinstance(pm, dict) and pm.get("followers_count") is not None:
                    try:
                        followers = int(pm["followers_count"])
                    except (TypeError, ValueError):
                        followers = None
            if not text:
                continue
            await queue.put(
                SocialIncomingMessage(
                    source="x",
                    text=text,
                    author_id=aid,
                    external_id=tid or text[:32],
                    followers=followers,
                )
            )
