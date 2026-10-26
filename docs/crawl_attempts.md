# Crawl attempts and data sourcing

robots.txt and terms of service read on 2026-10-18. Last attempt logged: 2026-10-19.

## Summary

The brief asks for live crawling of 1 or 2 sites while respecting ToS and robots.txt. All three sites
restrict automated access in their ToS. Because the brief still requires a live crawl:

- **Tokopedia** is the live source, crawled minimally (one shop listing, at most one run per 10 h).
- **Blibli** and **Klik Indomaret** were each tried once with strict limits and stopped when
  blocked. They use **sample data** (`data_origin = 'sample'`), labelled as such in every layer.

## Rules the crawler follows

| Rule | Where it is enforced | Test |
|---|---|---|
| robots.txt checked before every URL (protego, understands `/*?extParam=`) | `PoliteClient.is_allowed` | `test_url_with_tracking_query_is_refused_by_robots_and_never_requested` |
| robots.txt 404 = no rules, 5xx = stay out, 403 = blocked | `PoliteClient._load_robots` | three `test_robots_txt_*` / `test_missing_robots_txt_*` tests |
| Honest User-Agent `pricewatch-takehome/0.1` | `config/crawler.yaml` | |
| ≥ 3 s between requests + jitter, from the end of the previous request | `PoliteClient._request` | `test_requests_to_the_same_host_are_spaced_by_the_configured_delay` |
| Retry only 429, 5xx, network errors (max 3) | `PoliteClient.get` | `test_server_error_is_retried_until_max_attempts` |
| 403 or a bot-check page = stop, status `blocked`, no workaround | `BlockedError` | `test_403_stops_immediately_without_retrying`, `test_bot_check_page_is_treated_as_blocked_even_with_status_200` |
| Redirects are not followed (the target would skip the robots check) | httpx default | `test_redirect_is_not_followed_because_the_target_skips_the_robots_check` |
| At most one live run per platform per 10 h, even if Compose is run many times | `runner.recent_live_run`, `min_hours_between_live_runs: 10` | log `crawl_skipped_recent_run` |
| No login, no `/api/` or `/graphql`, no personal data | | |
| Raw HTML and live data stay local | `data/` in `.gitignore`; test fixtures are hand-written | |

## robots.txt and ToS findings (2026-10-18)

| Platform | robots.txt | ToS |
|---|---|---|
| Tokopedia | `/unilever-official-store/product` allowed; disallowed include `/graphql`, `/search?*` and any URL with `?extParam=` (every product link), so product pages are never opened | Prohibits crawlers, robots and scraping of content |
| Klik Indomaret | only `/api/` disallowed | Art. 10 prohibits robots or spiders retrieving or indexing content |
| Blibli | disallows `/cari/*` (the brief's URL), `/merchant*/products`, `/backend/search/*` | Art. 2.2 prohibits copying or downloading site information for any purpose |

## Attempt log

Only what was actually done.

| Date (WIB) | Platform | Target | Result | Status |
|---|---|---|---|---|
| 2026-10-14 | Tokopedia | shop listing | HTTP 200, ±1.6 MB, 80 products per page. Manual inspection with curl to see the page structure, not the crawler | ok |
| 2026-10-14 | Klik Indomaret | `/search?keyword=unilever` | HTTP 200, page skeleton only (±3.5 KB); products rendered by JavaScript | needs browser |
| 2026-10-14 | Blibli | merchant page | HTTP 403 | blocked |
| 2026-10-19 03:0x | all three | `/robots.txt`, once each | HTTP 200 | ok |
| 2026-10-19 02:57 | Tokopedia | listing pages 1 to 5 | 5 pages, 346 products, 346 valid; stopped at page 5 (26 < 80) | **success** |
| 2026-10-19 03:03 | Blibli | `/brand/unilever` (allowed by robots), 1 request | HTTP 403 | **blocked**, stopped without retry |
| 2026-10-19 03:12 | Klik Indomaret | search page in a headless browser | render stalled: a bug in our code | failed, fixed |
| 2026-10-19 03:14 | Klik Indomaret | same, after the fix | products only appear after loading scripts from hosts whose robots.txt answers 403, and after running an AWS WAF bot check; neither was done | **blocked** |
| 2026-10-19 03:54 | Tokopedia | listing pages 1 to 5 (2nd run that day) | 346 products, **0 new raw rows** (P1) | **success** |
| 2026-10-26 14:42 | Tokopedia | listing page 1, submitted crawler (`fetch.py`) | A 2xx answer that the crawler recognised as a bot-check / verification page (a small page with a verification marker). Stopped on the first page: nothing retried, nothing parsed, no workaround | **blocked** |
| 2026-10-26 16:51 | Tokopedia | listing pages 1 to 5, submitted crawler, `--force` past the 10-hour guard | HTTP 200 on every page, 360 products (5 pages: 80, 80, 80, 80, 40), 360 valid, 360 new rows. The block seen at 14:42 did **not** repeat | **success** |

The 14:42 block was not reproducible: two hours later the same code got normal pages. The page that triggered it was not saved, so a real bot check and a false positive of our check (a small page containing a verification word) cannot be told apart. A blocked run counts towards the 10-hour guard, so the 16:51 run needed `--force` (still within the limit of two live runs per day). After the block, the pipeline kept working on the 2026-10-19 data and reported the run as `blocked` in `report_pipeline_health`.

Requests on 2026-10-26: Tokopedia 8 (2 in the blocked run: robots.txt and the first page; 6 in the
successful run: robots.txt and 5 pages).

Requests on 2026-10-19: Tokopedia 13 (2 runs × [robots.txt + 5 pages] + 1 manual robots.txt),
Blibli 3, Klik Indomaret 2 pages plus robots.txt of the hosts the browser tried to load.

Note: the Blibli and Klik Indomaret attempts used an earlier, multi-platform version of this
crawler (with a Playwright fetcher for Klik Indomaret). The submitted crawler is Tokopedia-only,
because the other two sites ended blocked and the browser code added complexity without data.

## Sample data

- Synthetic and deterministic (`seed = 42`, generating twice gives identical files), built from a
  hand-written catalogue of 29 products, not from crawled content: `src/pricewatch/sample/`.
- 3 platforms × 56 days, platform price offsets (Blibli 2% cheaper, Klik Indomaret 3% more expensive), weekday promo
  patterns, deliberate defects (unreadable prices, giveaways, bundles, crossed-out price below
  price) and one product rename for the SCD2 demo.
- Loaded through the same loader as live data, so idempotency and quarantine apply to it too.

## Remaining risks

- Tokopedia's ToS restricts crawling. The footprint is kept minimal and documented here; a real
  system would need permission or a licensed source.
- Prices depend on the delivery location; the crawler uses the site's default.
- robots.txt and ToS can change after the dates above.
