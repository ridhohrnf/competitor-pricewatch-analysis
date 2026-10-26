with attributes as (
    select * from {{ ref('silver_listing_attributes') }}
),

assigned as (
    select
        a.listing_key,
        a.platform,
        a.data_origin,
        coalesce(target.match_key, a.match_key) as master_key,
        target.match_key is not null            as is_seeded
    from attributes as a
    left join {{ ref('product_mapping') }} as pm on pm.listing_key = a.listing_key
    left join attributes as target on target.listing_key = pm.same_as_listing_key
),

master_spread as (
    select
        master_key,
        count(distinct platform) as n_platforms,
        bool_or(is_seeded)       as has_seed
    from assigned
    group by master_key
)

select
    a.listing_key,
    a.platform,
    a.data_origin,
    a.master_key,
    md5(a.master_key) as product_master_key,
    case

        when a.is_seeded or (ms.has_seed and ms.n_platforms > 1) then 'manual_seed'
        when ms.n_platforms > 1 then 'rule_key'
        else 'singleton'
    end as match_method
from assigned as a
inner join master_spread as ms using (master_key)
