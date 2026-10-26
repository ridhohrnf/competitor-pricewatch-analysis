import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from protego import Protego

from pricewatch.logging import get_logger

log = get_logger(__name__)

TRANSIENT_STATUS = {429, 500, 502, 503, 504}

CHALLENGE_MARKERS = ("verify you are human", "cf-chl", "challenge-platform", "captcha")
CHALLENGE_MAX_BYTES = 100_000


class CrawlError(Exception):
    pass


class BlockedError(CrawlError):
    pass


class DisallowedError(CrawlError):
    pass


@dataclass
class FetchResult:
    url: str
    content: bytes
    fetched_at: datetime


def looks_like_challenge(content: bytes) -> bool:
    if len(content) > CHALLENGE_MAX_BYTES:
        return False
    lowered = content.decode("utf-8", errors="replace").lower()
    return any(marker in lowered for marker in CHALLENGE_MARKERS)


class PoliteClient:
    def __init__(
        self,
        user_agent: str,
        timeout_seconds: float = 20,
        delay_seconds: float = 3.0,
        jitter_seconds: float = 1.5,
        max_attempts: int = 3,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.jitter_seconds = jitter_seconds
        self.max_attempts = max_attempts
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent}, timeout=timeout_seconds
        )
        self._sleep = sleep
        self._robots: dict[str, Protego] = {}
        self._last_request_at: float | None = None

    def close(self) -> None:
        self._client.close()

    def is_allowed(self, url: str) -> bool:
        origin = _origin(url)
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        return self._robots[origin].can_fetch(url, self.user_agent)

    def _load_robots(self, origin: str) -> Protego:
        response = self._request(f"{origin}/robots.txt")
        log.info("robots_fetched", origin=origin, status_code=response.status_code)
        if response.status_code in (401, 403):
            raise BlockedError(f"robots.txt answered HTTP {response.status_code}")
        if response.status_code >= 500:
            return Protego.parse("User-agent: *\nDisallow: /")
        if response.status_code >= 400:
            return Protego.parse("")
        return Protego.parse(response.text)

    def get(self, url: str) -> FetchResult:
        if not self.is_allowed(url):
            log.warning("url_disallowed_by_robots", url=url)
            raise DisallowedError(url)

        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._request(url)
            except httpx.TransportError as exc:
                reason = type(exc).__name__
            else:
                status = response.status_code
                log.info("page_fetched", url=url, status_code=status, bytes=len(response.content))
                if status in (401, 403):
                    raise BlockedError(f"HTTP {status}")
                if status not in TRANSIENT_STATUS:
                    if status >= 300:
                        raise CrawlError(f"HTTP {status}")
                    if looks_like_challenge(response.content):
                        raise BlockedError("bot-check / verification page")
                    return FetchResult(url, response.content, datetime.now(UTC))
                reason = f"HTTP {status}"

            if attempt < self.max_attempts:
                wait = 2**attempt + random.uniform(0, 1)
                log.warning("fetch_retry", url=url, reason=reason, attempt=attempt, wait=wait)
                self._sleep(wait)

        raise CrawlError(f"gave up after {self.max_attempts} attempts: {reason}")

    def _request(self, url: str) -> httpx.Response:
        if self._last_request_at is not None:
            wanted = self.delay_seconds + random.uniform(0, self.jitter_seconds)
            remaining = wanted - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                self._sleep(remaining)
        try:
            return self._client.get(url)
        finally:
            self._last_request_at = time.monotonic()


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"
