import argparse
import sys

from pricewatch.logging import configure_logging, get_logger
from pricewatch.settings import get_settings, load_crawler_config, load_selectors

log = get_logger("pricewatch.cli")
PLATFORMS = ("tokopedia",)  # Blibli / Klik Indomaret: blocked, sample data only


def cmd_crawl(args) -> int:
    from pricewatch.crawler.runner import crawl_all
    from pricewatch.db import connect, wait_for_db

    settings = get_settings()
    wait_for_db()
    platforms = [args.platform]
    crawler_cfg = load_crawler_config()
    if args.max_pages:
        crawler_cfg.max_pages = args.max_pages
    with connect() as conn:
        results = crawl_all(
            conn,
            platforms,
            load_selectors(),
            crawler_cfg,
            settings.landing_dir,
            force=args.force,
            alert_webhook_url=settings.alert_webhook_url,
        )
    for r in results:
        print(
            f"{r.platform}: {r.status} pages={r.stats.pages_fetched} seen={r.stats.items_seen} "
            f"valid={r.stats.items_valid} inserted={r.stats.items_inserted} {r.error_message or ''}"
        )
    # A blocked or failed live crawl is reported, but it is not a pipeline failure:
    # the rest of the system keeps working on the data that already exists.
    return 1 if args.strict and any(r.status != "success" for r in results) else 0


def cmd_load_landing(args) -> int:
    from pricewatch.crawler.runner import load_landing
    from pricewatch.db import connect, wait_for_db

    wait_for_db()
    with connect() as conn:
        totals = load_landing(conn, load_selectors(), get_settings().landing_dir, args.platform)
    print(totals)
    return 0


def cmd_generate_sample(args) -> int:
    from pricewatch.sample.generate import write_sample

    counts = write_sample(get_settings().sample_dir, days=args.days, seed=args.seed)
    print(counts)
    return 0


def cmd_load_sample(args) -> int:
    from pricewatch.db import connect, wait_for_db
    from pricewatch.sample.generate import load_sample

    wait_for_db()
    with connect() as conn:
        counts = load_sample(conn, get_settings().sample_dir)
    print(counts)
    return 0


def cmd_ingest(args) -> int:
    """The `ingest` step of docker compose: sample + backfill + (rate-limited) live crawl."""
    cmd_load_sample(args)
    cmd_load_landing(argparse.Namespace(platform=None))
    if args.skip_live or get_settings().skip_live_crawl:
        log.info("live_crawl_skipped_by_setting")
        return 0
    return cmd_crawl(
        argparse.Namespace(platform="tokopedia", force=False, max_pages=None, strict=False)
    )


def cmd_recommend(args) -> int:
    from pricewatch.db import connect, wait_for_db
    from pricewatch.recommender.job import run_recommendations

    wait_for_db()
    with connect() as conn:
        result = run_recommendations(conn)
    print(result)
    return 0 if result["rows"] > 0 else 1


def main(argv: list[str] | None = None) -> int:
    configure_logging(get_settings().log_level)
    parser = argparse.ArgumentParser(prog="pricewatch")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("crawl", help="live crawl (respects robots.txt and run limits)")
    p.add_argument("--platform", choices=PLATFORMS, default="tokopedia")
    p.add_argument("--force", action="store_true", help="ignore min_hours_between_live_runs")
    p.add_argument("--max-pages", type=int)
    p.add_argument("--strict", action="store_true", help="exit 1 unless every run succeeded")
    p.set_defaults(func=cmd_crawl)

    p = sub.add_parser("load-landing", help="backfill raw from landed HTML (no crawling)")
    p.add_argument("--platform", choices=PLATFORMS)
    p.set_defaults(func=cmd_load_landing)

    p = sub.add_parser("generate-sample", help="write the synthetic sample dataset")
    p.add_argument("--days", type=int, default=56)
    p.add_argument("--seed", type=int, default=42)
    p.set_defaults(func=cmd_generate_sample)

    sub.add_parser("load-sample", help="load sample_data/ into raw").set_defaults(
        func=cmd_load_sample
    )

    p = sub.add_parser("ingest", help="load-sample + load-landing + live crawl")
    p.add_argument("--skip-live", action="store_true")
    p.set_defaults(func=cmd_ingest)

    sub.add_parser("recommend", help="batch pricing recommendations").set_defaults(
        func=cmd_recommend
    )

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
