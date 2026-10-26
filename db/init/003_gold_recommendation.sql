CREATE TABLE IF NOT EXISTS gold.fct_price_recommendation (
    recommendation_id       bigserial PRIMARY KEY,
    run_id                  uuid NOT NULL,
    model_version           text NOT NULL,
    run_at                  timestamptz NOT NULL,
    as_of_date              date NOT NULL,
    product_master_key      text NOT NULL,
    data_origin             text NOT NULL,
    competitor_median_price numeric(14, 2) NOT NULL,
    competitor_min_price    numeric(14, 2) NOT NULL,
    competitor_max_price    numeric(14, 2) NOT NULL,
    n_platforms             int NOT NULL,
    unit_cost_assumed       numeric(14, 2) NOT NULL,
    floor_price             numeric(14, 2) NOT NULL,
    recommended_price       numeric(14, 2) NOT NULL,
    reason_code             text NOT NULL,
    params                  jsonb NOT NULL,
    UNIQUE (run_id, product_master_key, data_origin)
);

CREATE INDEX IF NOT EXISTS fct_price_recommendation_lookup_idx
    ON gold.fct_price_recommendation (product_master_key, as_of_date);
