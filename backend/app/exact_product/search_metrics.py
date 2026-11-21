"""Per-execution search accounting; contains no market data or reusable results."""
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass
class SearchMetrics:
    requests: int = 0
    async_requests: int = 0
    sync_requests: int = 0


active_search_metrics: ContextVar[SearchMetrics | None] = ContextVar("exact_product_search_metrics", default=None)


def record_search_request(*, is_sync: bool = False) -> None:
    metrics = active_search_metrics.get()
    if metrics is not None:
        metrics.requests += 1
        if is_sync:
            metrics.sync_requests += 1
        else:
            metrics.async_requests += 1
