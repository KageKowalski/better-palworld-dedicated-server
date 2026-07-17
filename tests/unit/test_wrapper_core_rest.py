"""Unit tests for WrapperCore REST API connection retry logic.

Tests the connectivity check with retries that runs at the start of
_rest_poll_loop when entering RUNNING state (Requirements 8.1–8.5).
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import WrapperConfig
from src.models import InfoResult, MetricsResult, ServerState
from src.wrapper_core import WrapperCore


def _make_config(tmp_path: Path) -> WrapperConfig:
    """Create a minimal WrapperConfig for testing."""
    return WrapperConfig(
        server_exe_path=tmp_path / "PalServer.exe",
        settings_file_path=tmp_path / "PalWorldSettings.ini",
        idle_timeout_seconds=300,
        start_timeout_seconds=5,
        stop_timeout_seconds=5,
        poll_interval_seconds=1,
    )


def _setup_core(tmp_path: Path) -> WrapperCore:
    """Create a WrapperCore with mocked dependencies ready for RUNNING state."""
    config = _make_config(tmp_path)
    core = WrapperCore(config)
    core._state = ServerState.RUNNING
    core._logger.log_state_transition = MagicMock()
    core._logger.log_player_event = MagicMock()
    core._logger.log_error = MagicMock()
    return core


@pytest.mark.asyncio
class TestRestApiConnectRetry:
    """Test the REST API connectivity check with retries at poll loop start."""

    async def test_immediate_success_proceeds_to_polling(self, tmp_path):
        """When get_info succeeds on first attempt, proceeds to polling loop."""
        core = _setup_core(tmp_path)

        # get_info succeeds immediately
        core._rest_client.get_info = AsyncMock(
            return_value=InfoResult(success=True, version="v0.3.5")
        )
        # get_metrics will be called in the polling loop - make it succeed once then
        # change state to stop the loop
        call_count = 0

        async def metrics_then_stop():
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                core._state = ServerState.STOPPING
            return MetricsResult(success=True, player_count=0)

        core._rest_client.get_metrics = AsyncMock(side_effect=metrics_then_stop)
        core._idle_timer.start = AsyncMock()
        core._idle_timer.is_active = MagicMock(return_value=False)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await core._rest_poll_loop()

        # get_info was called exactly once (succeeded on first attempt)
        core._rest_client.get_info.assert_called_once()

    async def test_retries_on_failure_then_succeeds(self, tmp_path):
        """Retries get_info on failure, succeeds on 3rd attempt."""
        core = _setup_core(tmp_path)

        # Fail twice, succeed on third
        core._rest_client.get_info = AsyncMock(
            side_effect=[
                InfoResult(success=False, error_message="Connection refused"),
                InfoResult(success=False, error_message="Connection refused"),
                InfoResult(success=True, version="v0.3.5"),
            ]
        )
        # Stop the polling loop immediately after retry succeeds
        core._rest_client.get_metrics = AsyncMock(
            side_effect=lambda: _stop_core(core)
        )
        core._idle_timer.start = AsyncMock()
        core._idle_timer.is_active = MagicMock(return_value=False)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await core._rest_poll_loop()

        # get_info called 3 times
        assert core._rest_client.get_info.call_count == 3

    async def test_retry_delays_are_correct(self, tmp_path):
        """Retry delays follow the [2, 4, 8, 16, 30] pattern."""
        core = _setup_core(tmp_path)

        # Fail all 5 attempts
        core._rest_client.get_info = AsyncMock(
            return_value=InfoResult(success=False, error_message="Timeout")
        )
        # Stop the loop after retries exhausted
        core._rest_client.get_metrics = AsyncMock(
            side_effect=lambda: _stop_core(core)
        )
        core._idle_timer.start = AsyncMock()
        core._idle_timer.is_active = MagicMock(return_value=False)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await core._rest_poll_loop()

        # Collect all sleep calls (first is the initial 2s delay,
        # then retry delays, then possibly poll interval)
        sleep_args = [call.args[0] for call in mock_sleep.call_args_list]

        # First sleep is the initial 2s wait
        assert sleep_args[0] == 2
        # Retry delays: attempts 1-4 get delays [2, 4, 8, 16]
        # (attempt 5 fails without a subsequent delay)
        assert sleep_args[1] == 2   # after attempt 1
        assert sleep_args[2] == 4   # after attempt 2
        assert sleep_args[3] == 8   # after attempt 3
        assert sleep_args[4] == 16  # after attempt 4

    async def test_all_retries_exhausted_enters_polling_loop(self, tmp_path):
        """After all 5 retries fail, still enters the polling loop."""
        core = _setup_core(tmp_path)

        # All attempts fail
        core._rest_client.get_info = AsyncMock(
            return_value=InfoResult(success=False, error_message="Timeout")
        )
        # Track that polling loop is entered
        poll_entered = False

        async def mark_poll_entered():
            nonlocal poll_entered
            poll_entered = True
            core._state = ServerState.STOPPING
            return MetricsResult(success=True, player_count=0)

        core._rest_client.get_metrics = AsyncMock(side_effect=mark_poll_entered)
        core._idle_timer.start = AsyncMock()
        core._idle_timer.is_active = MagicMock(return_value=False)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await core._rest_poll_loop()

        # All 5 attempts were made
        assert core._rest_client.get_info.call_count == 5
        # Polling loop was still entered
        assert poll_entered is True

    async def test_state_change_aborts_retries(self, tmp_path):
        """If state changes from RUNNING during retries, aborts immediately."""
        core = _setup_core(tmp_path)

        # Change state after 2 failed attempts when sleep is called
        attempt_count = 0

        async def get_info_and_track():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count >= 2:
                core._state = ServerState.STOPPING
            return InfoResult(success=False, error_message="Connection refused")

        core._rest_client.get_info = AsyncMock(side_effect=get_info_and_track)
        core._rest_client.get_metrics = AsyncMock()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await core._rest_poll_loop()

        # Should have called get_info twice, then state check aborted at attempt 3
        assert core._rest_client.get_info.call_count == 2
        # get_metrics should NOT have been called (loop not entered)
        core._rest_client.get_metrics.assert_not_called()

    async def test_state_change_before_first_attempt_aborts(self, tmp_path):
        """If state changes before even the first attempt, aborts."""
        core = _setup_core(tmp_path)

        async def change_state_on_sleep(seconds):
            if seconds == 2:  # The initial sleep
                core._state = ServerState.STOPPING

        core._rest_client.get_info = AsyncMock(
            return_value=InfoResult(success=True, version="v0.3.5")
        )
        core._rest_client.get_metrics = AsyncMock()

        with patch("asyncio.sleep", new_callable=AsyncMock, side_effect=change_state_on_sleep):
            await core._rest_poll_loop()

        # get_info should not be called since state changed before first attempt
        core._rest_client.get_info.assert_not_called()
        core._rest_client.get_metrics.assert_not_called()


def _stop_core(core: WrapperCore) -> MetricsResult:
    """Helper to stop the polling loop by changing state."""
    core._state = ServerState.STOPPING
    return MetricsResult(success=True, player_count=0)
