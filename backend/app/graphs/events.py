from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from app.domain.models import RunEvent
from app.repositories.base import ProjectRepository


class EventBroker:
    """事件先持久化，再广播；SSE 重连可从仓储回放。"""

    def __init__(self, repository: ProjectRepository) -> None:
        self.repository = repository
        self._subscribers: dict[str, set[asyncio.Queue[RunEvent]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def emit(self, event: str, thread_id: str, project_id: str, **data: object) -> RunEvent:
        item = RunEvent(
            event=event,
            thread_id=thread_id,
            project_id=project_id,
            data=dict(data),
        )
        await self.repository.add_event(item)
        async with self._lock:
            queues = list(self._subscribers[thread_id])
        for queue in queues:
            queue.put_nowait(item)
        return item

    async def subscribe(self, thread_id: str) -> AsyncIterator[RunEvent]:
        for event in await self.repository.list_events(thread_id):
            yield event
        queue: asyncio.Queue[RunEvent] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers[thread_id].add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._lock:
                self._subscribers[thread_id].discard(queue)
