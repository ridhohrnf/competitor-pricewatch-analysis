with per_platform as (
    select data_origin, price_date, product_master_key, platform, min(price) as price
    from {{ ref('fct_product_price_daily') }}
    group by data_origin, price_date, product_master_key, platform
),
daily as (
    select *,
           count(*) over (partition by data_origin, price_date, product_master_key) as n_platforms
    from per_platform
),
latest_common_day as (
    select data_origin, product_master_key, max(price_date) as price_date
    from daily where n_platforms >= 2
    group by data_origin, product_master_key
)
select
    d.data_origin,
    p.canonical_name                                             as product,
    d.price_date,
    count(*)                                                     as n_platforms,
    min(d.price)                                                 as min_price,
    max(d.price)                                                 as max_price,
    (array_agg(d.platform order by d.price))[1]                  as cheapest_platform,
    (array_agg(d.platform order by d.price desc))[1]             as most_expensive_platform,
    round((max(d.price) - min(d.price)) / min(d.price) * 100, 1) as spread_pct,
    round((stddev_pop(d.price) / avg(d.price) * 100)::numeric, 1) as cv_pct
from daily d
join latest_common_day l using (data_origin, product_master_key, price_date)
join {{ ref('dim_product_master') }} p using (product_master_key)
group by d.data_origin, p.canonical_name, d.price_date
order by spread_pct desc
limit 15
