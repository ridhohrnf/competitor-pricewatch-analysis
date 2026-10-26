from decimal import Decimal

import pytest

from pricewatch.recommender.rules import Params, recommend


def test_price_is_the_competitor_median_minus_three_percent_rounded_up_to_100():
    rec = recommend({"tokopedia": 25000, "klikindomaret": 26000, "blibli": 24000}, 24000)
    assert rec.competitor_median_price == Decimal("25000.00")
    assert rec.recommended_price == Decimal("24300.00")
    assert rec.reason_code == "median_minus_x"


def test_median_of_two_platforms_is_their_average():
    rec = recommend({"tokopedia": 20000, "blibli": 30000}, 20000)
    assert rec.competitor_median_price == Decimal("25000.00")


def test_margin_floor_wins_when_the_undercut_would_go_below_it():
    rec = recommend({"tokopedia": 10000, "blibli": 10000}, 13000)
    assert rec.floor_price == Decimal("11440.00")
    assert rec.recommended_price == Decimal("11500.00")
    assert rec.reason_code == "margin_floor"


def test_rounding_never_lands_below_the_floor():
    rec = recommend({"a": 1000, "b": 1000}, 1137)
    assert rec.recommended_price >= rec.floor_price


def test_single_platform_is_flagged_as_low_confidence():
    rec = recommend({"tokopedia": 15000}, 15000)
    assert rec.n_platforms == 1
    assert rec.reason_code == "single_platform_low_confidence"


def test_min_and_max_competitor_prices_are_reported():
    rec = recommend({"a": 9000, "b": 12000, "c": 10000}, 9000)
    assert (rec.competitor_min_price, rec.competitor_max_price) == (
        Decimal("9000.00"),
        Decimal("12000.00"),
    )


def test_parameters_change_the_result():
    rec = recommend({"a": 10000, "b": 10000}, 9000, Params(undercut_pct=0.10))
    assert rec.recommended_price == Decimal("9000.00")


def test_no_competitor_price_is_an_error():
    with pytest.raises(ValueError):
        recommend({}, 1000)
