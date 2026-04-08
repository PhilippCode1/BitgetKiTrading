from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row


@contextmanager
def db_conn(dsn: str) -> Generator[psycopg.Connection[Any], None, None]:
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10) as conn:
        yield conn
