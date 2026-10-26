with latest as (
    select distinct on (listing_key)
        listing_key,
        platform,
        data_origin,
        external_product_id,
        listing_name,
        brand,
        category,
        is_bundle,
        crawled_at as last_seen_at
    from {{ ref('silver_price_observation') }}
    order by listing_key, crawled_at desc
),

sized as (
    select
        l.*,
        ub.brand_slug,
        ub.alias_regex,
        pack_size.size_value,
        pack_size.size_unit,
        trim_scale(pack_size.size_base) as size_base,
        pack_size.base_unit,
        pack_size.pack_qty
    from latest as l
    inner join {{ ref('unilever_brands') }} as ub on ub.brand = l.brand
    {{ parse_pack_size('l.listing_name') }}
),

cleaned as (

    select
        listing_key,
        regexp_replace(
            regexp_replace(
                regexp_replace(
                    regexp_replace(
                        lower(regexp_replace(listing_name, '(\d),(\d)', '\1.\2', 'g')),
                        '\[[^]]*\]', ' ', 'g'),
                    alias_regex, ' ', 'g'),
                '(\d+\s*[x×]\s*)?\d+(\.\d+)?\s*(ml|ltr|liter|lt|l|gram|gr|g|kg)\M', ' ', 'g'),
            '[^a-z]+', ' ', 'g') as clean_name
    from sized
),

tokens as (
    select
        c.listing_key,
        string_agg(distinct coalesce(tr.canonical, t.tok), ' '
                   order by coalesce(tr.canonical, t.tok)) as core_tokens
    from cleaned as c
    cross join lateral regexp_split_to_table(trim(c.clean_name), '\s+') as t (tok)
    left join {{ ref('token_rules') }} as tr on tr.token = t.tok
    where length(t.tok) > 1
      and coalesce(tr.canonical, '') <> '-'
    group by c.listing_key
)

select
    s.listing_key,
    s.platform,
    s.data_origin,
    s.external_product_id,
    s.listing_name,
    s.brand,
    s.category,
    s.size_value,
    s.size_unit,
    s.size_base,
    s.base_unit,
    s.pack_qty,
    s.is_bundle,
    coalesce(t.core_tokens, '') as core_tokens,
    s.brand_slug
        || '|' || coalesce(s.size_base::text || s.base_unit, 'nosize')
        || '|x' || s.pack_qty
        || '|' || coalesce(t.core_tokens, '') as match_key,
    s.last_seen_at
from sized as s
left join tokens as t using (listing_key)
