{{ config(materialized='view') }}

select
    run_id,
    platform,
    crawler_version,
    data_origin,
    started_at,
    finished_at,
    status,
    coalesce(pages_fetched, 0)  as pages_fetched,
    coalesce(items_seen, 0)     as items_seen,
    coalesce(items_valid, 0)    as items_valid,
    coalesce(items_invalid, 0)  as items_invalid,
    parse_success_rate,
    strategy_used,
    error_message
from {{ source('raw', 'crawl_run') }}
