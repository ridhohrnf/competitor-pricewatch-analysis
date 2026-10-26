select recommendation_id, recommended_price, floor_price
from {{ source('jobs', 'fct_price_recommendation') }}
where recommended_price < floor_price
