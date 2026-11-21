"""Share one filesystem poller and the latest event of each kind per worker."""
import asyncio
import json
import logging


class DashboardEvents:
    def __init__(self, snapshot, get_status, interval=2.5):
        self.snapshot = snapshot
        self.get_status = get_status
        self.interval = interval
        self.subscribers = {}
        self.task = None

    async def stream(self):
        pending = asyncio.Event()
        latest = {}
        self.subscribers[pending] = latest
        if self.task is None:
            self.task = asyncio.create_task(self._watch())
        try:
            while True:
                try:
                    await asyncio.wait_for(pending.wait(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                pending.clear()
                messages = list(latest.values())
                latest.clear()
                for message in messages:
                    yield message
        finally:
            del self.subscribers[pending]
            if not self.subscribers:
                self.task.cancel()
                self.task = None

    async def _watch(self):
        previous = None
        while True:
            try:
                current = await asyncio.to_thread(self.snapshot)
                events = {}
                if previous is not None:
                    if current[0] != previous[0]:
                        events["status_update"] = await asyncio.to_thread(self.get_status)
                    if current[1] != previous[1]:
                        events["brain_graph_update"] = {}
                previous = current
                for kind, fields in events.items():
                    message = "data: " + json.dumps({"type": kind, **fields}, ensure_ascii=False) + "\n\n"
                    for pending, latest in self.subscribers.items():
                        latest[kind] = message
                        pending.set()
            except (OSError, ValueError, TypeError, AttributeError):
                logging.getLogger(__name__).exception("Dashboard filesystem poll failed")
            await asyncio.sleep(self.interval)
