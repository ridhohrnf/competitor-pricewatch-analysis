"""P6: the incremental fct_product_price_daily must equal a full rebuild, row for row.

docker compose run --rm dev python scripts/proof/incremental_vs_full_refresh.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from pricewatch.db import connect  # noqa: E402

COLS = (
    "price_date, platform, product_master_key, listing_key, listing_name, price, "
    "original_price, discount_pct, is_discounted, n_observations, data_origin"
)


def dbt(*args: str) -> None:
    print("$ dbt", " ".join(args))
    subprocess.run(["dbt", *args, "--quiet"], cwd=ROOT / "dbt", check=True)


def snapshot(conn, name: str) -> None:
    conn.execute(f"drop table if exists public.{name}")
    conn.execute(f"create table public.{name} as select {COLS} from gold.fct_product_price_daily")
    conn.commit()


def main() -> None:
    with connect() as conn:
        before = conn.execute("select count(*) from gold.fct_product_price_daily").fetchone()[0]
        print(f"rows before: {before}")
        dbt(
            "build",
            "--select",
            "+fct_product_price_daily",
            "--exclude",
            "resource_type:test",
            "resource_type:unit_test",
        )
        snapshot(conn, "proof_fct_incremental")
        dbt("run", "--select", "fct_product_price_daily", "--full-refresh")
        snapshot(conn, "proof_fct_full")
        checks = conn.execute("""
            select 'rows (incremental)', count(*) from public.proof_fct_incremental
            union all select 'rows (full refresh)', count(*) from public.proof_fct_full
            union all select 'rows only in incremental', count(*) from (
                select * from public.proof_fct_incremental
                except select * from public.proof_fct_full) a
            union all select 'rows only in full refresh', count(*) from (
                select * from public.proof_fct_full
                except select * from public.proof_fct_incremental) b
        """).fetchall()
        for label, value in checks:
            print(f"{label:<28} {value}")
        conn.execute("drop table public.proof_fct_incremental; drop table public.proof_fct_full")
        conn.commit()
    differences = checks[2][1] + checks[3][1]
    print("RESULT:", "identical" if differences == 0 else f"{differences} differing rows")
    sys.exit(0 if differences == 0 else 1)


if __name__ == "__main__":
    main()
