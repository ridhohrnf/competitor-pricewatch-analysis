with latest as (
    select distinct on (product_master_key, platform, data_origin)
        product_master_key,
        platform,
        data_origin,
        price,
        price_date
    from {{ ref('fct_product_price_daily') }}
    order by product_master_key, platform, data_origin, price_date desc, price
)

select
    p.canonical_name                                               as product,
    p.brand                                                        as brand,
    p.category                                                     as category,
    {{ pack_size('p') }}                                           as pack_size,
    case l.data_origin when 'live' then 'Live crawl' else 'Sample (synthetic)' end as data_source,
    max(l.price) filter (where pl.platform_code = 'tokopedia')     as tokopedia_price_idr,
    max(l.price) filter (where pl.platform_code = 'blibli')        as blibli_price_idr,
    max(l.price) filter (where pl.platform_code = 'klikindomaret') as klikindomaret_price_idr,
    min(l.price)                                                   as cheapest_price_idr,
    (array_agg(pl.platform_name order by l.price))[1]              as cheapest_platform,
    round((max(l.price) - min(l.price)) / min(l.price) * 100, 1)   as price_gap_pct,
    count(*)                                                       as platforms_compared,
    max(l.price_date)                                              as latest_price_date
from latest as l
join {{ ref('dim_product_master') }} as p using (product_master_key)
join {{ ref('dim_platform') }} as pl on pl.platform_code = l.platform
group by l.product_master_key, l.data_origin, p.canonical_name, p.brand, p.category,
    p.size_value, p.size_unit, p.pack_qty
