from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("news_engine.social.reference")


def load_reference_bundle(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        for base in Path(__file__).resolve().parents:
            cand = base / "shared" / "contracts" / "data" / "social_sentiment_reference_v1.json"
            if cand.is_file():
                p = cand
                break
    if not p.is_file():
        raise FileNotFoundError(f"social reference json nicht gefunden: {path}")
    return json.loads(p.read_text(encoding="utf-8"))
