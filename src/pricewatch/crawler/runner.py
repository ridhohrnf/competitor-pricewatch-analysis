import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import psycopg

from pricewatch import __version__
from pricewatch.crawler import loader
from pricewatch.crawler.extract import extract
from pricewatch.crawler.fetch import BlockedError, CrawlError, PoliteClient
from pricewatch.crawler.health import RunStats, alert_if_unhealthy, run_status
from pricewatch.crawler.landing import LandingWriter, RunManifest, iter_manifests
from pricewatch.crawler.models import validate_payload
from pricewatch.logging import bind_run_context, get_logger
from pricewatch.settings import CrawlerConfig

log = get_logger(__name__)


@dataclass
class Page:
    number: int
    url: str
    content: bytes
    fetched_at: datetime


def page_url(platform_cfg: dict[str, Any], number: int) -> str:
    urls = platform_cfg["page_urls"]
    return urls["first"] if number == 1 else urls["next"].format(page=number)


def fetch_pages(
    platform_cfg: dict[str, Any], client: PoliteClient, max_pages: int
) -> Iterator[Page]:
    for number in range(1, max_pages + 1):
        result = client.get(page_url(platform_cfg, number))
        yield Page(number, result.url, result.content, result.fetched_at)


@dataclass
class RunResult:
    run_id: str
    platform: str
    status: str
    stats: RunStats
    error_message: str | None = None


def build_rows(
    page: Page,
    platform_cfg: dict[str, Any],
    platform: str,
    run_id: str,
    crawler_version: str,
    data_origin: str,
    page_hash: str | None,
) -> tuple[list[loader.ListingRow], str]:
    html = page.content.decode("utf-8", errors="replace")
    payloads, strategy = extract(html, platform_cfg["strategies"], page.url)
    rows = []
    for payload in payloads:
        try:
            is_valid, validation = validate_payload(payload)
        except Exception as exc:
            is_valid, validation = False, {"errors": [f"validator_crashed: {exc}"], "warnings": []}
        if not is_valid:
            log.warning(
                "item_invalid",
                product_id=payload.get("external_product_id"),
                errors=validation["errors"],
            )
        rows.append(
            loader.ListingRow(
                run_id,
                platform,
                page.fetched_at,
                crawler_version,
                data_origin,
                payload,
                page_hash,
                is_valid,
                validation,
            )
        )
    return rows, strategy


def recent_live_run(conn: psycopg.Connection, platform: str, hours: float) -> datetime | None:
    row = conn.execute(
        """SELECT max(started_at) FROM raw.crawl_run
           WHERE platform = %s AND data_origin = 'live' AND status <> 'running'
             AND started_at > now() - make_interval(secs => %s)""",
        (platform, hours * 3600),
    ).fetchone()
    return row[0] if row else None


def crawl_platform(
    conn: psycopg.Connection,
    platform: str,
    platform_cfg: dict[str, Any],
    crawler_cfg: CrawlerConfig,
    client: PoliteClient,
    landing_dir: Path,
    alert_webhook_url: str | None = None,
) -> RunResult:
    run_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)
    bind_run_context(run_id=run_id, platform=platform)
    log.info("crawl_run_started", crawler_version=__version__)
    loader.start_run(
        conn,
        run_id=run_id,
        platform=platform,
        crawler_version=__version__,
        data_origin="live",
        started_at=started_at,
    )
    conn.commit()

    landing = LandingWriter(
        landing_dir,
        platform,
        loader.wib_date(started_at).isoformat(),
        RunManifest(run_id, platform, __version__, started_at.isoformat()),
    )
    stats = RunStats()
    strategies_used: list[str] = []
    seen_ids: set[str] = set()
    blocked, error_message = False, None
    max_pages = min(crawler_cfg.max_pages, platform_cfg.get("max_pages", crawler_cfg.max_pages))

    try:
        for page in fetch_pages(platform_cfg, client, max_pages):
            landed = landing.save_page(page.number, page.url, page.content, page.fetched_at)
            rows, strategy = build_rows(
                page, platform_cfg, platform, run_id, __version__, "live", landed.html_sha256
            )
            stats.pages_fetched += 1
            if strategy not in strategies_used:
                strategies_used.append(strategy)
            ids = {r.payload.get("external_product_id") for r in rows}
            new_ids = ids - seen_ids
            seen_ids |= ids
            stats.items_seen += len(new_ids)
            stats.items_valid += sum(
                1 for r in rows if r.is_valid and r.payload.get("external_product_id") in new_ids
            )
            stats.items_inserted += loader.insert_listings(conn, rows)
            conn.commit()
            log.info(
                "page_parsed",
                page=page.number,
                strategy=strategy,
                items=len(rows),
                new_items=len(new_ids),
            )
            if not rows or len(rows) < platform_cfg["page_size"] or not new_ids:
                break
    except BlockedError as exc:
        blocked, error_message = True, f"blocked: {exc}"
        log.error("crawl_blocked", reason=str(exc))
    except CrawlError as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        log.error("crawl_failed", error=error_message)
    except Exception as exc:
        conn.rollback()
        error_message = f"{type(exc).__name__}: {exc}"
        log.exception("crawl_crashed")

    status = run_status(
        stats,
        crawler_cfg.health.parse_success_rate_threshold,
        platform_cfg["min_items_expected"],
        blocked,
    )
    result = {
        "run_id": run_id,
        "finished_at": datetime.now(UTC).isoformat(),
        "status": status,
        "pages_fetched": stats.pages_fetched,
        "items_seen": stats.items_seen,
        "items_valid": stats.items_valid,
        "items_invalid": stats.items_invalid,
        "parse_success_rate": stats.parse_success_rate,
        "strategy_used": ",".join(strategies_used) or None,
        "error_message": error_message,
    }
    loader.finish_run(conn, **result)
    conn.commit()
    landing.finalize(result)
    log.info(
        "crawl_run_finished",
        status=status,
        pages=stats.pages_fetched,
        items_seen=stats.items_seen,
        items_valid=stats.items_valid,
        items_inserted=stats.items_inserted,
        parse_success_rate=stats.parse_success_rate,
    )
    alert_if_unhealthy(status, run_id, platform, stats, error_message, alert_webhook_url)
    return RunResult(run_id, platform, status, stats, error_message)


def crawl_all(
    conn,
    platforms: list[str],
    selectors: dict[str, Any],
    crawler_cfg: CrawlerConfig,
    landing_dir: Path,
    force: bool = False,
    alert_webhook_url: str | None = None,
) -> list[RunResult]:
    client = PoliteClient(
        crawler_cfg.user_agent,
        crawler_cfg.request_timeout_seconds,
        crawler_cfg.delay_seconds,
        crawler_cfg.delay_jitter_seconds,
        crawler_cfg.max_attempts,
    )
    results = []
    try:
        for platform in platforms:
            last = recent_live_run(conn, platform, crawler_cfg.min_hours_between_live_runs)
            if last and not force:
                log.info(
                    "crawl_skipped_recent_run",
                    platform=platform,
                    last_run_at=last.isoformat(),
                    min_hours=crawler_cfg.min_hours_between_live_runs,
                )
                continue
            results.append(
                crawl_platform(
                    conn,
                    platform,
                    selectors[platform],
                    crawler_cfg,
                    client,
                    landing_dir,
                    alert_webhook_url,
                )
            )
    finally:
        client.close()
    return results


def load_landing(
    conn: psycopg.Connection,
    selectors: dict[str, Any],
    landing_dir: Path,
    platform: str | None = None,
) -> dict[str, int]:
    totals = {"runs": 0, "pages": 0, "rows_seen": 0, "rows_inserted": 0}
    for folder, manifest in iter_manifests(landing_dir, platform):
        platform_cfg = selectors[manifest.platform]
        started_at = datetime.fromisoformat(manifest.started_at)
        loader.start_run(
            conn,
            run_id=manifest.run_id,
            platform=manifest.platform,
            crawler_version=manifest.crawler_version,
            data_origin="live",
            started_at=started_at,
        )
        for landed in manifest.pages:
            content = (folder / landed.file).read_bytes()
            page = Page(landed.page, landed.url, content, datetime.fromisoformat(landed.fetched_at))
            rows, _ = build_rows(
                page,
                platform_cfg,
                manifest.platform,
                manifest.run_id,
                manifest.crawler_version,
                "live",
                landed.html_sha256,
            )
            totals["pages"] += 1
            totals["rows_seen"] += len(rows)
            totals["rows_inserted"] += loader.insert_listings(conn, rows)
        still_running = conn.execute(
            "SELECT 1 FROM raw.crawl_run WHERE run_id = %s AND status = 'running'",
            (manifest.run_id,),
        ).fetchone()
        if still_running:
            result = manifest.result or {
                "run_id": manifest.run_id,
                "finished_at": (started_at + timedelta(minutes=5)).isoformat(),
                "status": "failed",
                "pages_fetched": len(manifest.pages),
                "items_seen": None,
                "items_valid": None,
                "items_invalid": None,
                "parse_success_rate": None,
                "strategy_used": None,
                "error_message": "interrupted; closed by load-landing",
            }
            loader.finish_run(conn, **result)
        conn.commit()
        totals["runs"] += 1
    log.info("landing_loaded", **totals)
    return totals
