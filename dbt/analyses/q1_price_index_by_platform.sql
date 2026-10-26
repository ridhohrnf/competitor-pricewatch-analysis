with daily as (
    select data_origin, price_date, product_master_key, platform, min(price) as price
    from {{ ref('fct_product_price_daily') }}
    group by data_origin, price_date, product_master_key, platform
),
comparable as (
    select *,
           avg(price) over (partition by data_origin, price_date, product_master_key) as market_avg,
           count(*)   over (partition by data_origin, price_date, product_master_key) as n_platforms,
           rank()     over (partition by data_origin, price_date, product_master_key
                            order by price) as price_rank
    from daily
)
select
    data_origin,
    platform,
    count(*)                                                  as product_days_compared,
    count(distinct product_master_key)                        as products_compared,
    round(avg(price / market_avg * 100), 1)                   as avg_price_index,
    round((percentile_cont(0.5) within group (order by price / market_avg * 100))::numeric, 1)
                                                              as median_price_index,
    round(avg(case when price_rank = 1 then 1 else 0 end) * 100, 1) as pct_days_cheapest
from comparable
where n_platforms >= 2
group by data_origin, platform
order by data_origin, avg_price_index
