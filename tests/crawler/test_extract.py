import re

from pricewatch.crawler.extract import extract, extract_apollo, extract_dom, load_apollo_cache

BASE = "https://www.tokopedia.com"


def tokopedia(selectors):
    return selectors["tokopedia"]["strategies"]


def test_apollo_strategy_reads_every_product_and_follows_pointers(selectors, shop_html):
    products = extract_apollo(shop_html, tokopedia(selectors)[0])
    assert [p["price_text"] for p in products] == ["Rp15.000", "Rp42.500", "Rp99.000"]
    assert products[0]["original_price_text"] == "Rp20.000"
    assert products[0]["source_discounted_percentage"] == "0"
    assert products[0]["detail"]["rating"] == "4.9"


def test_objects_of_another_type_are_not_products(selectors, shop_html):
    names = [p["name"] for p in extract_apollo(shop_html, tokopedia(selectors)[0])]
    assert "not a product" not in names


def test_empty_original_price_becomes_none_not_an_empty_string(selectors, shop_html):
    products = extract_apollo(shop_html, tokopedia(selectors)[0])
    assert products[1]["original_price_text"] is None


def test_listing_id_is_the_url_slug_for_old_and_new_style_urls(selectors, shop_html):
    ids = [p["external_product_id"] for p in extract_apollo(shop_html, tokopedia(selectors)[0])]
    assert (
        ids[0]
        == "contoh-sabun-cuci-piring-jeruk-nipis-750ml-1700000000000000001-1700000000000000002"
    )
    assert ids[1] == "contoh-deterjen-bubuk-800-g-isi-2"


def test_json_product_id_is_kept_only_for_audit(selectors, shop_html):
    product = extract_apollo(shop_html, tokopedia(selectors)[0])[0]
    assert product["source_product_id"] == "111"


def test_source_url_drops_the_tracking_query_that_robots_txt_disallows(selectors, shop_html):
    for product in extract_apollo(shop_html, tokopedia(selectors)[0]):
        assert "?" not in product["source_url"]
        assert "extParam" not in product["source_url"]


def test_closing_brace_inside_a_product_name_does_not_cut_the_json(selectors, shop_html):
    names = [p["name"] for p in extract_apollo(shop_html, tokopedia(selectors)[0])]
    assert "Contoh Paket Promo }; Hemat" in names


def test_truncated_json_is_treated_as_missing_instead_of_crashing():
    assert (
        load_apollo_cache('<script>window.__cache = {"a": {"name": "Rin', "window.__cache") is None
    )


def test_dom_fallback_finds_products_when_the_json_is_gone(selectors, shop_html):
    without_json = re.sub(r"<script>.*?</script>", "", shop_html, flags=re.S)
    products, strategy = extract(without_json, tokopedia(selectors), BASE)
    assert strategy == "dom_semantic"
    assert [p["name"] for p in products] == [
        "Contoh Sabun Cuci Piring Jeruk Nipis 750ml",
        "Contoh Deterjen Bubuk 800 g isi 2",
    ]
    assert products[0]["price_text"] == "Rp15.000"
    assert products[0]["original_price_text"] == "Rp20.000"
    assert products[0]["discount_text"] == "25%"


def test_both_strategies_give_the_same_listing_id(selectors, shop_html):
    from_json = extract_apollo(shop_html, tokopedia(selectors)[0])
    from_dom = extract_dom(shop_html, tokopedia(selectors)[1], BASE)
    assert {p["external_product_id"] for p in from_dom} <= {
        p["external_product_id"] for p in from_json
    }


def test_json_strategy_wins_when_both_are_available(selectors, shop_html):
    _, strategy = extract(shop_html, tokopedia(selectors), BASE)
    assert strategy == "apollo_cache"


def test_page_with_no_known_structure_returns_nothing(selectors):
    products, strategy = extract(
        "<html><body>Maintenance</body></html>", tokopedia(selectors), BASE
    )
    assert products == [] and strategy == "none"
