# Proof

Each scenario below was run on 2026-10-26 (WIB) against this repository, and the output is
copied as printed. Re-run with the command given.

| # | Scenario | Expected | Result |
|---|---|---|---|
| P1 | Load the same crawl twice | no new raw rows | ✔ 0 inserted |
| P2 | Embedded JSON removed | DOM fallback still finds products, run degraded | ✔ 10 products via `dom_semantic` |
| P3 | Page without products | run `failed` | ✔ integration test |
| P4 | Bad records | quarantined with a reason | ✔ 198 rows, 4 reasons |
| P5 | Late data (old crawl date, new insert) | reaches gold | ✔ |
| P6 | Incremental vs full refresh | 0 differing rows | ✔ identical |
| P7 | API and BI roles read silver | permission denied | ✔ |
| P8 | `docker compose down -v && up` | every service healthy from zero, dashboard imported | ✔ about 1.5 to 3 minutes |
| P9 | Listing renamed | snapshot holds 2 versions | ✔ |

## P1 Idempotency

All saved live crawls (2 runs on 2026-10-19, 1 blocked run and 1 successful run on 2026-10-26; 15
pages in total) re-parsed from the landing zone, twice:

```
$ docker compose run --rm dev python -m pricewatch.cli load-landing
{'runs': 4, 'pages': 15, 'rows_seen': 1052, 'rows_inserted': 0}
$ docker compose run --rm dev python -m pricewatch.cli load-landing
{'runs': 4, 'pages': 15, 'rows_seen': 1052, 'rows_inserted': 0}
$ select crawl_date, count(*) from raw.product_listing where data_origin = 'live' group by 1;
 2026-10-19 | 346
 2026-10-26 | 360
```

Nothing is added on a re-run. The crawl of 26 October did add 360 rows the first time, because it
is a new day and the prices had changed. The second crawl of 2026-10-19 had also shown the same
thing live: 346 products seen, 0 new rows.
Covered by `test_running_the_same_crawl_twice_adds_no_duplicate_rows`.

## P2 Site changes structure: JSON gone

`window.__cache=` replaced in page 1, then extracted:

```
with marker:     80 products, strategy apollo_cache
without marker:  10 products, strategy dom_semantic
fields filled by the fallback: name, price_text, original_price_text, discount_text, source_url
```

(Live product names and prices are left out of the repo on purpose.)

The server-rendered HTML only holds 10 product cards, so the run falls below
`min_items_expected: 40` and is marked `degraded`: visible, not silent.

## P3 Broken page

`test_page_without_products_ends_the_run_as_failed` (real Postgres): a page with no products
ends the run as `failed` with nothing inserted; `test_blocked_site_ends_the_run_as_blocked_with_the_reason`
does the same for a 403.

## P4 Quarantine

```
$ select data_origin, reject_reason, count(*) from silver.silver_rejected_listing group by 1, 2;
 live    | bundle_without_brand |   5
 live    | giveaway_item        |   4
 sample  | not_unilever_brand   | 168
 sample  | contract_invalid     |  21
```

`assert_every_raw_row_is_observed_or_quarantined` checks that no raw row is lost between the two.

## P5 Late data and P9 SCD2

```
$ docker compose run --rm dev python scripts/proof/late_data_and_scd2.py
P5 target: blibli:bango-kecap-manis-refill-520-ml-6e7b29 on 2026-08-17: price 24400, 1 observation(s)
loaded now (inserted_at = 2026-10-25 18:56) an observation crawled on 2026-08-17 23:00 WIB at Rp23900
$ dbt run --select +fct_product_price_daily
after incremental run: price 23900, 2 observation(s)
P5 RESULT: late row reached gold

P9: snapshot versions of blibli:bango-kecap-manis-refill-520-ml-6e7b29 before rename: 1
$ dbt build --exclude resource_type:test resource_type:unit_test
  Bango Kecap Manis Refill - 520 mL                            valid_from=2026-10-25 18:56 valid_to=2026-10-25 18:56
  Bango Kecap Manis Refill - 520 mL (Kemasan Baru)             valid_from=2026-10-25 18:56 valid_to=null (current)
P9 RESULT: old version closed, new version current
```

The script works on a throw-away database (`pricewatch_proof`), not the main one.

## P6 Incremental equals full refresh

```
$ docker compose run --rm dev python scripts/proof/incremental_vs_full_refresh.py
rows before: 4820
rows (incremental)           4820
rows (full refresh)          4820
rows only in incremental     0
rows only in full refresh    0
RESULT: identical
```

## P7 Least privilege

```
[bi_reader] select count(*) from gold.dim_platform;                -> 3
[bi_reader] select count(*) from silver.silver_price_observation;  -> ERROR: permission denied for schema silver
[api_app]   select count(*) from gold.dim_platform;                -> 3
[api_app]   select count(*) from silver.silver_price_observation;  -> ERROR: permission denied for schema silver
```

## P8 From zero

```
$ docker compose down -v && docker compose up -d --build
up-exit=0 seconds=89 to 159   (images cached; a first build takes longer)
api             Up (healthy)
dbt             Exited (0)
dbt-docs        Up
ingest          Exited (0)
postgres        Up (healthy)
recommender     Exited (0)
superset        Up (healthy)
superset-init   Exited (0)
```

`dbt build` on an empty database: `PASS=138 WARN=0 ERROR=0`. pytest: 69 passed (5 integration tests
on Postgres). On a database that already has older recommendation runs it ends with one warning,
`older_recommendations_whose_product_was_rekeyed`, which is expected.

The dashboard is imported too. With a Superset that had no data at all, `superset-init` finished
with exit code 0 and Superset then had 1 dashboard, 8 charts and 3 datasets, and every chart
returned data.

`dbt source freshness` warns when the newest live crawl is older than 24 hours (error after 48
hours). It reports the problem and does not stop the pipeline.

When new data arrives, one more test warns until the price suggestions are recalculated (the
previous suggestions can point at products that were re-matched). It is a warning on purpose: the
recommender only runs after dbt succeeds, so an error here would block the very step that fixes it.

## Bonus: Dagster runs the same chain

```
$ make orchestrator-run
... STEP_START raw_layer → pricewatch_dbt (84 asset checks, all passed) → price_recommendations → recommendation_report
RUN_SUCCESS
```

`tests/test_orchestration.py` (4 tests, run in the orchestrator image) checks that the job loads,
that dbt depends on the ingest assets, that recommendations sit between the price fact and their
report, and that the schedule uses Asia/Jakarta time.
