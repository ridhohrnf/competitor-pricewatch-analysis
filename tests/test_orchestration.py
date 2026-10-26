import pytest

pytest.importorskip("dagster_dbt")

from dagster import AssetKey  # noqa: E402
from dagster_dbt import get_asset_key_for_model  # noqa: E402

from pricewatch.orchestration.definitions import (  # noqa: E402
    defs,
    pricewatch_dbt,
    recommendation_report,
)

RECOMMENDATIONS = AssetKey(["jobs", "fct_price_recommendation"])


def parents(key):
    return defs.resolve_asset_graph().get(key).parent_keys


def test_definitions_load():
    defs.resolve_job_def("daily_pipeline")


def test_dbt_reads_what_ingest_writes():
    staging = get_asset_key_for_model([pricewatch_dbt], "stg_product_listing")
    assert AssetKey(["raw", "product_listing"]) in parents(staging)


def test_recommendations_run_after_the_price_fact_and_before_their_report():
    fact = get_asset_key_for_model([pricewatch_dbt], "fct_product_price_daily")
    report = get_asset_key_for_model([recommendation_report], "report_price_recommendations")
    assert fact in parents(RECOMMENDATIONS)
    assert RECOMMENDATIONS in parents(report)


def test_daily_schedule_runs_in_jakarta_time():
    schedule = defs.resolve_schedule_def("daily_pipeline_schedule")
    assert schedule.execution_timezone == "Asia/Jakarta"
