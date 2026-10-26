"""FastAPI dependencies: one database connection per request, and the repository on top.
Tests replace get_repository / get_recommender with fakes (no database needed)."""

from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, Query

from pricewatch.api.config import ApiSettings, get_api_settings
from pricewatch.api.repository import Repository


def get_connection(
    settings: Annotated[ApiSettings, Depends(get_api_settings)],
) -> Iterator[psycopg.Connection]:
    with psycopg.connect(settings.database_url, connect_timeout=5) as conn:
        yield conn


def get_repository(conn: Annotated[psycopg.Connection, Depends(get_connection)]) -> Repository:
    return Repository(conn)


def get_recommender(conn: Annotated[psycopg.Connection, Depends(get_connection)]):
    from pricewatch.recommender.job import run_recommendations

    return lambda: run_recommendations(conn)


class Paging:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
        page_size: Annotated[int, Query(ge=1, le=100, description="rows per page, max 100")] = 20,
    ):
        self.page = page
        self.page_size = page_size
