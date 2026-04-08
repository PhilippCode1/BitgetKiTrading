from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from alert_engine.config import get_settings
from alert_engine.storage.repo_outbox import RepoOutbox

router = APIRouter(tags=["outbox"])


@router.get("/outbox/recent")
def outbox_recent(limit: Annotated[int, Query(ge=1, le=200)] = 50) -> dict[str, Any]:
    settings = get_settings()
    rows = RepoOutbox(settings.database_url).list_recent(limit)
    return {"items": rows, "limit": limit}
