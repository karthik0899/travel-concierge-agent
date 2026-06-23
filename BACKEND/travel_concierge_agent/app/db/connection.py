"""The single data doorway.

Every tool reads/writes the world through these helpers — one connection pool,
dict rows, transaction-per-call. Keeping all DB access here is what guarantees
the agents see consistent data (the whole point of a shared tool layer).

Env (.env supported):
    DATABASE_URL=postgresql://user:pass@host:5432/dbname
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

load_dotenv()

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL is not set (see .env.example).")
        _pool = ConnectionPool(dsn, min_size=1, max_size=10, open=True,
                               kwargs={"row_factory": dict_row})
    return _pool


def close_pool() -> None:
    """Close the pool (call on app shutdown to avoid finalizer warnings)."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def cursor():
    """A cursor in its own transaction — commits on success, rolls back on error."""
    with pool().connection() as conn:      # commits/rolls back at block exit
        with conn.cursor() as cur:
            yield cur


def query(sql: str, params: dict | tuple | None = None) -> list[dict[str, Any]]:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def query_one(sql: str, params: dict | tuple | None = None) -> dict[str, Any] | None:
    with cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: dict | tuple | None = None) -> list[dict[str, Any]] | None:
    """For writes. Returns rows if the statement has RETURNING, else None."""
    with cursor() as cur:
        cur.execute(sql, params)
        if cur.description is not None:
            return cur.fetchall()
        return None
