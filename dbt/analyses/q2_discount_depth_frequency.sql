select
    f.data_origin,
    p.category,
    f.platform,
    count(*)                                                        as product_days,
    round(avg(case when f.is_discounted then 1 else 0 end) * 100, 1) as pct_days_discounted,
    round(avg(f.discount_pct) filter (where f.is_discounted), 1)    as avg_depth_pct,
    round((percentile_cont(0.5) within group (order by f.discount_pct)
           filter (where f.is_discounted))::numeric, 1)             as median_depth_pct,
    max(f.discount_pct)                                             as max_depth_pct
from {{ ref('fct_product_price_daily') }} f
join {{ ref('dim_product_master') }} p using (product_master_key)
group by f.data_origin, p.category, f.platform
order by f.data_origin, p.category, f.platform
