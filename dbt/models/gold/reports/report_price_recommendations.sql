{{ config(materialized='view') }}

with latest_run as (
    select run_id
    from {{ source('jobs', 'fct_price_recommendation') }}
    order by run_at desc
    limit 1
),

one_per_product as (
    select
        r.*,
        row_number() over (
            partition by r.product_master_key
            order by r.n_platforms desc, (r.data_origin = 'live') desc
        ) as pick
    from {{ source('jobs', 'fct_price_recommendation') }} as r
    join latest_run using (run_id)
)

select
    p.canonical_name                                               as product,
    p.brand                                                        as brand,
    p.category                                                     as category,
    {{ pack_size('p') }}                                           as pack_size,
    case r.data_origin when 'live' then 'Live crawl' else 'Sample (synthetic)' end as data_source,
    round(r.recommended_price)::bigint                             as recommended_price_idr,
    round(r.competitor_min_price)::bigint                          as competitor_lowest_idr,
    round(r.competitor_median_price)::bigint                       as competitor_median_idr,
    round(r.competitor_max_price)::bigint                          as competitor_highest_idr,
    round(r.floor_price)::bigint                                   as minimum_allowed_price_idr,
    round((r.recommended_price - r.competitor_median_price)
        / r.competitor_median_price * 100, 1)                      as vs_competitor_median_pct,
    r.n_platforms                                                  as platforms_compared,
    c.tokopedia_price_idr                                          as tokopedia_price_idr,
    c.blibli_price_idr                                             as blibli_price_idr,
    c.klikindomaret_price_idr                                      as klikindomaret_price_idr,
    c.cheapest_platform                                            as cheapest_platform,
    c.price_gap_pct                                                as price_gap_pct,
    case r.reason_code
        when 'median_minus_x' then 'Competitor median minus '
            || round((r.params ->> 'undercut_pct')::numeric * 100) || '%'
        when 'margin_floor' then 'Raised to the minimum margin'
        when 'single_platform_low_confidence' then 'Only one platform to compare: low confidence'
        else r.reason_code
    end                                                            as how_it_was_set,
    r.as_of_date                                                   as prices_as_of,
    r.run_at                                                       as calculated_at,
    r.model_version                                                as model_version
from one_per_product as r
join {{ ref('dim_product_master') }} as p using (product_master_key)
left join {{ ref('report_price_comparison') }} as c
    on c.product = p.canonical_name
   and c.data_source = case r.data_origin when 'live' then 'Live crawl' else 'Sample (synthetic)' end
where r.pick = 1
