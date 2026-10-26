"""Synthetic, deterministic sample dataset .

Why: live history is a few days of one platform, but the analysis needs several weeks
on three platforms. Everything here is generated from the hand-written catalog with
seed=42 and is labelled data_origin='sample' all the way to the dashboard.

Patterns put in on purpose (so the analysis has something to find, and so a reader can
check the method recovers them). They are assumptions, not facts:
- price level per platform: tokopedia 1.00, klikindomaret 1.03, blibli 0.98 (+-2% per SKU);
- klikindomaret promos start on Fridays and last the weekend;
- blibli runs more and deeper promos around payday (25th to the 3rd);
- 9.9 and 10.10 are big sale days on tokopedia and blibli;
- ~30% of SKUs get one +4% list-price increase;
- a few broken / suspicious records and non-Unilever products, to exercise quarantine.
"""

import json
import random
import re
import uuid
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pricewatch.crawler import loader
from pricewatch.crawler.models import validate_payload
from pricewatch.logging import get_logger
from pricewatch.sample.catalog import CATALOG, NON_UNILEVER, Sku

log = get_logger(__name__)
WIB = ZoneInfo("Asia/Jakarta")
VERSION = "sample-gen-1.0"
NAMESPACE = uuid.UUID("6f1c2d3e-0000-4000-8000-000000000042")
END_DATE = date(2026, 10, 11)  # fixed, so the dataset is identical on every machine
PLATFORM_LEVEL = {"tokopedia": 1.00, "klikindomaret": 1.03, "blibli": 0.98}
CRAWL_TIMES = {  # local (WIB) crawl times per day
    "tokopedia": [time(8, 5), time(20, 5)],
    "klikindomaret": [time(9, 0)],
    "blibli": [time(7, 30), time(19, 30)],
}
BIG_SALE_DAYS = {date(2026, 9, 9), date(2026, 10, 10)}


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def rupiah(amount: int, platform: str) -> str:
    formatted = f"{amount:,}".replace(",", ".")
    return f"Rp {formatted}" if platform == "klikindomaret" else f"Rp{formatted}"


def listing_name(sku: Sku, platform: str) -> str:
    v, u = sku.size_value, sku.size_unit
    if platform == "tokopedia":
        size = f"{v / 1000:g}{'kg' if u == 'g' else 'L'}" if v >= 1000 else f"{v:g}{u}"
        name = f"{sku.brand} {sku.descriptor} {size}"
        return name + (f" isi {sku.pack_qty}" if sku.pack_qty > 1 else "")
    if platform == "klikindomaret":
        size = (
            f"{v / 1000:g}{'KG' if u == 'g' else 'LT'}"
            if v >= 1000
            else f"{v:g}{'GR' if u == 'g' else 'ML'}"
        )
        size = f"{sku.pack_qty}X{size}" if sku.pack_qty > 1 else size
        return f"{sku.brand.upper()} {sku.short.upper()} {size}"
    # blibli: "Brand Descriptor - 1,8 kg [Isi 2]"
    if v >= 1000:
        size = f"{v / 1000:g}".replace(".", ",") + (" kg" if u == "g" else " L")
    else:
        size = f"{v:g} " + ("gr" if u == "g" else "mL")
    name = f"{sku.brand} {sku.descriptor} - {size}"
    return name + (f" [Isi {sku.pack_qty}]" if sku.pack_qty > 1 else "")


def in_payday_window(day: date) -> bool:
    return day.day >= 25 or day.day <= 3


def plan_campaigns(rng: random.Random, platform: str, days: list[date]) -> dict[date, float]:
    """Discount depth per day for one listing (0 = no promo)."""
    depth_by_day: dict[date, float] = {}
    day_index = 0
    while day_index < len(days):
        day = days[day_index]
        start_chance = {"tokopedia": 0.07, "klikindomaret": 0.03, "blibli": 0.06}[platform]
        if platform == "klikindomaret" and day.weekday() == 4:  # Friday
            start_chance = 0.45
        if platform == "blibli" and in_payday_window(day):
            start_chance = 0.20
        if day in BIG_SALE_DAYS and platform != "klikindomaret":
            depth_by_day[day] = rng.choice([0.25, 0.30, 0.35])
            day_index += 1
            continue
        if rng.random() < start_chance:
            if platform == "klikindomaret":
                depth, length = rng.choice([0.05, 0.10, 0.15]), 3  # Fri-Sun
            elif platform == "blibli":
                depth, length = rng.choice([0.10, 0.15, 0.20, 0.25]), rng.randint(2, 4)
            else:
                depth, length = rng.choice([0.05, 0.10, 0.15, 0.20]), rng.randint(1, 3)
            for offset in range(length):
                if day_index + offset < len(days):
                    depth_by_day[days[day_index + offset]] = depth
            day_index += length
        else:
            day_index += 1
    return depth_by_day


def generate(days: int = 56, seed: int = 42) -> tuple[list[dict], list[dict]]:
    rng = random.Random(seed)
    dates = [END_DATE - timedelta(days=days - 1 - i) for i in range(days)]
    listings_by_platform = {}
    for platform in PLATFORM_LEVEL:
        listings = []
        for sku in CATALOG:
            if platform != "tokopedia" and rng.random() < 0.10:
                continue  # not every SKU is sold everywhere
            name = listing_name(sku, platform)
            suffix = uuid.uuid5(NAMESPACE, platform + sku.sku).hex[:6]
            listings.append(
                {
                    "sku": sku,
                    "external_id": f"{slug(name)}-{suffix}",
                    "name": name,
                    "level": PLATFORM_LEVEL[platform] * rng.uniform(0.98, 1.02),
                    "increase_on": dates[rng.randrange(len(dates))]
                    if rng.random() < 0.30
                    else None,
                    "campaigns": plan_campaigns(rng, platform, dates),
                }
            )
        listings_by_platform[platform] = listings
    # One listing changes its name half-way (packaging refresh): exercises SCD2.
    renamed = listings_by_platform["blibli"][0]
    renamed["new_name_from"] = dates[days // 2]

    runs, records = [], []
    for day in dates:
        for platform, listings in listings_by_platform.items():
            for slot, local_time in enumerate(CRAWL_TIMES[platform]):
                crawled_local = datetime.combine(day, local_time, WIB) + timedelta(
                    minutes=rng.randint(0, 20)
                )
                crawled_at = crawled_local.astimezone(UTC)
                run_id = str(uuid.uuid5(NAMESPACE, f"{platform}|{day}|{slot}"))
                run_records = []
                for item in listings:
                    sku = item["sku"]
                    list_price = sku.base_price * item["level"]
                    if item["increase_on"] and day >= item["increase_on"]:
                        list_price *= 1.04
                    list_price = round(list_price / 100) * 100
                    depth = item["campaigns"].get(day, 0)
                    price = round(list_price * (1 - depth) / 100) * 100 if depth else list_price
                    name = item["name"]
                    if item.get("new_name_from") and day >= item["new_name_from"]:
                        name = name.replace(" - ", " Kemasan Baru - ")
                    payload = {
                        "external_product_id": item["external_id"],
                        "source_product_id": None,
                        "name": name,
                        "price_text": rupiah(price, platform),
                        "original_price_text": rupiah(list_price, platform) if depth else None,
                        "discount_text": f"{round(depth * 100)}%"
                        if depth and platform != "tokopedia"
                        else None,
                        # Mimics the live finding: Tokopedia's own field says 0 during promos.
                        "source_discounted_percentage": "0"
                        if depth and platform == "tokopedia"
                        else None,
                        "source_url": f"sample://{platform}/{item['external_id']}",
                        "detail": {"rating": None, "review_count": None, "image_url": None},
                        "strategy": VERSION,
                    }
                    roll = rng.random()
                    if roll < 0.002:
                        payload["price_text"] = ""  # broken: invalid in raw
                    elif roll < 0.004:
                        payload["price_text"] = "Rp -"  # broken: invalid in raw
                    elif roll < 0.005 and depth:
                        payload["original_price_text"], payload["price_text"] = (
                            payload["price_text"],
                            payload["original_price_text"],
                        )  # suspicious
                    run_records.append(payload)
                if platform == "klikindomaret":
                    for name, base in NON_UNILEVER:
                        run_records.append(
                            {
                                "external_product_id": slug(name),
                                "source_product_id": None,
                                "name": name,
                                "price_text": rupiah(base, platform),
                                "original_price_text": None,
                                "discount_text": None,
                                "source_discounted_percentage": None,
                                "source_url": f"sample://{platform}/{slug(name)}",
                                "detail": {"rating": None, "review_count": None, "image_url": None},
                                "strategy": VERSION,
                            }
                        )
                valid = sum(validate_payload(p)[0] for p in run_records)
                runs.append(
                    {
                        "run_id": run_id,
                        "platform": platform,
                        "started_at": crawled_at.isoformat(),
                        "finished_at": (crawled_at + timedelta(minutes=2)).isoformat(),
                        "status": "success",
                        "pages_fetched": 1,
                        "items_seen": len(run_records),
                        "items_valid": valid,
                        "items_invalid": len(run_records) - valid,
                        "parse_success_rate": round(valid / len(run_records), 4),
                        "strategy_used": VERSION,
                        "error_message": None,
                    }
                )
                records.extend(
                    {
                        "run_id": run_id,
                        "platform": platform,
                        "crawled_at": crawled_at.isoformat(),
                        "payload": p,
                    }
                    for p in run_records
                )
    return runs, records


def write_sample(out_dir: Path, days: int = 56, seed: int = 42) -> dict[str, int]:
    runs, records = generate(days, seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("crawl_runs.jsonl", runs), ("product_listings.jsonl", records)):
        with open(out_dir / name, "w", encoding="utf-8", newline="\n") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return {"runs": len(runs), "records": len(records)}


def _read_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def load_sample(conn, sample_dir: Path) -> dict[str, int]:
    """Load sample_data/ into raw through the same loader as live data. Idempotent."""
    sample_dir = Path(sample_dir)
    runs = list(_read_jsonl(sample_dir / "crawl_runs.jsonl"))
    by_run: dict[str, list[dict]] = {}
    for record in _read_jsonl(sample_dir / "product_listings.jsonl"):
        by_run.setdefault(record["run_id"], []).append(record)
    inserted = 0
    for run in runs:
        started_at = datetime.fromisoformat(run["started_at"])
        loader.start_run(
            conn,
            run_id=run["run_id"],
            platform=run["platform"],
            crawler_version=VERSION,
            data_origin="sample",
            started_at=started_at,
        )
        rows = []
        for record in by_run.get(run["run_id"], []):
            is_valid, validation = validate_payload(record["payload"])
            rows.append(
                loader.ListingRow(
                    run["run_id"],
                    run["platform"],
                    datetime.fromisoformat(record["crawled_at"]),
                    VERSION,
                    "sample",
                    record["payload"],
                    None,
                    is_valid,
                    validation,
                )
            )
        inserted += loader.insert_listings(conn, rows)
        loader.finish_run(
            conn,
            **{
                k: run[k]
                for k in (
                    "run_id",
                    "finished_at",
                    "status",
                    "pages_fetched",
                    "items_seen",
                    "items_valid",
                    "items_invalid",
                    "parse_success_rate",
                    "strategy_used",
                    "error_message",
                )
            },
        )
        conn.commit()
    log.info("sample_loaded", runs=len(runs), rows_inserted=inserted)
    return {"runs": len(runs), "rows_inserted": inserted}
