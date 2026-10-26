import json
import re
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

Payload = dict[str, Any]


def strip_query(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def id_from_url(url: str | None, pattern: str) -> str | None:
    if not url:
        return None
    match = re.search(pattern, urlsplit(url).path)
    return match.group(1) if match else None


def make_payload(fields: dict[str, Any], strategy: str) -> Payload:
    return {
        "external_product_id": _text(fields.get("external_product_id")),
        "source_product_id": _text(fields.get("source_product_id")),
        "name": _text(fields.get("name")),
        "price_text": _text(fields.get("price_text")),
        "original_price_text": _text(fields.get("original_price_text")),
        "discount_text": _text(fields.get("discount_text")),
        "source_discounted_percentage": _text(fields.get("source_discounted_percentage")),
        "source_url": strip_query(_text(fields.get("source_url"))),
        "detail": {
            "rating": _text(fields.get("rating")),
            "review_count": _text(fields.get("review_count")),
            "image_url": _text(fields.get("image_url")),
        },
        "strategy": strategy,
    }


def load_apollo_cache(html: str, marker: str) -> dict[str, Any] | None:
    start = html.find(marker)
    if start == -1:
        return None
    brace = html.find("{", start)
    if brace == -1:
        return None
    try:
        cache, _ = json.JSONDecoder().raw_decode(html, brace)
    except json.JSONDecodeError:
        return None
    return cache if isinstance(cache, dict) else None


def resolve_ref(cache: dict[str, Any], value: Any) -> Any:
    if isinstance(value, dict) and value.get("type") == "id" and "id" in value:
        return cache.get(value["id"])
    return value


def get_path(obj: Any, path: str, cache: dict[str, Any]) -> Any:
    current = obj
    for key in path.split("."):
        current = resolve_ref(cache, current)
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return resolve_ref(cache, current)


def extract_apollo(html: str, strategy: dict[str, Any]) -> list[Payload]:
    cache = load_apollo_cache(html, strategy["marker"])
    if cache is None:
        return []
    items = [
        value
        for value in cache.values()
        if isinstance(value, dict) and value.get("__typename") == strategy["item_typename"]
    ]
    payloads = []
    for item in items:
        fields = {field: get_path(item, path, cache) for field, path in strategy["fields"].items()}
        fields["external_product_id"] = id_from_url(
            fields.get("source_url"), strategy["id_from_url_pattern"]
        )
        payloads.append(make_payload(fields, strategy["name"]))
    return payloads


def _find_card(anchor: Tag, link_selector: str, price_re: re.Pattern) -> Tag | None:
    for parent in anchor.parents:
        if not isinstance(parent, Tag) or parent.name in ("body", "html"):
            return None
        has_link = parent.select_one(link_selector) is not None
        if has_link and any(price_re.match(t) for t in parent.stripped_strings):
            return parent
    return None


def extract_dom(html: str, strategy: dict[str, Any], base_url: str) -> list[Payload]:
    soup = BeautifulSoup(html, "lxml")
    price_re = re.compile(strategy["price_pattern"])
    discount_re = re.compile(strategy["discount_pattern"])

    payloads: list[Payload] = []
    seen_ids: set[str] = set()
    for anchor in soup.select(strategy["card_anchor"]):
        card = _find_card(anchor, strategy["link_selector"], price_re)
        if card is None:
            continue
        link = card.select_one(strategy["link_selector"])
        url = urljoin(base_url, link["href"]) if link and link.has_attr("href") else None
        product_id = id_from_url(url, strategy["id_from_url_pattern"]) or strip_query(url)
        if not product_id or product_id in seen_ids:
            continue
        seen_ids.add(product_id)

        texts = list(card.stripped_strings)
        prices = [t for t in texts if price_re.match(t)]
        discounts = [t for t in texts if discount_re.match(t)]
        others = [t for t in texts if t not in prices and t not in discounts]
        image = card.select_one("img[alt]")
        name = max(others, key=len) if others else (image.get("alt") if image else None)
        payloads.append(
            make_payload(
                {
                    "external_product_id": product_id,
                    "name": name,
                    "price_text": prices[0] if prices else None,
                    "original_price_text": prices[1] if len(prices) > 1 else None,
                    "discount_text": discounts[0] if discounts else None,
                    "source_url": url,
                    "image_url": image.get("src") if image else None,
                },
                strategy["name"],
            )
        )
    return payloads


def extract(
    html: str, strategies: list[dict[str, Any]], base_url: str
) -> tuple[list[Payload], str]:
    for strategy in strategies:
        if strategy["type"] == "apollo":
            payloads = extract_apollo(html, strategy)
        elif strategy["type"] == "dom":
            payloads = extract_dom(html, strategy, base_url)
        else:
            raise ValueError(f"unknown strategy type: {strategy['type']}")
        if payloads:
            return payloads, strategy["name"]
    return [], "none"
