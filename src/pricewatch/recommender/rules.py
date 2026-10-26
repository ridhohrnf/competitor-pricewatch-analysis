import math
import statistics
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

MODEL_VERSION = "median-minus-x-v1.0"


@dataclass(frozen=True)
class Params:
    undercut_pct: float = 0.03
    assumed_cost_ratio: float = 0.80
    min_margin_pct: float = 0.10
    lookback_days: int = 7
    cost_window_days: int = 30
    round_to: int = 100

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Recommendation:
    competitor_median_price: Decimal
    competitor_min_price: Decimal
    competitor_max_price: Decimal
    n_platforms: int
    unit_cost_assumed: Decimal
    floor_price: Decimal
    recommended_price: Decimal
    reason_code: str


def _money(value: float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def recommend(
    latest_price_by_platform: dict[str, float],
    lowest_price_in_cost_window: float,
    params: Params | None = None,
) -> Recommendation:
    params = params or Params()
    if not latest_price_by_platform:
        raise ValueError("need at least one competitor price")
    prices = [float(p) for p in latest_price_by_platform.values()]
    median = statistics.median(prices)
    candidate = median * (1 - params.undercut_pct)
    unit_cost = params.assumed_cost_ratio * float(lowest_price_in_cost_window)
    floor = unit_cost * (1 + params.min_margin_pct)
    recommended = math.ceil(max(candidate, floor) / params.round_to) * params.round_to

    if len(prices) < 2:
        reason = "single_platform_low_confidence"
    elif floor > candidate:
        reason = "margin_floor"
    else:
        reason = "median_minus_x"
    return Recommendation(
        competitor_median_price=_money(median),
        competitor_min_price=_money(min(prices)),
        competitor_max_price=_money(max(prices)),
        n_platforms=len(prices),
        unit_cost_assumed=_money(unit_cost),
        floor_price=_money(floor),
        recommended_price=_money(recommended),
        reason_code=reason,
    )
