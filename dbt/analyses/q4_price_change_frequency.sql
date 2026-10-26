with ordered as (
    select f.data_origin, f.platform, f.listing_key, f.price_date, f.price,
           lag(f.price) over (partition by f.listing_key order by f.price_date) as previous_price,
           lag(f.price_date) over (partition by f.listing_key order by f.price_date) as previous_date
    from {{ ref('fct_product_price_daily') }} f
),
changes as (
    select o.*, d.day_name, d.day_of_week,
           o.previous_price is not null and o.price <> o.previous_price as is_change,
           o.price > o.previous_price as is_increase
    from ordered o
    join {{ ref('dim_date') }} d on d.date = o.price_date
    where o.previous_price is not null
)
select
    data_origin,
    platform,
    day_of_week,
    day_name,
    count(*)                                                       as listing_days,
    sum(case when is_change then 1 else 0 end)                     as price_changes,
    round(avg(case when is_change then 1 else 0 end) * 100, 1)     as pct_listing_days_with_change,
    sum(case when is_change and is_increase then 1 else 0 end)     as increases,
    sum(case when is_change and not is_increase then 1 else 0 end) as decreases
from changes
group by data_origin, platform, day_of_week, day_name
order by data_origin, platform, day_of_week
