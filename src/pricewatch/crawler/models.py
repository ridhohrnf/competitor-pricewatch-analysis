import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

PRICE_TEXT_RE = re.compile(r"^Rp\s?[\d.]+$")
MIN_PRICE, MAX_PRICE = 500, 5_000_000
DISCOUNT_TOLERANCE_POINTS = 2


class ProductRecord(BaseModel):
    external_product_id: str = Field(min_length=1)
    name: str = Field(min_length=3)
    price_text: str
    source_url: str = Field(min_length=1)
    original_price_text: str | None = None
    discount_text: str | None = None
    source_discounted_percentage: str | None = None

    @field_validator("price_text", "original_price_text")
    @classmethod
    def looks_like_rupiah(cls, value: str | None) -> str | None:
        if value is not None and not PRICE_TEXT_RE.match(value):
            raise ValueError(f"not a rupiah price: {value!r}")
        return value


def rupiah_to_int(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def check_warnings(record: ProductRecord) -> list[str]:
    warnings = []
    price = rupiah_to_int(record.price_text)
    original = rupiah_to_int(record.original_price_text)
    if price is not None and not MIN_PRICE <= price <= MAX_PRICE:
        warnings.append(f"price_out_of_range:{price}")
    if price is not None and original is not None:
        if original < price:
            warnings.append("original_price_below_price")
        elif original > 0 and record.source_discounted_percentage is not None:
            computed = (original - price) / original * 100
            try:
                source = float(record.source_discounted_percentage)
            except ValueError:
                source = None
            if source is not None and abs(computed - source) > DISCOUNT_TOLERANCE_POINTS:
                warnings.append(
                    f"source_discount_mismatch:source={source:g},computed={computed:.1f}"
                )
    return warnings


def validate_payload(payload: dict[str, Any]) -> tuple[bool, dict[str, list[str]]]:
    try:
        record = ProductRecord(
            **{k: v for k, v in payload.items() if k in ProductRecord.model_fields}
        )
    except ValidationError as exc:
        errors = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        return False, {"errors": errors, "warnings": []}
    return True, {"errors": [], "warnings": check_warnings(record)}
