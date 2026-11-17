import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

class JobEventBus:
    def __init__(self):
        self._subscribers: dict[asyncio.Queue, asyncio.AbstractEventLoop | None] = {}

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        try:
            loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        self._subscribers[q] = loop
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subscribers.pop(q, None)

    @staticmethod
    def _deliver(q: asyncio.Queue, event_data: dict[str, Any]) -> None:
        try:
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(event_data)
        except Exception:
            pass

    def publish(self, event_data: dict[str, Any]) -> None:
        if not self._subscribers:
            return
        try:
            running_loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        dead: list[asyncio.Queue] = []
        for q, sub_loop in list(self._subscribers.items()):
            try:
                if sub_loop is not None and not sub_loop.is_closed():
                    if running_loop is sub_loop:
                        self._deliver(q, event_data)
                    else:
                        sub_loop.call_soon_threadsafe(self._deliver, q, event_data)
                elif sub_loop is None:
                    self._deliver(q, event_data)
                else:
                    dead.append(q)
            except Exception:
                dead.append(q)
        for q in dead:
            self._subscribers.pop(q, None)

job_event_bus = JobEventBus()
