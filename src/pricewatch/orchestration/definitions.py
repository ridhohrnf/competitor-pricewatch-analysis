import argparse
from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetSelection,
    AssetSpec,
    Definitions,
    MaterializeResult,
    ScheduleDefinition,
    asset,
    define_asset_job,
    multi_asset,
)
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets, get_asset_key_for_model

from pricewatch.cli import cmd_ingest
from pricewatch.db import connect
from pricewatch.recommender.job import run_recommendations

DBT_DIR = Path(__file__).resolve().parents[3] / "dbt"
RECOMMENDATION_REPORT = "report_price_recommendations"

dbt_project = DbtProject(project_dir=DBT_DIR, profiles_dir=DBT_DIR)


@multi_asset(
    specs=[AssetSpec(["raw", "crawl_run"]), AssetSpec(["raw", "product_listing"])],
    group_name="ingest",
)
def raw_layer(context: AssetExecutionContext):
    exit_code = cmd_ingest(argparse.Namespace(skip_live=False))
    if exit_code != 0:
        raise RuntimeError(f"ingest exited with {exit_code}")
    return None


@dbt_assets(manifest=dbt_project.manifest_path, exclude=RECOMMENDATION_REPORT)
def pricewatch_dbt(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


@asset(
    key=["jobs", "fct_price_recommendation"],
    deps=[
        get_asset_key_for_model([pricewatch_dbt], "fct_product_price_daily"),
        get_asset_key_for_model([pricewatch_dbt], "dim_product_master"),
    ],
    group_name="recommend",
)
def price_recommendations(context: AssetExecutionContext) -> MaterializeResult:
    with connect() as conn:
        result = run_recommendations(conn)
    if result["rows"] == 0:
        raise RuntimeError("recommendation run produced no rows")
    return MaterializeResult(
        metadata={"run_id": result["run_id"], "rows": result["rows"], **result["reasons"]}
    )


@dbt_assets(
    manifest=dbt_project.manifest_path,
    select=RECOMMENDATION_REPORT,
    name="recommendation_report",
)
def recommendation_report(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


daily_pipeline = define_asset_job("daily_pipeline", selection=AssetSelection.all())

defs = Definitions(
    assets=[raw_layer, pricewatch_dbt, price_recommendations, recommendation_report],
    jobs=[daily_pipeline],
    schedules=[
        ScheduleDefinition(
            job=daily_pipeline, cron_schedule="0 7 * * *", execution_timezone="Asia/Jakarta"
        )
    ],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
