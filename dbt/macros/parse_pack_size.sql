{% macro parse_pack_size(name_column) -%}
left join lateral (
    select
        coalesce(m.multi[2], m.single[1])::numeric                         as size_value,
        coalesce(m.multi[3], m.single[2])                                  as size_unit,
        coalesce(m.multi[2], m.single[1])::numeric
            * case when coalesce(m.multi[3], m.single[2]) in ('l', 'lt', 'ltr', 'liter', 'kg')
                   then 1000 else 1 end                                    as size_base,
        case
            when coalesce(m.multi[3], m.single[2]) in ('ml', 'l', 'lt', 'ltr', 'liter') then 'ml'
            when coalesce(m.multi[3], m.single[2]) in ('g', 'gr', 'gram', 'kg') then 'g'
        end                                                                as base_unit,
        coalesce(
            m.multi[1]::int,
            m.after_size[3]::int,
            m.isi[1]::int,
            m.counted[1]::int,
            case when m.n ~ '\mtwin ?pack\M' then 2 end,
            1
        )                                                                  as pack_qty
    from (
        select
            n,
            regexp_match(n, '(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(ml|ltr|liter|lt|l|gram|gr|g|kg)\M') as multi,
            regexp_match(n, '(\d+(?:\.\d+)?)\s*(ml|ltr|liter|lt|l|gram|gr|g|kg)\M')              as single,
            regexp_match(n, '(\d+(?:\.\d+)?)\s*(ml|ltr|liter|lt|l|gram|gr|g|kg)\s*[x×]\s*(\d+)\M') as after_size,
            regexp_match(n, '\misi\s*(\d+)\M')                                                    as isi,
            regexp_match(n, '(\d+)\s*(pcs|pc|packs|pack|sachet)\M')                               as counted
        from (select lower(regexp_replace({{ name_column }}, '(\d),(\d)', '\1.\2', 'g')) as n) as normalized
    ) as m
) as pack_size on true
{%- endmacro %}
