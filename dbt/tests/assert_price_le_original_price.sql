select price_date, listing_key, price, original_price
from {{ ref('fct_product_price_daily') }}
where price > original_price
