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

{% if is_incremental() %}
affected as (
    select crawl_date, listing_key
    from observations
    where inserted_at > (
        select coalesce(max(_max_inserted_at), '1900-01-01'::timestamptz)
               - interval '{{ var("incremental_lookback_hours") }} hours'
        from {{ this }}
    )
    union
    select t.price_date, t.listing_key
    from {{ this }} as t
    inner join matches as m using (listing_key)
    where t.product_master_key <> m.product_master_key
),

scoped as (
    select o.*
    from observations as o
    inner join affected as a
        on a.crawl_date = o.crawl_date and a.listing_key = o.listing_key
),
{% else %}
scoped as (
    select * from observations
),
{% endif %}

ranked as (
    select
        *,
        row_number() over w_desc                        as rank_in_day,
        count(*) over w_all                             as n_observations,
        max(inserted_at) over w_all                     as max_inserted_at
    from scoped
    window
        w_desc as (partition by crawl_date, listing_key order by crawled_at desc, raw_id desc),
        w_all as (partition by crawl_date, listing_key)
)

select
    r.crawl_date                                        as price_date,
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
    r.max_inserted_at                                   as _max_inserted_at
from ranked as r
inner join matches as m using (listing_key)
where r.rank_in_day = 1
