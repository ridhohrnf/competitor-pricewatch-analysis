with ordered as (
    select data_origin, platform, listing_key, price_date, price,
           lag(price) over (partition by listing_key order by price_date) as previous_price
    from {{ ref('fct_product_price_daily') }}
),
per_listing as (
    select data_origin, platform, listing_key,
           sum(case when previous_price is not null and price <> previous_price then 1 else 0 end) as changes,
           greatest((max(price_date) - min(price_date)) / 7.0, 1) as weeks_observed
    from ordered
    group by data_origin, platform, listing_key
)
select data_origin, platform,
       count(*)                                  as listings,
       round(avg(changes / weeks_observed), 2)   as avg_changes_per_listing_per_week,
       round(avg(weeks_observed), 1)             as avg_weeks_observed
from per_listing
group by data_origin, platform
order by data_origin, platform
