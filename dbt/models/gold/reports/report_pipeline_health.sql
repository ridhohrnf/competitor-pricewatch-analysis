{{ config(materialized='view') }}

select
    pl.platform_name                                               as platform,
    case r.data_origin when 'live' then 'Live crawl' else 'Sample (synthetic)' end as data_source,
    (r.started_at at time zone 'Asia/Jakarta')::timestamp(0)       as started_at_wib,
    round(extract(epoch from now() - r.started_at) / 3600, 1)      as hours_ago,
    case r.status
        when 'success' then 'OK'
        when 'degraded' then 'Degraded: fewer or broken products'
        when 'failed' then 'Failed: no products'
        when 'blocked' then 'Blocked by the site'
        else r.status
    end                                                            as status,
    r.pages_fetched                                                as pages_fetched,
    r.items_seen                                                   as products_found,
    r.items_valid                                                  as products_valid,
    r.items_rejected_silver                                        as products_quarantined,
    round(r.parse_success_rate * 100, 1)                           as parse_success_pct,
    r.strategy_used                                                as parser_used,
    r.duration_seconds                                             as duration_seconds,
    r.error_message                                                as error_message,
    row_number() over (
        partition by r.platform, r.data_origin order by r.started_at desc
    ) = 1                                                          as is_latest_run
from {{ ref('fct_crawl_run') }} as r
join {{ ref('dim_platform') }} as pl on pl.platform_code = r.platform
