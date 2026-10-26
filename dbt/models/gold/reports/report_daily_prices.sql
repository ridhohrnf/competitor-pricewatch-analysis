select
    f.price_date                                                   as price_date,
    d.day_name                                                     as day_name,
    pl.platform_name                                               as platform,
    p.canonical_name                                               as product,
    p.brand                                                        as brand,
    p.category                                                     as category,
    {{ pack_size('p') }}                                           as pack_size,
    f.listing_name                                                 as name_on_platform,
    f.price                                                        as price_idr,
    f.original_price                                               as original_price_idr,
    round(f.discount_pct, 1)                                       as discount_pct,
    f.is_discounted                                                as on_discount,
    case f.data_origin when 'live' then 'Live crawl' else 'Sample (synthetic)' end as data_source
from {{ ref('fct_product_price_daily') }} as f
join {{ ref('dim_product_master') }} as p using (product_master_key)
join {{ ref('dim_platform') }} as pl on pl.platform_code = f.platform
join {{ ref('dim_date') }} as d on d.date = f.price_date
