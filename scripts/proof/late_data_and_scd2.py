"""P5 (late data reaches gold) and P9 (SCD2 history), on a throw-away database.

Builds pricewatch_proof from empty (schemas, raw tables, sample data, dbt build), then:
- P5: loads an observation for an OLD date now, runs the incremental model, and checks the
  fact row for that day changed (the watermark is inserted_at, not the crawl date);
- P9: loads a renamed listing on a later day, runs dbt build, and checks the snapshot now
  holds two versions of that listing (old one closed with dbt_valid_to).

docker compose run --rm dev python scripts/proof/late_data_and_scd2.py
"""

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pricewatch.crawler import loader  # noqa: E402
from pricewatch.crawler.models import validate_payload  # noqa: E402
from pricewatch.sample.generate import load_sample  # noqa: E402
from pricewatch.settings import get_settings  # noqa: E402

DB = "pricewatch_proof"
WIB = ZoneInfo("Asia/Jakarta")


def dbt(*args: str) -> None:
    print("$ dbt", " ".join(args))
    env = {**os.environ, "POSTGRES_DB": DB}
    subprocess.run(
        ["dbt", *args, "--quiet", "--target-path", "target_proof"],
        cwd=ROOT / "dbt",
        env=env,
        check=True,
    )


def add_observation(conn, listing: dict, crawled_at: datetime, **changes) -> None:
    run_id = str(uuid.uuid4())
    payload = {**listing["payload"], **changes}
    loader.start_run(
        conn,
        run_id=run_id,
        platform=listing["platform"],
        crawler_version="proof",
        data_origin="sample",
        started_at=crawled_at,
    )
    is_valid, validation = validate_payload(payload)
    loader.insert_listings(
        conn,
        [
            loader.ListingRow(
                run_id,
                listing["platform"],
                crawled_at,
                "proof",
                "sample",
                payload,
                None,
                is_valid,
                validation,
            )
        ],
    )
    loader.finish_run(
        conn,
        run_id=run_id,
        finished_at=crawled_at,
        status="success",
        pages_fetched=1,
        items_seen=1,
        items_valid=1,
        items_invalid=0,
        parse_success_rate=1,
        strategy_used="proof",
        error_message=None,
    )
    conn.commit()


def main() -> None:
    settings = get_settings()
    admin_url = settings.database_url().rsplit("/", 1)[0] + "/postgres"
    proof_url = settings.database_url().rsplit("/", 1)[0] + f"/{DB}"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f"drop database if exists {DB} with (force)")
        admin.execute(f"create database {DB}")

    with psycopg.connect(proof_url) as conn:
        for schema in ("raw", "silver", "gold", "snapshots"):
            conn.execute(f"create schema {schema}")
        for name in ("002_raw_tables.sql", "003_gold_recommendation.sql"):
            conn.execute((ROOT / "db" / "init" / name).read_text(encoding="utf-8"))
        conn.commit()
        print("sample loaded:", load_sample(conn, settings.sample_dir))
    dbt("build", "--exclude", "resource_type:test", "resource_type:unit_test")

    with psycopg.connect(proof_url) as conn:
        row = conn.execute("""
            select f.listing_key, f.platform, f.price_date, f.price, f.n_observations, p.payload
            from gold.fct_product_price_daily f
            join raw.product_listing p on p.platform || ':' || p.external_product_id = f.listing_key
                                      and p.crawl_date = f.price_date
            where f.data_origin = 'sample' and f.platform = 'blibli'
            order by f.price_date, f.listing_key limit 1""").fetchone()
        listing_key, platform, old_date, old_price, old_n, payload = row
        listing = {"platform": platform, "payload": payload}
        print(
            f"\nP5 target: {listing_key} on {old_date}: price {old_price}, {old_n} observation(s)"
        )
        late_price = int(old_price) - 500
        add_observation(
            conn,
            listing,
            datetime.combine(old_date, datetime.max.time(), WIB)
            .replace(hour=23, minute=0, microsecond=0)
            .astimezone(UTC),
            price_text=f"Rp{late_price:,}".replace(",", "."),
        )
        print(
            f"loaded now (inserted_at = {datetime.now(UTC):%Y-%m-%d %H:%M}) an observation "
            f"crawled on {old_date} 23:00 WIB at Rp{late_price}"
        )

    # silver tables are rebuilt, then the fact runs incrementally (its table already exists)
    dbt("run", "--select", "+fct_product_price_daily")

    with psycopg.connect(proof_url) as conn:
        new_price, new_n = conn.execute(
            "select price, n_observations from gold.fct_product_price_daily "
            "where listing_key = %s and price_date = %s",
            (listing_key, old_date),
        ).fetchone()
        print(f"after incremental run: price {new_price}, {new_n} observation(s)")
        p5 = int(new_price) == late_price and new_n == old_n + 1
        print("P5 RESULT:", "late row reached gold" if p5 else "FAILED")

        # P9: rename the same listing on a later day
        versions_before = conn.execute(
            "select count(*) from snapshots.snap_listing_attributes where listing_key = %s",
            (listing_key,),
        ).fetchone()[0]
        last_seen = conn.execute(
            "select max(crawled_at) from raw.product_listing "
            "where platform || ':' || external_product_id = %s",
            (listing_key,),
        ).fetchone()[0]
        new_name = payload["name"] + " (Kemasan Baru)"
        add_observation(
            conn, listing, last_seen.replace(day=min(last_seen.day + 1, 28)), name=new_name
        )
        print(f"\nP9: snapshot versions of {listing_key} before rename: {versions_before}")

    dbt("build", "--exclude", "resource_type:test", "resource_type:unit_test")

    with psycopg.connect(proof_url) as conn:
        versions = conn.execute(
            "select listing_name, dbt_valid_from, dbt_valid_to "
            "from snapshots.snap_listing_attributes "
            "where listing_key = %s order by dbt_valid_from",
            (listing_key,),
        ).fetchall()
        for name, valid_from, valid_to in versions:
            print(
                f"  {name[:60]:<60} valid_from={valid_from:%Y-%m-%d %H:%M} "
                f"valid_to={valid_to:%Y-%m-%d %H:%M}"
                if valid_to
                else f"  {name[:60]:<60} valid_from={valid_from:%Y-%m-%d %H:%M} "
                "valid_to=null (current)"
            )
        p9 = len(versions) == 2 and versions[0][2] is not None and versions[1][2] is None
        print("P9 RESULT:", "old version closed, new version current" if p9 else "FAILED")

    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(f"drop database {DB} with (force)")
    sys.exit(0 if p5 and p9 else 1)


if __name__ == "__main__":
    main()
