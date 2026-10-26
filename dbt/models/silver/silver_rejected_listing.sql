select
    raw_id,
    run_id,
    platform,
    listing_key,
    crawled_at,
    crawl_date,
    data_origin,
    listing_name,
    price_text,
    original_price_text,
    reject_reason,
    validation_errors
from {{ ref('int_listing_checked') }}
where reject_reason is not null
