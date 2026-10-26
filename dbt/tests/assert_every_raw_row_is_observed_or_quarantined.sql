with counts as (
    select
        (select count(*) from {{ source('raw', 'product_listing') }})       as raw_rows,
        (select count(*) from {{ ref('silver_price_observation') }})        as observed,
        (select count(*) from {{ ref('silver_rejected_listing') }})         as quarantined,
        (select count(*) - count(distinct (listing_key, crawled_at))
           from {{ ref('int_listing_checked') }} where reject_reason is null) as duplicates
)
select * from counts where raw_rows <> observed + quarantined + duplicates
