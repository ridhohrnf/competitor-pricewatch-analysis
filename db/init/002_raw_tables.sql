CREATE TABLE IF NOT EXISTS raw.crawl_run (
    run_id             uuid PRIMARY KEY,
    platform           text NOT NULL,
    crawler_version    text NOT NULL,
    data_origin        text NOT NULL CHECK (data_origin IN ('live', 'sample')),
    started_at         timestamptz NOT NULL,
    finished_at        timestamptz,
    status             text NOT NULL
                       CHECK (status IN ('running', 'success', 'degraded', 'failed', 'blocked')),
    pages_fetched      int,
    items_seen         int,
    items_valid        int,
    items_invalid      int,
    parse_success_rate numeric(5, 4),
    strategy_used      text,
    error_message      text,
    inserted_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw.product_listing (
    id                  bigserial PRIMARY KEY,
    run_id              uuid NOT NULL REFERENCES raw.crawl_run (run_id),
    platform            text NOT NULL,
    external_product_id text NOT NULL,
    source_url          text,
    crawled_at          timestamptz NOT NULL,
    crawl_date          date NOT NULL,
    crawler_version     text NOT NULL,
    data_origin         text NOT NULL CHECK (data_origin IN ('live', 'sample')),
    payload             jsonb NOT NULL,
    payload_hash        char(64) NOT NULL,
    page_html_hash      char(64),
    is_valid            boolean NOT NULL,
    validation_errors   jsonb,
    inserted_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (platform, external_product_id, crawl_date, payload_hash)
);

CREATE INDEX IF NOT EXISTS product_listing_inserted_at_idx ON raw.product_listing (inserted_at);
CREATE INDEX IF NOT EXISTS product_listing_run_idx ON raw.product_listing (run_id);
