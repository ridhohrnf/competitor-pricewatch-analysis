{{ config(materialized='table') }}

with listings as (
    select * from {{ ref('stg_product_listing') }}
),

with_brand as (
    select
        l.*,
        b.brand,
        b.brand_slug,
        b.default_category
    from listings as l
    left join lateral (

        select brand, brand_slug, default_category
        from {{ ref('unilever_brands') }} as ub
        where lower(l.listing_name) ~ ub.alias_regex
        order by regexp_instr(lower(l.listing_name), ub.alias_regex), length(ub.brand) desc
        limit 1
    ) as b on true
),

with_category as (
    select
        wb.*,
        coalesce(rule.category, wb.default_category) as category
    from with_brand as wb
    left join lateral (
        select category
        from {{ ref('category_rules') }} as cr
        where lower(wb.listing_name) ~ cr.pattern
        order by cr.priority
        limit 1
    ) as rule on true
),

judged as (
    select
        *,

        coalesce(original_price_shown, price)                as original_price,
        case
            when not is_valid then 'contract_invalid'
            when price is null then 'price_unparseable'
            when brand is null and lower(listing_name) ~ '(giveaway|gratis|free\M|hadiah)'
                then 'giveaway_item'
            when brand is null and lower(listing_name) ~ '(paket|bundle|banded|bundling)'
                then 'bundle_without_brand'
            when brand is null then 'not_unilever_brand'
            when original_price_shown < price then 'original_below_price'
        end                                                  as reject_reason
    from with_category
)

select
    raw_id,
    run_id,
    platform,
    external_product_id,
    listing_key,
    crawled_at,
    crawl_date,
    data_origin,
    inserted_at,
    source_url,
    listing_name,
    brand,
    brand_slug,
    category,
    price_text,
    original_price_text,
    price,
    original_price,

    case when original_price > 0 and original_price > price
         then round((original_price - price) / original_price * 100, 2)
         else 0 end                                          as discount_pct,
    coalesce(original_price > price, false)                  as is_discounted,
    source_discount_text,
    case when source_discount_text ~ '^[0-9.]+$' and original_price > price
         then abs(source_discount_text::numeric
                  - round((original_price - price) / original_price * 100, 2)) > 2
         else false end                                      as source_discount_mismatch,
    lower(listing_name) ~ '(bundle|paket|\+)'                as is_bundle,
    extraction_strategy,
    validation_errors,
    reject_reason
from judged
