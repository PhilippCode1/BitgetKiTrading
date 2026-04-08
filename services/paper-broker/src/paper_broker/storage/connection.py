from __future__ import annotations

import psycopg
from psycopg.rows import dict_row


def paper_connect(dsn: str, *, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(dsn, autocommit=autocommit, row_factory=dict_row)
