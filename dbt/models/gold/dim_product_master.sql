with listings as (
    select
        m.master_key,
        m.product_master_key,
        m.match_method,
        a.*
    from {{ ref('silver_product_match') }} as m
    inner join {{ ref('silver_listing_attributes') }} as a using (listing_key)
)

select
    product_master_key,
    (array_agg(listing_name order by
        case data_origin when 'live' then 0 else 1 end,
        case platform when 'tokopedia' then 0 else 1 end,
        length(listing_name)))[1]                           as canonical_name,
    mode() within group (order by brand)                     as brand,
    mode() within group (order by category)                  as category,
    mode() within group (order by size_value)                as size_value,
    mode() within group (order by size_unit)                 as size_unit,
    mode() within group (order by pack_qty)                  as pack_qty,
    count(distinct platform)                                 as n_platforms_listed,
    string_agg(distinct data_origin, ',' order by data_origin) as data_origins,
    bool_or(is_bundle)                                       as is_bundle,
    mode() within group (order by match_method)              as match_method
from listings
group by product_master_key, master_key
