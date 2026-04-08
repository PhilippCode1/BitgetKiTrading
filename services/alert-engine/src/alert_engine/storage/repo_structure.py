from __future__ import annotations


import psycopg


class RepoStructureTrend:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def get_last_trend(self, symbol: str, timeframe: str) -> str | None:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(
                """
                SELECT last_trend_dir FROM alert.structure_trend_state
                WHERE symbol = %s AND timeframe = %s
                """,
                (symbol.upper(), timeframe),
            ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def set_trend(self, symbol: str, timeframe: str, trend_dir: str, ts_ms: int) -> None:
        with psycopg.connect(self._dsn) as conn:
            conn.execute(
                """
                INSERT INTO alert.structure_trend_state (symbol, timeframe, last_trend_dir, updated_ts_ms)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (symbol, timeframe) DO UPDATE SET
                  last_trend_dir = EXCLUDED.last_trend_dir,
                  updated_ts_ms = EXCLUDED.updated_ts_ms
                """,
                (symbol.upper(), timeframe, trend_dir, ts_ms),
            )
            conn.commit()
