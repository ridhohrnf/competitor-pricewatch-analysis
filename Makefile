DC  = docker compose
RUN = $(DC) run --rm dev
# Lint settings live here (no pyproject.toml): line length, rule families, Python version
RUFF = --line-length 100 --target-version py312 --extend-exclude dbt
RULES = --select E,F,I,B,UP

.PHONY: help up down reset logs ps ingest crawl load-landing sample load-sample \
        dbt-build dbt-test dbt-docs freshness recommend dashboard-export dashboard-import \
        orchestrator orchestrator-run proof \
        test test-integration lint format

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-17s %s\n", $$1, $$2}'

up:              ## start everything (db, ingest, dbt, recommender, API, Superset, dbt docs)
	$(DC) up -d --build

down:            ## stop containers (keeps the database volume)
	$(DC) down

reset:           ## stop and delete the database volume (landed HTML in data/ is kept)
	$(DC) down -v

logs:            ## follow the logs of all services
	$(DC) logs -f

ps:              ## status of every service
	$(DC) ps -a

ingest:          ## sample + backfill from landed HTML + rate-limited live crawl
	$(RUN) python -m pricewatch.cli ingest

crawl:           ## live crawl of Tokopedia (skipped if the last run is < 10 h old)
	$(RUN) python -m pricewatch.cli crawl --platform tokopedia

load-landing:    ## re-parse every landed HTML page into raw (no network)
	$(RUN) python -m pricewatch.cli load-landing

sample:          ## regenerate sample_data/ (deterministic, seed 42)
	$(RUN) python -m pricewatch.cli generate-sample

load-sample:     ## load sample_data/ into raw
	$(RUN) python -m pricewatch.cli load-sample

dbt-build:       ## seeds, models, snapshot and all tests
	$(RUN) sh -c "cd dbt && dbt build"

dbt-test:        ## dbt tests only
	$(RUN) sh -c "cd dbt && dbt test"

freshness:       ## source freshness of live crawls
	$(RUN) sh -c "cd dbt && dbt source freshness"

dbt-docs:        ## regenerate docs (served on :8080 by the dbt-docs service)
	$(RUN) sh -c "cd dbt && dbt docs generate"

recommend:       ## batch pricing recommendations (new run_id)
	$(RUN) python -m pricewatch.cli recommend

dashboard-export: ## write the dashboards built in the Superset UI to dashboards/superset/
	$(DC) exec superset sh -c "sh /scripts/export.sh"

dashboard-import: ## load dashboards/superset/ into a running Superset
	$(DC) run --rm superset-init

orchestrator:    ## bonus: Dagster UI on :3000 (same chain as `up`, as assets + daily schedule)
	$(DC) --profile orchestrator up -d --build dagster

orchestrator-run: ## bonus: run the whole Dagster job once, in the terminal
	$(DC) --profile orchestrator run --rm dagster sh -c 'mkdir -p $$DAGSTER_HOME && cd dbt && dbt parse --quiet && cd .. && dagster job execute -m pricewatch.orchestration.definitions -j daily_pipeline'

proof:           ## re-run the proof scripts (docs/proof.md)
	$(RUN) python scripts/proof/incremental_vs_full_refresh.py
	$(RUN) python scripts/proof/late_data_and_scd2.py

test:            ## unit + integration tests (Postgres must be up)
	$(RUN) pytest -q

test-integration: ## integration tests only
	$(RUN) pytest -q -m integration

lint:            ## ruff lint + format check
	$(RUN) sh -c "ruff check $(RULES) $(RUFF) . && ruff format $(RUFF) --check ."

format:          ## apply ruff formatting
	$(RUN) sh -c "ruff check --fix $(RULES) $(RUFF) . && ruff format $(RUFF) ."
