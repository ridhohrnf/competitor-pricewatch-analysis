with live_runs as (
    select
        platform,
        bool_or(status = 'success')                          as has_successful_live_run,
        max(started_at)                                      as last_live_run_at,
        (array_agg(status order by started_at desc))[1]      as last_live_run_status
    from {{ ref('stg_crawl_run') }}
    where data_origin = 'live'
    group by platform
)

select
    p.platform_code,
    p.platform_name,
    p.base_url,
    coalesce(r.has_successful_live_run, false)               as is_live_crawled,
    r.last_live_run_at,
    r.last_live_run_status
from {{ ref('dim_platform_seed') }} as p
left join live_runs as r on r.platform = p.platform_code
