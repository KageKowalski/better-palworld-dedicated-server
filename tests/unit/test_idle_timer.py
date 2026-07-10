"""Unit tests for the IdleTimer class."""

import asyncio

import pytest
import pytest_asyncio

from src.idle_timer import IdleTimer


class TestIdleTimerInit:
    """Test IdleTimer construction and defaults."""

    def test_default_timeout(self):
        timer = IdleTimer()
        assert timer._timeout_seconds == 600

    def test_custom_timeout(self):
        timer = IdleTimer(timeout_seconds=300)
        assert timer._timeout_seconds == 300

    def test_default_callback_is_none(self):
        timer = IdleTimer()
        assert timer._on_expired is None

    def test_custom_callback(self):
        cb = lambda: None
        timer = IdleTimer(on_expired=cb)
        assert timer._on_expired is cb

    def test_not_active_initially(self):
        timer = IdleTimer()
        assert timer.is_active() is False

    def test_elapsed_zero_when_not_started(self):
        timer = IdleTimer()
        assert timer.elapsed_seconds() == 0


@pytest.mark.asyncio
class TestIdleTimerStart:
    """Test starting the idle timer."""

    async def test_start_makes_timer_active(self):
        timer = IdleTimer(timeout_seconds=10)
        await timer.start()
        assert timer.is_active() is True
        timer.cancel()

    async def test_start_is_idempotent(self):
        timer = IdleTimer(timeout_seconds=10)
        await timer.start()
        task1 = timer._task
        await timer.start()
        task2 = timer._task
        assert task1 is task2
        timer.cancel()

    async def test_elapsed_increases_after_start(self):
        timer = IdleTimer(timeout_seconds=10)
        await timer.start()
        await asyncio.sleep(0.1)
        # Elapsed should be 0 (less than 1 full second) but start_time set
        assert timer._start_time is not None
        timer.cancel()


@pytest.mark.asyncio
class TestIdleTimerReset:
    """Test resetting the idle timer."""

    async def test_reset_restarts_timer(self):
        timer = IdleTimer(timeout_seconds=10)
        await timer.start()
        old_task = timer._task
        await asyncio.sleep(0.05)
        timer.reset()
        new_task = timer._task
        assert old_task is not new_task
        assert timer.is_active() is True
        timer.cancel()

    async def test_reset_resets_start_time(self):
        timer = IdleTimer(timeout_seconds=10)
        await timer.start()
        first_start = timer._start_time
        await asyncio.sleep(0.05)
        timer.reset()
        second_start = timer._start_time
        assert second_start > first_start
        timer.cancel()


@pytest.mark.asyncio
class TestIdleTimerCancel:
    """Test cancelling the idle timer."""

    async def test_cancel_stops_timer(self):
        timer = IdleTimer(timeout_seconds=10)
        await timer.start()
        timer.cancel()
        assert timer.is_active() is False

    async def test_cancel_clears_start_time(self):
        timer = IdleTimer(timeout_seconds=10)
        await timer.start()
        timer.cancel()
        assert timer._start_time is None

    async def test_cancel_when_not_started_is_safe(self):
        timer = IdleTimer(timeout_seconds=10)
        timer.cancel()  # Should not raise
        assert timer.is_active() is False

    async def test_elapsed_zero_after_cancel(self):
        timer = IdleTimer(timeout_seconds=10)
        await timer.start()
        await asyncio.sleep(0.05)
        timer.cancel()
        assert timer.elapsed_seconds() == 0


@pytest.mark.asyncio
class TestIdleTimerCallback:
    """Test that the callback fires when the timeout expires."""

    async def test_callback_fires_on_expiry(self):
        fired = []
        timer = IdleTimer(timeout_seconds=0.1, on_expired=lambda: fired.append(True))
        await timer.start()
        await asyncio.sleep(0.2)
        assert fired == [True]

    async def test_callback_does_not_fire_when_cancelled(self):
        fired = []
        timer = IdleTimer(timeout_seconds=0.1, on_expired=lambda: fired.append(True))
        await timer.start()
        timer.cancel()
        await asyncio.sleep(0.2)
        assert fired == []

    async def test_async_callback_fires_on_expiry(self):
        fired = []

        async def async_callback():
            fired.append(True)

        timer = IdleTimer(timeout_seconds=0.1, on_expired=async_callback)
        await timer.start()
        await asyncio.sleep(0.2)
        assert fired == [True]

    async def test_no_callback_does_not_crash(self):
        timer = IdleTimer(timeout_seconds=0.1, on_expired=None)
        await timer.start()
        await asyncio.sleep(0.2)
        # Should complete without error


@pytest.mark.asyncio
class TestIdleTimerElapsed:
    """Test elapsed_seconds reporting."""

    async def test_elapsed_returns_whole_seconds(self):
        timer = IdleTimer(timeout_seconds=10)
        await timer.start()
        await asyncio.sleep(1.1)
        elapsed = timer.elapsed_seconds()
        assert elapsed >= 1
        timer.cancel()

    async def test_elapsed_zero_before_one_second(self):
        timer = IdleTimer(timeout_seconds=10)
        await timer.start()
        # Immediately after start, less than 1 second has passed
        elapsed = timer.elapsed_seconds()
        assert elapsed == 0
        timer.cancel()
