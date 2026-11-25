{{
    config(
        materialized='incremental',
        incremental_strategy='merge',
        unique_key=['price_date', 'listing_key'],
        on_schema_change='fail'
    )
}}

with observations as (
    select * from {{ ref('silver_price_observation') }}
),

matches as (
    select listing_key, product_master_key from {{ ref('silver_product_match') }}
),

ranked as (
    select
        *,
        row_number() over w_desc                        as rank_in_day,
        count(*) over w_all                             as n_observations,
        max(inserted_at) over w_all                     as max_inserted_at
    from observations
    window
        w_desc as (partition by crawl_date, listing_key order by crawled_at desc, raw_id desc),
        w_all as (partition by crawl_date, listing_key)
),

daily as (
    select
        r.crawl_date                                    as price_date,
        r.platform,
        m.product_master_key,
        r.listing_key,
        r.listing_name,
        r.price,
        r.original_price,
        r.discount_pct,
        r.is_discounted,
        r.n_observations,
        r.data_origin,
        r.max_inserted_at                               as _max_inserted_at
    from ranked as r
    inner join matches as m using (listing_key)
    where r.rank_in_day = 1
)

select d.*
from daily as d
{% if is_incremental() %}
where not exists (
    select 1
    from {{ this }} as t
    where t.price_date = d.price_date
      and t.listing_key = d.listing_key
      and row(t.platform, t.product_master_key, t.listing_name, t.price, t.original_price,
              t.discount_pct, t.is_discounted, t.n_observations, t.data_origin, t._max_inserted_at)
          is not distinct from
          row(d.platform, d.product_master_key, d.listing_name, d.price, d.original_price,
              d.discount_pct, d.is_discounted, d.n_observations, d.data_origin, d._max_inserted_at)
)
{% endif %}
