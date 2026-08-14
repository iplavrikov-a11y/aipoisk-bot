import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

class JobEventBus:
    def __init__(self):
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.discard(q)

    def publish(self, event_data: dict[str, Any]) -> None:
        if not self._subscribers:
            return
        dead = set()
        for q in list(self._subscribers):
            try:
                q.put_nowait(event_data)
            except Exception:
                dead.add(q)
        for q in dead:
            self._subscribers.discard(q)

job_event_bus = JobEventBus()
