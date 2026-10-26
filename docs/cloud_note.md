# Cloud note (bonus): the same design on AWS

| Here | On AWS | Why this service |
|---|---|---|
| `data/landing/` (raw HTML) | **S3** `landing/platform=…/date=…/run_id=…/`, lifecycle rule to Glacier after 90 days | Cheap, durable bronze; backfill works exactly like `load-landing` |
| `raw` schema (append-only) | **Iceberg** tables on S3 in the **Glue Data Catalog**, partitioned by `crawl_date` | `MERGE … WHEN NOT MATCHED` gives the same idempotent load as `ON CONFLICT DO NOTHING` |
| dbt on Postgres | **dbt-athena** on Iceberg; Redshift Serverless if BI concurrency grows | Serverless, same models and tests |
| dbt snapshot | dbt snapshot on Iceberg (or table time travel for audits) | SCD2 unchanged |
| Crawler container | **ECS Fargate** scheduled task with a fixed egress IP | One run a day matches the crawl limit |
| Compose ordering / Dagster | **Dagster** on ECS (or Dagster+), or **MWAA** if the team already runs Airflow | Retries, alerts and run history |
| Postgres gold for the API | **RDS PostgreSQL** with gold exported, or the API reading Athena through a cache | The API needs low-latency lookups |
| FastAPI | **ECS Fargate** behind an **ALB**; **Cognito** tokens instead of demo users | Managed auth replaces the user list; the role check stays |
| Superset | Superset on ECS, or **QuickSight** on Athena | Same report tables |
| `.env` secrets | **Secrets Manager** | Rotation, no secrets in task definitions |
| `crawl_run_unhealthy` log | **CloudWatch** metric filter on the JSON log, alarm on parse success < 90% → SNS / Slack | The structured logs were designed for this |
| DB roles (`api_app`, `bi_reader`) | **Lake Formation** grants on gold only | Least privilege enforced by the platform |

Alibaba Cloud equivalents: OSS, MaxCompute or Hologres, DataWorks scheduling, SAE for containers,
RDS PostgreSQL, KMS / Secrets Manager, CloudMonitor.
