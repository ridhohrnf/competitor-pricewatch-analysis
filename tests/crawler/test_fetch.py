import httpx
import pytest
import respx

from pricewatch.crawler.fetch import BlockedError, CrawlError, DisallowedError, PoliteClient

TOKOPEDIA_ROBOTS = (
    "User-agent: *\nDisallow: /graphql\nDisallow: /search?*\nDisallow: /*?extParam=\n"
)
SHOP = "https://www.tokopedia.com/unilever-official-store/product"
ROBOTS = "https://www.tokopedia.com/robots.txt"


def make_client(sleeps=None, max_attempts=3):
    sleeps = sleeps if sleeps is not None else []
    return PoliteClient(
        "pricewatch-test/0.1",
        delay_seconds=3.0,
        jitter_seconds=0.0,
        max_attempts=max_attempts,
        sleep=sleeps.append,
    )


@respx.mock
def test_url_with_tracking_query_is_refused_by_robots_and_never_requested():
    respx.get(ROBOTS).respond(200, text=TOKOPEDIA_ROBOTS)
    page = respx.get(url__startswith="https://www.tokopedia.com/unilever-official-store/x")
    with pytest.raises(DisallowedError):
        make_client().get("https://www.tokopedia.com/unilever-official-store/x?extParam=src")
    assert page.call_count == 0


@respx.mock
def test_the_shop_listing_page_is_allowed():
    respx.get(ROBOTS).respond(200, text=TOKOPEDIA_ROBOTS)
    assert make_client().is_allowed(SHOP)


@respx.mock
def test_missing_robots_txt_means_everything_is_allowed():
    respx.get(ROBOTS).respond(404)
    assert make_client().is_allowed(SHOP + "?extParam=src")


@respx.mock
def test_robots_txt_server_error_means_everything_is_disallowed():
    respx.get(ROBOTS).respond(503)
    assert not make_client().is_allowed(SHOP)


@respx.mock
def test_robots_txt_that_answers_403_means_blocked():
    respx.get(ROBOTS).respond(403)
    with pytest.raises(BlockedError):
        make_client().is_allowed(SHOP)


@respx.mock
def test_robots_txt_is_fetched_once_per_host():
    robots = respx.get(ROBOTS).respond(200, text="")
    respx.get(SHOP).respond(200, text="ok")
    client = make_client()
    client.get(SHOP)
    client.get(SHOP)
    assert robots.call_count == 1


@respx.mock
def test_server_error_is_retried_until_max_attempts():
    respx.get(ROBOTS).respond(200, text="")
    page = respx.get(SHOP).mock(return_value=httpx.Response(503))
    with pytest.raises(CrawlError, match="503"):
        make_client(max_attempts=3).get(SHOP)
    assert page.call_count == 3


@respx.mock
def test_temporary_error_then_success_returns_the_bytes_as_received():
    respx.get(ROBOTS).respond(200, text="")
    respx.get(SHOP).mock(side_effect=[httpx.Response(429), httpx.Response(200, text="<html>ok")])
    assert make_client().get(SHOP).content == b"<html>ok"


@respx.mock
def test_retry_waits_longer_each_time():
    respx.get(ROBOTS).respond(200, text="")
    respx.get(SHOP).mock(return_value=httpx.Response(503))
    sleeps: list[float] = []
    with pytest.raises(CrawlError):
        make_client(sleeps, max_attempts=3).get(SHOP)
    backoffs = [s for s in sleeps if s >= 2.0 and s < 3.0] + [s for s in sleeps if s >= 4.0]
    assert any(2.0 <= s < 3.0 for s in backoffs) and any(4.0 <= s < 5.0 for s in backoffs)


@respx.mock
def test_403_stops_immediately_without_retrying():
    respx.get(ROBOTS).respond(200, text="")
    page = respx.get(SHOP).respond(403)
    with pytest.raises(BlockedError):
        make_client().get(SHOP)
    assert page.call_count == 1


@respx.mock
def test_404_is_permanent_and_not_retried():
    respx.get(ROBOTS).respond(200, text="")
    page = respx.get(SHOP).respond(404)
    with pytest.raises(CrawlError):
        make_client().get(SHOP)
    assert page.call_count == 1


@respx.mock
def test_redirect_is_not_followed_because_the_target_skips_the_robots_check():
    respx.get(ROBOTS).respond(200, text="")
    respx.get(SHOP).respond(302, headers={"Location": "https://www.tokopedia.com/login"})
    with pytest.raises(CrawlError, match="302"):
        make_client().get(SHOP)


@respx.mock
def test_bot_check_page_is_treated_as_blocked_even_with_status_200():
    respx.get(ROBOTS).respond(200, text="")
    respx.get(SHOP).respond(200, text="<title>Just a moment...</title> verify you are human")
    with pytest.raises(BlockedError):
        make_client().get(SHOP)


@respx.mock
def test_big_real_page_that_mentions_captcha_in_its_scripts_is_not_a_bot_check():
    respx.get(ROBOTS).respond(200, text="")
    respx.get(SHOP).respond(200, text="x" * 200_000 + "recaptcha-config")
    assert len(make_client().get(SHOP).content) > 200_000


@respx.mock
def test_requests_to_the_same_host_are_spaced_by_the_configured_delay():
    respx.get(ROBOTS).respond(200, text="")
    respx.get(SHOP).respond(200, text="ok")
    sleeps: list[float] = []
    client = make_client(sleeps)
    client.get(SHOP)
    client.get(SHOP)
    assert len(sleeps) == 2 and all(2.9 < s <= 3.0 for s in sleeps)
