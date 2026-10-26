from dataclasses import dataclass

import httpx

from pricewatch.logging import get_logger

log = get_logger(__name__)


@dataclass
class RunStats:
    pages_fetched: int = 0
    items_seen: int = 0
    items_valid: int = 0
    items_inserted: int = 0

    @property
    def items_invalid(self) -> int:
        return self.items_seen - self.items_valid

    @property
    def parse_success_rate(self) -> float | None:
        return round(self.items_valid / self.items_seen, 4) if self.items_seen else None


def run_status(stats: RunStats, threshold: float, min_items_expected: int, blocked: bool) -> str:
    if blocked:
        return "blocked"
    if stats.items_seen == 0:
        return "failed"
    if stats.parse_success_rate < threshold or stats.items_valid < min_items_expected:
        return "degraded"
    return "success"


def alert_if_unhealthy(
    status: str,
    run_id: str,
    platform: str,
    stats: RunStats,
    error_message: str | None,
    webhook_url: str | None,
) -> None:
    if status == "success":
        return
    event = {
        "run_id": run_id,
        "platform": platform,
        "status": status,
        "items_seen": stats.items_seen,
        "items_valid": stats.items_valid,
        "parse_success_rate": stats.parse_success_rate,
        "error_message": error_message,
    }
    log.error("crawl_run_unhealthy", **event)
    if webhook_url:
        try:
            httpx.post(
                webhook_url, json={"text": f"pricewatch crawl {status}", **event}, timeout=10
            )
        except httpx.HTTPError as exc:
            log.error("alert_webhook_failed", error=str(exc))
