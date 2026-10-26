from dataclasses import dataclass
from datetime import date
from typing import Any

import psycopg
from psycopg.rows import dict_row


@dataclass
class Filters:
    clauses: list[str]
    params: dict[str, Any]

    @classmethod
    def build(cls, **conditions: tuple[str, Any]) -> "Filters":
        clauses, params = [], {}
        for name, (sql, value) in conditions.items():
            if value is not None:
                clauses.append(sql)
                params[name] = value
        return cls(clauses, params)

    @property
    def where(self) -> str:
        return ("where " + " and ".join(self.clauses)) if self.clauses else ""


class Repository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def _page(self, sql: str, filters: Filters, order_by: str, page: int, page_size: int):
        params = {**filters.params, "limit": page_size, "offset": (page - 1) * page_size}
        with self.conn.cursor(row_factory=dict_row) as cur:
            total = cur.execute(
                f"select count(*) as n from ({sql} {filters.where}) t", filters.params
            ).fetchone()["n"]
            rows = cur.execute(
                f"{sql} {filters.where} order by {order_by} limit %(limit)s offset %(offset)s",
                params,
            ).fetchall()
        return rows, total

    PRODUCTS = """
        select product_master_key, canonical_name, brand, category, size_value, size_unit,
               pack_qty, n_platforms_listed, data_origins, match_method
        from gold.dim_product_master
    """

    def list_products(
        self,
        brand: str | None,
        category: str | None,
        q: str | None,
        data_origin: str | None,
        page: int,
        page_size: int,
    ):
        filters = Filters.build(
            brand=("lower(brand) = lower(%(brand)s)", brand),
            category=("lower(category) = lower(%(category)s)", category),
            q=("canonical_name ilike %(q)s", f"%{q}%" if q else None),
            data_origin=("position(%(data_origin)s in data_origins) > 0", data_origin),
        )
        return self._page(self.PRODUCTS, filters, "brand, canonical_name", page, page_size)

    def get_product(self, product_master_key: str) -> dict | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            product = cur.execute(
                self.PRODUCTS + " where product_master_key = %(k)s", {"k": product_master_key}
            ).fetchone()
            if product is None:
                return None
            product["listings"] = cur.execute(
                """select distinct on (listing_key)
                          platform, listing_key, listing_name, data_origin,
                          price_date as last_price_date, price as last_price,
                          discount_pct as last_discount_pct
                   from gold.fct_product_price_daily
                   where product_master_key = %(k)s
                   order by listing_key, price_date desc""",
                {"k": product_master_key},
            ).fetchall()
        return product

    def list_prices(
        self,
        product_master_key: str | None,
        platform: str | None,
        data_origin: str | None,
        date_from: date | None,
        date_to: date | None,
        page: int,
        page_size: int,
    ):
        sql = """
            select price_date, platform, product_master_key, listing_key, listing_name,
                   price, original_price, discount_pct, is_discounted, data_origin
            from gold.fct_product_price_daily
        """
        filters = Filters.build(
            product_master_key=("product_master_key = %(product_master_key)s", product_master_key),
            platform=("platform = %(platform)s", platform),
            data_origin=("data_origin = %(data_origin)s", data_origin),
            date_from=("price_date >= %(date_from)s", date_from),
            date_to=("price_date <= %(date_to)s", date_to),
        )
        return self._page(sql, filters, "price_date desc, platform, listing_key", page, page_size)

    def latest_run_id(self) -> str | None:
        row = self.conn.execute(
            "select run_id::text from gold.fct_price_recommendation order by run_at desc limit 1"
        ).fetchone()
        return row[0] if row else None

    def list_recommendations(
        self,
        product_master_key: str | None,
        as_of_date: date | None,
        run_id: str | None,
        data_origin: str | None,
        page: int,
        page_size: int,
    ):
        sql = """
            select r.recommendation_id, r.run_id::text as run_id, r.model_version, r.run_at,
                   r.as_of_date, r.product_master_key, p.canonical_name, r.data_origin,
                   r.competitor_median_price, r.competitor_min_price, r.competitor_max_price,
                   r.n_platforms, r.floor_price, r.recommended_price, r.reason_code
            from gold.fct_price_recommendation r
            left join gold.dim_product_master p using (product_master_key)
        """
        filters = Filters.build(
            run_id=("r.run_id = %(run_id)s::uuid", run_id),
            product_master_key=(
                "r.product_master_key = %(product_master_key)s",
                product_master_key,
            ),
            as_of_date=("r.as_of_date = %(as_of_date)s", as_of_date),
            data_origin=("r.data_origin = %(data_origin)s", data_origin),
        )
        return self._page(sql, filters, "r.as_of_date desc, p.canonical_name", page, page_size)

    def platform_health(self) -> list[dict]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            return cur.execute(
                """select p.platform_code as platform, r.started_at as last_live_run_at,
                          r.status as last_live_status, r.items_valid as last_items_valid,
                          r.parse_success_rate as last_parse_success_rate
                   from gold.dim_platform p
                   left join lateral (
                       select * from gold.fct_crawl_run c
                       where c.platform = p.platform_code and c.data_origin = 'live'
                       order by c.started_at desc limit 1
                   ) r on true
                   order by p.platform_code"""
            ).fetchall()
