with bounds as (
    select
        least(
            (select min(crawl_date) from {{ ref('silver_price_observation') }}),
            (select min((started_at at time zone 'Asia/Jakarta')::date) from {{ ref('stg_crawl_run') }})
        ) as first_day,
        greatest(
            (select max(crawl_date) from {{ ref('silver_price_observation') }}),
            current_date
        ) + 30 as last_day
),

days as (
    select generate_series(first_day, last_day, interval '1 day')::date as date_day
    from bounds
)

select
    date_day                                                 as date,
    extract(isodow from date_day)::int                       as day_of_week,   -- 1 = Monday
    trim(to_char(date_day, 'Day'))                           as day_name,
    (array['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'])
        [extract(isodow from date_day)::int]                 as day_name_id,
    extract(isodow from date_day) in (6, 7)                  as is_weekend,
    extract(week from date_day)::int                         as iso_week,
    date_trunc('week', date_day)::date                       as week_start,
    extract(month from date_day)::int                        as month,
    trim(to_char(date_day, 'Month'))                         as month_name,
    extract(year from date_day)::int                         as year,
    -- Salaries in Indonesia usually land around the 25th; promos follow.
    extract(day from date_day) >= 25 or extract(day from date_day) <= 3 as is_payday_window,
    -- "Twin dates" (9.9, 10.10, 11.11 ...) are national online sale days.
    extract(day from date_day) = extract(month from date_day) as is_twin_date_sale
from days
