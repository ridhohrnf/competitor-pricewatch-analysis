from pricewatch.crawler.models import validate_payload

GOOD = {
    "external_product_id": "super-pell-pembersih-lantai-lemon-770ml",
    "name": "Super Pell Pembersih Lantai Lemon 770ml",
    "price_text": "Rp12.000",
    "original_price_text": "Rp16.000",
    "source_discounted_percentage": "0",
    "source_url": "https://www.tokopedia.com/unilever-official-store/super-pell-contoh",
}


def test_complete_record_is_valid():
    is_valid, result = validate_payload({**GOOD, "source_discounted_percentage": None})
    assert is_valid and result == {"errors": [], "warnings": []}


def test_missing_price_makes_the_record_invalid():
    is_valid, result = validate_payload({**GOOD, "price_text": None})
    assert not is_valid
    assert any(e.startswith("price_text") for e in result["errors"])


def test_price_that_is_not_rupiah_text_is_invalid():
    is_valid, result = validate_payload({**GOOD, "price_text": "24.200"})
    assert not is_valid


def test_name_shorter_than_three_characters_is_invalid():
    is_valid, _ = validate_payload({**GOOD, "name": "AB"})
    assert not is_valid


def test_source_discount_of_zero_with_a_strikethrough_price_is_a_warning_not_an_error():
    is_valid, result = validate_payload(GOOD)
    assert is_valid
    assert result["warnings"] == ["source_discount_mismatch:source=0,computed=25.0"]


def test_original_price_below_price_is_flagged():
    is_valid, result = validate_payload({**GOOD, "original_price_text": "Rp10.000"})
    assert is_valid
    assert "original_price_below_price" in result["warnings"]


def test_implausible_price_is_flagged():
    _, result = validate_payload({**GOOD, "price_text": "Rp100", "original_price_text": None})
    assert result["warnings"] == ["price_out_of_range:100"]
