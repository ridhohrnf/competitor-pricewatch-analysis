from datetime import UTC, datetime

from pricewatch.crawler.health import RunStats, run_status
from pricewatch.crawler.loader import payload_hash, wib_date

PAYLOAD = {
    "external_product_id": "rinso-770g",
    "name": "Rinso Anti Noda 770g",
    "price_text": "Rp25.000",
    "original_price_text": "Rp30.000",
    "detail": {"image_url": "https://img/1.jpg?x-signature=AAA", "rating": "4.8"},
}


def test_hash_ignores_rotating_image_signatures_and_ratings():
    other = {
        **PAYLOAD,
        "detail": {"image_url": "https://img/1.jpg?x-signature=BBB", "rating": "4.9"},
    }
    assert payload_hash(PAYLOAD) == payload_hash(other)


def test_hash_changes_when_the_price_changes():
    assert payload_hash(PAYLOAD) != payload_hash({**PAYLOAD, "price_text": "Rp24.000"})


def test_crawl_just_after_midnight_in_jakarta_belongs_to_that_jakarta_day():
    assert wib_date(datetime(2026, 10, 18, 17, 30, tzinfo=UTC)).isoformat() == "2026-10-19"


def stats(seen, valid):
    return RunStats(pages_fetched=1, items_seen=seen, items_valid=valid)


def test_run_with_enough_valid_items_is_success():
    assert run_status(stats(80, 80), 0.9, 40, blocked=False) == "success"


def test_low_parse_rate_is_degraded():
    assert run_status(stats(80, 60), 0.9, 40, blocked=False) == "degraded"


def test_too_few_items_is_degraded_even_if_all_are_valid():
    assert run_status(stats(10, 10), 0.9, 40, blocked=False) == "degraded"


def test_no_items_at_all_is_failed():
    assert run_status(stats(0, 0), 0.9, 40, blocked=False) == "failed"


def test_blocked_wins_over_everything_else():
    assert run_status(stats(0, 0), 0.9, 40, blocked=True) == "blocked"
