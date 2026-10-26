import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from psycopg.types.json import Jsonb

WIB = ZoneInfo("Asia/Jakarta")

HASHED_FIELDS = (
    "external_product_id",
    "name",
    "price_text",
    "original_price_text",
    "discount_text",
    "source_discounted_percentage",
)


def payload_hash(payload: dict[str, Any]) -> str:
    business = {key: payload.get(key) for key in HASHED_FIELDS}
    canonical = json.dumps(business, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def wib_date(ts: datetime) -> date:
    return ts.astimezone(WIB).date()


@dataclass
class ListingRow:
    run_id: str
    platform: str
    crawled_at: datetime
    crawler_version: str
    data_origin: str
    payload: dict[str, Any]
    page_html_hash: str | None
    is_valid: bool
    validation: dict[str, list[str]]

    def as_params(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "platform": self.platform,
            "external_product_id": self.payload.get("external_product_id") or "<missing>",
            "source_url": self.payload.get("source_url"),
            "crawled_at": self.crawled_at,
            "crawl_date": wib_date(self.crawled_at),
            "crawler_version": self.crawler_version,
            "data_origin": self.data_origin,
            "payload": Jsonb(self.payload),
            "payload_hash": payload_hash(self.payload),
            "page_html_hash": self.page_html_hash,
            "is_valid": self.is_valid,
            "validation_errors": Jsonb(self.validation),
        }


INSERT_RUN = """
INSERT INTO raw.crawl_run (run_id, platform, crawler_version, data_origin, started_at, status)
VALUES (%(run_id)s, %(platform)s, %(crawler_version)s, %(data_origin)s, %(started_at)s, 'running')
ON CONFLICT (run_id) DO NOTHING
"""

FINISH_RUN = """
UPDATE raw.crawl_run
SET finished_at = %(finished_at)s, status = %(status)s, pages_fetched = %(pages_fetched)s,
    items_seen = %(items_seen)s, items_valid = %(items_valid)s,
    items_invalid = %(items_invalid)s, parse_success_rate = %(parse_success_rate)s,
    strategy_used = %(strategy_used)s, error_message = %(error_message)s
WHERE run_id = %(run_id)s
"""

INSERT_LISTING = """
INSERT INTO raw.product_listing (
    run_id, platform, external_product_id, source_url, crawled_at, crawl_date,
    crawler_version, data_origin, payload, payload_hash, page_html_hash,
    is_valid, validation_errors
) VALUES (
    %(run_id)s, %(platform)s, %(external_product_id)s, %(source_url)s, %(crawled_at)s,
    %(crawl_date)s, %(crawler_version)s, %(data_origin)s, %(payload)s, %(payload_hash)s,
    %(page_html_hash)s, %(is_valid)s, %(validation_errors)s
)
ON CONFLICT (platform, external_product_id, crawl_date, payload_hash) DO NOTHING
"""


def start_run(conn: psycopg.Connection, **run: Any) -> None:
    conn.execute(INSERT_RUN, run)


def finish_run(conn: psycopg.Connection, **stats: Any) -> None:
    if isinstance(stats.get("finished_at"), str):
        stats["finished_at"] = datetime.fromisoformat(stats["finished_at"])
    conn.execute(FINISH_RUN, stats)


def insert_listings(conn: psycopg.Connection, rows: list[ListingRow]) -> int:
    inserted = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(INSERT_LISTING, row.as_params())
            inserted += cur.rowcount
    return inserted
