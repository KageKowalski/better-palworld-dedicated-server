"""Unit tests for the WrapperCore class.

Focuses on the idle-timeout-to-stop flow to verify that stop_server
completes fully when triggered by the idle timer callback.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import WrapperConfig
from src.models import ServerState, StartResult, StopResult
from src.wrapper_core import WrapperCore


def _make_config(tmp_path: Path) -> WrapperConfig:
    """Create a minimal WrapperConfig for testing."""
    return WrapperConfig(
        server_exe_path=tmp_path / "PalServer.exe",
        settings_file_path=tmp_path / "PalWorldSettings.ini",
        idle_timeout_seconds=1,
        start_timeout_seconds=5,
        stop_timeout_seconds=5,
        poll_interval_seconds=1,
    )


@pytest.mark.asyncio
class TestIdleTimeoutStopFlow:
    """Verify that idle timer expiry actually stops the server process.

    This class tests the fix for a bug where stop_server() was called from
    within the idle timer's own asyncio task. When stop_server cancelled the
    idle timer, it cancelled its own executing task, causing CancelledError
    to abort the shutdown before the terminate signal was sent.
    """

    async def test_stop_server_called_on_idle_expiry(self, tmp_path):
        """Process manager stop_server is invoked when idle timer fires."""
        config = _make_config(tmp_path)
        core = WrapperCore(config)

        # Put the core into RUNNING state manually
        core._state = ServerState.RUNNING

        # Mock the process manager to track the stop call
        core._process_manager.stop_server = AsyncMock(
            return_value=StopResult(success=True, was_forced=False)
        )
        core._process_manager.get_pid = MagicMock(return_value=12345)

        # Mock RCON client
        core._rcon_client.send_command = AsyncMock(return_value=None)
        core._rcon_client.disconnect = AsyncMock()

        # Mock connection listener
        core._connection_listener.start_listening = AsyncMock()

        # Mock the logger to avoid file I/O
        core._logger.log_state_transition = MagicMock()

        # Trigger the idle expiry handler
        await core.handle_idle_expired()

        # Give the created task time to run
        await asyncio.sleep(0.1)

        # The process manager's stop_server must have been called
        core._process_manager.stop_server.assert_called_once_with(
            timeout=config.stop_timeout_seconds
        )

    async def test_state_transitions_to_monitoring_after_idle_stop(self, tmp_path):
        """After idle-triggered stop completes, state returns to MONITORING."""
        config = _make_config(tmp_path)
        core = WrapperCore(config)

        core._state = ServerState.RUNNING

        core._process_manager.stop_server = AsyncMock(
            return_value=StopResult(success=True, was_forced=False)
        )
        core._process_manager.get_pid = MagicMock(return_value=12345)
        core._rcon_client.send_command = AsyncMock(return_value=None)
        core._rcon_client.disconnect = AsyncMock()
        core._connection_listener.start_listening = AsyncMock()
        core._logger.log_state_transition = MagicMock()

        await core.handle_idle_expired()
        await asyncio.sleep(0.1)

        assert core._state == ServerState.MONITORING

    async def test_idle_timer_self_cancellation_does_not_abort_stop(self, tmp_path):
        """Simulates the actual idle timer flow end-to-end.

        The idle timer's _countdown task awaits handle_idle_expired. The fix
        ensures that stop_server runs in a separate task so cancelling the
        idle timer doesn't cancel the stop operation.
        """
        config = _make_config(tmp_path)
        config.idle_timeout_seconds = 0  # Expire immediately

        core = WrapperCore(config)
        core._state = ServerState.RUNNING

        core._process_manager.stop_server = AsyncMock(
            return_value=StopResult(success=True, was_forced=False)
        )
        core._process_manager.get_pid = MagicMock(return_value=12345)
        core._rcon_client.send_command = AsyncMock(return_value=None)
        core._rcon_client.disconnect = AsyncMock()
        core._connection_listener.start_listening = AsyncMock()
        core._logger.log_state_transition = MagicMock()

        # Start the idle timer — it should fire almost immediately
        await core._idle_timer.start()

        # Wait for the timer to fire and the stop task to complete
        await asyncio.sleep(0.3)

        # The critical assertion: process manager stop was actually called
        core._process_manager.stop_server.assert_called_once()
        assert core._state == ServerState.MONITORING

    async def test_player_count_reset_after_idle_stop(self, tmp_path):
        """Player count resets to 0 after idle-triggered shutdown."""
        config = _make_config(tmp_path)
        core = WrapperCore(config)

        core._state = ServerState.RUNNING
        core._player_count = 3

        core._process_manager.stop_server = AsyncMock(
            return_value=StopResult(success=True, was_forced=False)
        )
        core._process_manager.get_pid = MagicMock(return_value=12345)
        core._rcon_client.send_command = AsyncMock(return_value=None)
        core._rcon_client.disconnect = AsyncMock()
        core._connection_listener.start_listening = AsyncMock()
        core._logger.log_state_transition = MagicMock()

        await core.handle_idle_expired()
        await asyncio.sleep(0.1)

        assert core._player_count == 0

    async def test_connection_listener_restarts_after_idle_stop(self, tmp_path):
        """Connection listener is restarted after idle-triggered shutdown."""
        config = _make_config(tmp_path)
        core = WrapperCore(config)

        core._state = ServerState.RUNNING

        core._process_manager.stop_server = AsyncMock(
            return_value=StopResult(success=True, was_forced=False)
        )
        core._process_manager.get_pid = MagicMock(return_value=12345)
        core._rcon_client.send_command = AsyncMock(return_value=None)
        core._rcon_client.disconnect = AsyncMock()
        core._connection_listener.start_listening = AsyncMock()
        core._logger.log_state_transition = MagicMock()

        await core.handle_idle_expired()
        await asyncio.sleep(0.1)

        core._connection_listener.start_listening.assert_called_once()


@pytest.mark.asyncio
class TestStopServerGuards:
    """Test stop_server state guards."""

    async def test_stop_rejects_when_not_running(self, tmp_path):
        """stop_server returns failure when not in RUNNING state."""
        config = _make_config(tmp_path)
        core = WrapperCore(config)

        # State is MONITORING by default
        result = await core.stop_server()
        assert result.success is False
        assert "not running" in result.error_message.lower()

    async def test_idle_expired_ignored_when_not_running(self, tmp_path):
        """handle_idle_expired is a no-op when state is not RUNNING."""
        config = _make_config(tmp_path)
        core = WrapperCore(config)
        core._state = ServerState.STOPPING

        core._process_manager.stop_server = AsyncMock()

        await core.handle_idle_expired()
        await asyncio.sleep(0.1)

        # stop_server should NOT have been called
        core._process_manager.stop_server.assert_not_called()
