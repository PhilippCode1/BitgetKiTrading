from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SocialIncomingMessage:
    """Normalisierte Roh-Nachricht aus X-Stream oder Telegram."""

    source: str  # "x" | "telegram"
    text: str
    author_id: str
    external_id: str
    followers: int | None = None
