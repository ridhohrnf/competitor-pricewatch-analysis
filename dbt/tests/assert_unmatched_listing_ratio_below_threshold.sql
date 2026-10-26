{{ config(severity='warn') }}

with sample as (
    select count(*) filter (where match_method = 'singleton')::numeric / nullif(count(*), 0) as ratio
    from {{ ref('silver_product_match') }}
    where data_origin = 'sample'
)
select ratio from sample where ratio > {{ var("max_unmatched_sample_ratio") }}
