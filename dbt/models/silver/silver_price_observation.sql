with accepted as (
    select
        *,
        row_number() over (partition by listing_key, crawled_at order by raw_id desc) as dup_rank
    from {{ ref('int_listing_checked') }}
    where reject_reason is null
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
    category,
    price,
    original_price,
    discount_pct,
    is_discounted,
    source_discount_mismatch,
    is_bundle,
    extraction_strategy
from accepted
where dup_rank = 1
