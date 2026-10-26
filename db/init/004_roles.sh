#!/bin/bash
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v api_pw="$API_DB_PASSWORD" -v bi_pw="$BI_READER_PASSWORD" -v owner="$POSTGRES_USER" <<'SQL'
SELECT format('CREATE ROLE api_app LOGIN PASSWORD %L', :'api_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'api_app')\gexec
SELECT format('CREATE ROLE bi_reader LOGIN PASSWORD %L', :'bi_pw')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'bi_reader')\gexec

GRANT USAGE ON SCHEMA gold TO api_app, bi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO api_app, bi_reader;
-- Tables that dbt (re)creates later in gold are readable too.
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA gold
  GRANT SELECT ON TABLES TO api_app, bi_reader;

-- The one write the API needs: an admin can trigger a recommendation run.
GRANT INSERT ON gold.fct_price_recommendation TO api_app;
GRANT USAGE ON SEQUENCE gold.fct_price_recommendation_recommendation_id_seq TO api_app;
SQL
