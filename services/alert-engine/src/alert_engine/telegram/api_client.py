from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

from alert_engine.alerts.formatter import chunk_message, truncate_telegram_text
from alert_engine.config import Settings
from alert_engine.log_safety import safe_chat_ref

logger = logging.getLogger("alert_engine.telegram")


class TelegramApiClient:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._token = settings.telegram_bot_token.strip()

    def _base(self) -> str:
        if not self._token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN missing")
        return f"https://api.telegram.org/bot{self._token}/"

    def send_message(
        self,
        chat_id: int,
        text: str,
        *,
        reply_to_message_id: int | None = None,
    ) -> dict[str, Any]:
        safe = truncate_telegram_text(text, self._s.telegram_message_safe_len)
        chunks = chunk_message(safe, self._s.telegram_message_safe_len)
        if self._s.telegram_dry_run:
            for part in chunks:
                logger.info("SIMULATED SEND chat=%s len=%s", safe_chat_ref(chat_id), len(part))
            return {"ok": True, "dry_run": True, "result": {"message_id": None}}
        if not self._token:
            return {"ok": False, "error": "no_token"}

        last: dict[str, Any] = {}
        parse_mode = self._s.telegram_parse_mode.strip().lower()
        for i, part in enumerate(chunks):
            body: dict[str, Any] = {"chat_id": chat_id, "text": part}
            if parse_mode not in ("", "none", "plain"):
                body["parse_mode"] = parse_mode
            if i == 0 and reply_to_message_id is not None:
                body["reply_to_message_id"] = int(reply_to_message_id)
            last = self._post_json("sendMessage", body, attempt=0)
            if not last.get("ok"):
                break
            if i < len(chunks) - 1:
                time.sleep(max(0.05, 1.0 / self._s.telegram_send_max_per_sec))
        return last

    def _post_json(self, method: str, body: dict[str, Any], attempt: int) -> dict[str, Any]:
        url = f"{self._base()}{method}"
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        max_r = self._s.telegram_send_max_retries
        backoff = 0.5
        for tries in range(max_r + 1):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read().decode("utf-8")
                    return json.loads(raw)
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")[:500]
                if e.code in (429, 500, 502, 503) and tries < max_r:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                logger.warning("telegram HTTPError code=%s body_len=%s", e.code, len(err_body))
                return {"ok": False, "error": f"http_{e.code}"}
            except OSError as exc:
                if tries < max_r:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                logger.warning("telegram network error: %s", exc)
                return {"ok": False, "error": str(exc)[:200]}
        return {"ok": False, "error": "exhausted_retries"}

    def get_updates(
        self,
        offset: int | None,
        timeout_sec: int,
        allowed_updates: list[str],
    ) -> dict[str, Any]:
        if not self._token:
            return {"ok": True, "result": []}
        body: dict[str, Any] = {
            "timeout": min(50, max(1, timeout_sec)),
            "allowed_updates": allowed_updates,
        }
        if offset is not None:
            body["offset"] = offset
        return self._post_json("getUpdates", body, attempt=0)
