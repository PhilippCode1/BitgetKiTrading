from __future__ import annotations

import psycopg
from psycopg.rows import dict_row


def db_connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(dsn, row_factory=dict_row)
