"""Maintenance timer that fires callbacks at broadcast and maintenance intervals.

The timer uses asyncio's monotonic event loop clock to track elapsed uptime
in the RUNNING state and triggers two callbacks: one when the broadcast
warning should be sent, and another when the maintenance cycle should begin.
"""

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class MaintenanceTimer:
    """Tracks uptime and fires callbacks at broadcast and maintenance times.

    The timer starts counting when the server enters the RUNNING state.
    At (interval - broadcast_lead) seconds, it fires on_broadcast_due.
    At interval seconds, it fires on_maintenance_due.
    Calling start() always resets to zero — no accumulated time carries over.
    """

    def __init__(
        self,
        interval_seconds: int,
        broadcast_lead_seconds: int,
        on_broadcast_due: Callable | None = None,
        on_maintenance_due: Callable | None = None,
    ) -> None:
        """Initialize the maintenance timer.

        Args:
            interval_seconds: Total seconds before maintenance cycle begins.
            broadcast_lead_seconds: Seconds before maintenance to fire the
                broadcast callback. The broadcast fires at
                (interval_seconds - broadcast_lead_seconds).
            on_broadcast_due: Callback invoked when the broadcast warning
                should be sent to players.
            on_maintenance_due: Callback invoked when the maintenance cycle
                should begin.
        """
        self._interval_seconds = interval_seconds
        self._broadcast_lead_seconds = broadcast_lead_seconds
        self._on_broadcast_due = on_broadcast_due
        self._on_maintenance_due = on_maintenance_due
        self._task: asyncio.Task | None = None
        self._start_time: float | None = None

    async def start(self) -> None:
        """Begin the maintenance timer countdown from zero.

        Cancels any existing timer task and creates a new one. Unlike
        IdleTimer.start(), this always resets to zero — calling start()
        while active restarts the countdown.
        """
        if self._task is not None and not self._task.done():
            self._task.cancel()

        loop = asyncio.get_event_loop()
        self._start_time = loop.time()
        self._task = asyncio.create_task(self._countdown())

    async def _countdown(self) -> None:
        """Internal coroutine that sleeps until broadcast, then until maintenance."""
        try:
            broadcast_time = self._interval_seconds - self._broadcast_lead_seconds
            await asyncio.sleep(broadcast_time)

            if self._on_broadcast_due is not None:
                result = self._on_broadcast_due()
                if asyncio.iscoroutine(result):
                    await result

            await asyncio.sleep(self._broadcast_lead_seconds)

            if self._on_maintenance_due is not None:
                result = self._on_maintenance_due()
                if asyncio.iscoroutine(result):
                    await result
        except asyncio.CancelledError:
            pass

    def cancel(self) -> None:
        """Stop the timer entirely without firing callbacks.

        Called when the server leaves the RUNNING state or when a
        maintenance cycle begins.
        """
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None
        self._start_time = None

    def is_active(self) -> bool:
        """Return True if the timer is currently running."""
        return self._task is not None and not self._task.done()

    def elapsed_seconds(self) -> int:
        """Return whole seconds elapsed since the timer started.

        Returns 0 if the timer is not active.
        """
        if self._start_time is None or self._task is None or self._task.done():
            return 0

        loop = asyncio.get_event_loop()
        elapsed = loop.time() - self._start_time
        return int(elapsed)
