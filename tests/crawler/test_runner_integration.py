from datetime import UTC, datetime

import psycopg
import pytest

from pricewatch.crawler.fetch import BlockedError, FetchResult
from pricewatch.crawler.runner import crawl_platform, load_landing
from pricewatch.settings import CrawlerConfig, get_settings

from ..conftest import ROOT

pytestmark = pytest.mark.integration


@pytest.fixture
def conn():
    settings = get_settings()
    admin_url = settings.database_url().rsplit("/", 1)[0] + "/postgres"
    try:
        admin = psycopg.connect(admin_url, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError:
        pytest.skip("Postgres is not running")
    admin.execute("DROP DATABASE IF EXISTS pricewatch_test WITH (FORCE)")
    admin.execute("CREATE DATABASE pricewatch_test")
    test_url = settings.database_url().rsplit("/", 1)[0] + "/pricewatch_test"
    with psycopg.connect(test_url) as c:
        c.execute("CREATE SCHEMA raw")
        c.execute((ROOT / "db" / "init" / "002_raw_tables.sql").read_text(encoding="utf-8"))
        c.commit()
        yield c
    admin.execute("DROP DATABASE IF EXISTS pricewatch_test WITH (FORCE)")
    admin.close()


class FakeClient:
    user_agent = "pricewatch-test/0.1"

    def __init__(self, pages):
        self.pages = pages

    def is_allowed(self, url, strict=True):
        return True

    def get(self, url):
        page = self.pages[url]
        if isinstance(page, Exception):
            raise page
        return FetchResult(url, page.encode("utf-8"), datetime.now(UTC))


CFG = CrawlerConfig(user_agent="pricewatch-test/0.1", max_pages=3)


def platform_cfg(selectors):
    return {**selectors["tokopedia"], "min_items_expected": 2}


def count(conn, sql):
    return conn.execute(sql).fetchone()[0]


def test_running_the_same_crawl_twice_adds_no_duplicate_rows(conn, selectors, shop_html, tmp_path):
    client = FakeClient({selectors["tokopedia"]["page_urls"]["first"]: shop_html})
    first = crawl_platform(conn, "tokopedia", platform_cfg(selectors), CFG, client, tmp_path)
    second = crawl_platform(conn, "tokopedia", platform_cfg(selectors), CFG, client, tmp_path)
    assert first.stats.items_inserted == 3
    assert second.stats.items_inserted == 0
    assert count(conn, "SELECT count(*) FROM raw.product_listing") == 3
    assert count(conn, "SELECT count(*) FROM raw.crawl_run WHERE status = 'success'") == 2


def test_page_without_products_ends_the_run_as_failed(conn, selectors, tmp_path):
    client = FakeClient({selectors["tokopedia"]["page_urls"]["first"]: "<html>down</html>"})
    result = crawl_platform(conn, "tokopedia", platform_cfg(selectors), CFG, client, tmp_path)
    assert result.status == "failed"
    assert count(conn, "SELECT count(*) FROM raw.product_listing") == 0


def test_blocked_site_ends_the_run_as_blocked_with_the_reason(conn, selectors, tmp_path):
    client = FakeClient({selectors["tokopedia"]["page_urls"]["first"]: BlockedError("HTTP 403")})
    result = crawl_platform(conn, "tokopedia", platform_cfg(selectors), CFG, client, tmp_path)
    assert result.status == "blocked"
    row = conn.execute("SELECT status, error_message FROM raw.crawl_run").fetchone()
    assert row == ("blocked", "blocked: HTTP 403")


def test_invalid_record_is_kept_in_raw_with_its_errors(conn, selectors, shop_html, tmp_path):
    broken = shop_html.replace('"text_idr":"Rp42.500"', '"text_idr":""')
    client = FakeClient({selectors["tokopedia"]["page_urls"]["first"]: broken})
    result = crawl_platform(conn, "tokopedia", platform_cfg(selectors), CFG, client, tmp_path)
    assert result.stats.items_seen == 3 and result.stats.items_valid == 2
    errors = conn.execute(
        "SELECT validation_errors->'errors' FROM raw.product_listing WHERE NOT is_valid"
    ).fetchone()[0]
    assert errors and errors[0].startswith("price_text")


def test_landed_pages_can_be_reloaded_after_the_database_is_lost(
    conn, selectors, shop_html, tmp_path
):
    client = FakeClient({selectors["tokopedia"]["page_urls"]["first"]: shop_html})
    crawl_platform(conn, "tokopedia", platform_cfg(selectors), CFG, client, tmp_path)
    conn.execute("TRUNCATE raw.product_listing, raw.crawl_run")
    conn.commit()
    totals = load_landing(conn, {"tokopedia": platform_cfg(selectors)}, tmp_path)
    again = load_landing(conn, {"tokopedia": platform_cfg(selectors)}, tmp_path)
    assert totals["rows_inserted"] == 3 and again["rows_inserted"] == 0
    assert count(conn, "SELECT count(*) FROM raw.crawl_run WHERE status = 'success'") == 1
