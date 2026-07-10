"""Idle timer that fires a callback after a configurable period of inactivity.

The timer uses asyncio's monotonic event loop clock to track elapsed time
and triggers a shutdown callback when the configured threshold is reached.
It resets on player connect and cancels when the server stops.
"""

import asyncio
from collections.abc import Callable


class IdleTimer:
    """Tracks idle time and fires a callback when the threshold is reached.

    The timer is active when the server is RUNNING with zero connected players.
    It resets when a player connects and cancels when the server stops.
    """

    def __init__(
        self,
        timeout_seconds: int = 600,
        on_expired: Callable | None = None,
    ) -> None:
        """Initialize the idle timer.

        Args:
            timeout_seconds: Seconds of idle time before the callback fires.
            on_expired: Callback invoked when the idle threshold is reached.
        """
        self._timeout_seconds = timeout_seconds
        self._on_expired = on_expired
        self._task: asyncio.Task | None = None
        self._start_time: float | None = None

    async def start(self) -> None:
        """Begin the idle timer countdown.

        Creates an asyncio task that waits for the timeout duration and then
        invokes the on_expired callback. If the timer is already active, this
        is a no-op.
        """
        if self._task is not None and not self._task.done():
            return

        loop = asyncio.get_event_loop()
        self._start_time = loop.time()
        self._task = asyncio.create_task(self._countdown())

    async def _countdown(self) -> None:
        """Internal coroutine that waits for the timeout then fires the callback."""
        try:
            await asyncio.sleep(self._timeout_seconds)
            if self._on_expired is not None:
                result = self._on_expired()
                # Support both sync and async callbacks
                if asyncio.iscoroutine(result):
                    await result
        except asyncio.CancelledError:
            pass

    def reset(self) -> None:
        """Restart the timer from zero.

        Cancels the current countdown task and starts a new one. This is
        called when a player connects (resetting the idle period).
        """
        if self._task is not None and not self._task.done():
            self._task.cancel()

        loop = asyncio.get_event_loop()
        self._start_time = loop.time()
        self._task = asyncio.create_task(self._countdown())

    def cancel(self) -> None:
        """Stop the timer entirely without firing the callback.

        Called when the server stops or leaves the RUNNING state.
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
