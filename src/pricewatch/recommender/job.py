import uuid
from datetime import UTC, datetime

import psycopg
from psycopg.types.json import Jsonb

from pricewatch.logging import get_logger
from pricewatch.recommender.rules import MODEL_VERSION, Params, recommend

log = get_logger(__name__)

INPUTS = """
with prices as (
    select product_master_key, data_origin, platform, price_date, price
    from gold.fct_product_price_daily
),
as_of as (
    select product_master_key, data_origin, max(price_date) as as_of_date
    from prices group by 1, 2
),
latest_per_platform as (
    select distinct on (p.product_master_key, p.data_origin, p.platform)
           p.product_master_key, p.data_origin, p.platform, p.price
    from prices p join as_of a using (product_master_key, data_origin)
    where p.price_date > a.as_of_date - %(lookback_days)s
    order by p.product_master_key, p.data_origin, p.platform, p.price_date desc, p.price
),
cost_window as (
    select p.product_master_key, p.data_origin, min(p.price) as lowest_price
    from prices p join as_of a using (product_master_key, data_origin)
    where p.price_date > a.as_of_date - %(cost_window_days)s
    group by 1, 2
)
select a.product_master_key, a.data_origin, a.as_of_date,
       jsonb_object_agg(l.platform, l.price) as latest_by_platform,
       c.lowest_price
from as_of a
join latest_per_platform l using (product_master_key, data_origin)
join cost_window c using (product_master_key, data_origin)
group by a.product_master_key, a.data_origin, a.as_of_date, c.lowest_price
order by a.product_master_key, a.data_origin
"""

INSERT = """
insert into gold.fct_price_recommendation (
    run_id, model_version, run_at, as_of_date, product_master_key, data_origin,
    competitor_median_price, competitor_min_price, competitor_max_price, n_platforms,
    unit_cost_assumed, floor_price, recommended_price, reason_code, params
) values (
    %(run_id)s, %(model_version)s, %(run_at)s, %(as_of_date)s, %(product_master_key)s,
    %(data_origin)s, %(competitor_median_price)s, %(competitor_min_price)s,
    %(competitor_max_price)s, %(n_platforms)s, %(unit_cost_assumed)s, %(floor_price)s,
    %(recommended_price)s, %(reason_code)s, %(params)s
)
"""


def run_recommendations(conn: psycopg.Connection, params: Params | None = None) -> dict:
    params = params or Params()
    run_id = str(uuid.uuid4())
    run_at = datetime.now(UTC)
    rows = conn.execute(
        INPUTS, {"lookback_days": params.lookback_days, "cost_window_days": params.cost_window_days}
    ).fetchall()
    reasons: dict[str, int] = {}
    with conn.transaction():
        with conn.cursor() as cur:
            for master_key, origin, as_of_date, latest_by_platform, lowest in rows:
                rec = recommend(latest_by_platform, lowest, params)
                reasons[rec.reason_code] = reasons.get(rec.reason_code, 0) + 1
                cur.execute(
                    INSERT,
                    {
                        "run_id": run_id,
                        "model_version": MODEL_VERSION,
                        "run_at": run_at,
                        "as_of_date": as_of_date,
                        "product_master_key": master_key,
                        "data_origin": origin,
                        "params": Jsonb(params.as_dict()),
                        **rec.__dict__,
                    },
                )
    result = {
        "run_id": run_id,
        "model_version": MODEL_VERSION,
        "run_at": run_at.isoformat(),
        "rows": len(rows),
        "reasons": reasons,
    }
    log.info("recommendation_run_finished", **result)
    return result
