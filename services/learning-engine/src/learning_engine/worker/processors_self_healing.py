from __future__ import annotations

import logging

from shared_py.eventbus import EventEnvelope

from learning_engine.config import LearningEngineSettings
from learning_engine.self_healing.code_fix_agent import run_self_healing_for_system_alert
from learning_engine.storage.connection import db_connect
from learning_engine.storage.repo_processed import mark_processed

logger = logging.getLogger("learning_engine.processor.self_healing")


def process_self_healing_system_alert(
    settings: LearningEngineSettings,
    env: EventEnvelope,
    *,
    stream: str,
    redis_message_id: str,
) -> None:
    try:
        run_self_healing_for_system_alert(settings, env)
    except Exception:
        logger.exception("self_healing failed stream=%s id=%s", stream, redis_message_id)
    with db_connect(settings.database_url) as conn:
        with conn.transaction():
            mark_processed(conn, stream, redis_message_id)
