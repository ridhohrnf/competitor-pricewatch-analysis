{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw', 'product_listing') }}
)

select
    id                                               as raw_id,
    run_id,
    platform,
    external_product_id,
    platform || ':' || external_product_id           as listing_key,
    crawled_at,
    crawl_date,
    data_origin,
    crawler_version,
    inserted_at,
    is_valid,
    validation_errors,
    source_url,
    payload ->> 'name'                               as listing_name,
    payload ->> 'price_text'                         as price_text,
    payload ->> 'original_price_text'                as original_price_text,
    payload ->> 'discount_text'                      as discount_text,
    payload ->> 'source_discounted_percentage'       as source_discount_text,
    payload ->> 'strategy'                           as extraction_strategy,
    {{ parse_idr("payload ->> 'price_text'") }}          as price,
    {{ parse_idr("payload ->> 'original_price_text'") }} as original_price_shown
from source
