with quarantined as (
    select run_id, count(*) as items_rejected_silver
    from {{ ref('silver_rejected_listing') }}
    group by run_id
)

select
    r.run_id,
    r.platform,
    (r.started_at at time zone 'Asia/Jakarta')::date             as run_date,
    r.started_at,
    r.finished_at,
    extract(epoch from r.finished_at - r.started_at)::int        as duration_seconds,
    r.status,
    r.data_origin,
    r.crawler_version,
    r.pages_fetched,
    r.items_seen,
    r.items_valid,
    r.items_invalid,
    coalesce(q.items_rejected_silver, 0)                         as items_rejected_silver,
    r.parse_success_rate,
    r.strategy_used,
    r.error_message
from {{ ref('stg_crawl_run') }} as r
left join quarantined as q using (run_id)
