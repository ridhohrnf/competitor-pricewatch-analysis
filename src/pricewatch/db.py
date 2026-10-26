import time

import psycopg

from pricewatch.logging import get_logger
from pricewatch.settings import get_settings

log = get_logger(__name__)


def connect(url: str | None = None, autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(url or get_settings().database_url(), autocommit=autocommit)


def wait_for_db(url: str | None = None, timeout_seconds: int = 60) -> None:
    """Block until Postgres accepts connections (containers can start in any order)."""
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with connect(url) as conn:
                conn.execute("SELECT 1")
            return
        except psycopg.OperationalError:
            if time.monotonic() > deadline:
                raise
            log.info("db_not_ready_yet")
            time.sleep(2)
