from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

DataOrigin = Literal["live", "sample"]
Platform = Literal["tokopedia", "klikindomaret", "blibli"]


class Page[T](BaseModel):
    items: list[T]
    page: int
    page_size: int
    total: int


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int
    role: str


class Product(BaseModel):
    product_master_key: str
    canonical_name: str
    brand: str
    category: str | None
    size_value: Decimal | None
    size_unit: str | None
    pack_qty: int
    n_platforms_listed: int
    data_origins: str


class ProductListing(BaseModel):
    platform: str
    listing_key: str
    listing_name: str
    data_origin: DataOrigin
    last_price_date: date
    last_price: Decimal
    last_discount_pct: Decimal


class ProductDetail(Product):
    match_method: str
    listings: list[ProductListing]


class PricePoint(BaseModel):
    price_date: date
    platform: str
    product_master_key: str
    listing_key: str
    listing_name: str
    price: Decimal
    original_price: Decimal
    discount_pct: Decimal
    is_discounted: bool
    data_origin: DataOrigin


class Recommendation(BaseModel):
    recommendation_id: int
    run_id: str
    model_version: str
    run_at: datetime
    as_of_date: date
    product_master_key: str
    canonical_name: str | None
    data_origin: DataOrigin
    competitor_median_price: Decimal
    competitor_min_price: Decimal
    competitor_max_price: Decimal
    n_platforms: int
    floor_price: Decimal
    recommended_price: Decimal
    reason_code: str


class RunResult(BaseModel):
    run_id: str
    model_version: str
    run_at: str
    rows: int
    reasons: dict[str, int]


class PlatformHealth(BaseModel):
    platform: str
    last_live_run_at: datetime | None
    last_live_status: str | None
    last_items_valid: int | None
    last_parse_success_rate: Decimal | None


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unreachable"]
    platforms: list[PlatformHealth] = Field(default_factory=list)
