from pathlib import Path

import pytest

from pricewatch.settings import load_selectors

ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def selectors():
    return load_selectors(ROOT / "config" / "selectors.yaml")


@pytest.fixture
def shop_html():
    return (FIXTURES / "tokopedia_shop_page.html").read_text(encoding="utf-8")
