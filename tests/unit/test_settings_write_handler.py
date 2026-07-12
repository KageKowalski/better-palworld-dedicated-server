"""Unit tests for SettingsWriteHandler."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.models import ServerState, ValidationResult, WrapperStatus
from src.pending_settings import PendingSettingsQueue
from src.settings_write_handler import SettingsWriteHandler


def _make_wrapper_core_mock(state: ServerState) -> MagicMock:
    """Create a mock WrapperCore that returns the given server state."""
    mock = MagicMock()
    mock.get_status.return_value = WrapperStatus(
        server_state=state,
        player_count=0,
        idle_timer_active=False,
        idle_seconds=0,
        server_pid=None,
        uptime_seconds=None,
    )
    return mock


class TestSettingsWriteHandlerInit:
    """Tests for SettingsWriteHandler initialization."""

    def test_init_stores_dependencies(self, tmp_path: Path) -> None:
        """SettingsWriteHandler stores wrapper_core, pending_queue, and path."""
        wrapper = _make_wrapper_core_mock(ServerState.MONITORING)
        queue = PendingSettingsQueue()
        file_path = tmp_path / "settings.ini"

        handler = SettingsWriteHandler(wrapper, queue, file_path)

        assert handler._wrapper_core is wrapper
        assert handler._pending_queue is queue
        assert handler._settings_file_path == file_path

    def test_safe_states_only_monitoring(self) -> None:
        """SAFE_STATES contains only MONITORING."""
        assert SettingsWriteHandler.SAFE_STATES == {ServerState.MONITORING}


class TestSubmitDirectWrite:
    """Tests for submit() in MONITORING (safe) state."""

    @patch("src.settings_write_handler.SettingsParser.write_setting")
    @patch("src.settings_write_handler.SettingsParser.validate_setting")
    def test_direct_write_success(
        self, mock_validate: MagicMock, mock_write: MagicMock, tmp_path: Path
    ) -> None:
        """In MONITORING state, valid settings are written directly."""
        mock_validate.return_value = ValidationResult(valid=True)
        mock_write.return_value = ValidationResult(valid=True)

        wrapper = _make_wrapper_core_mock(ServerState.MONITORING)
        queue = PendingSettingsQueue()
        file_path = tmp_path / "settings.ini"

        handler = SettingsWriteHandler(wrapper, queue, file_path)
        result, was_queued = handler.submit("DayTimeSpeedRate", 1.5)

        assert result.valid is True
        assert was_queued is False
        mock_write.assert_called_once_with(file_path, "DayTimeSpeedRate", 1.5)
        assert queue.is_empty()

    @patch("src.settings_write_handler.SettingsParser.write_setting")
    @patch("src.settings_write_handler.SettingsParser.validate_setting")
    def test_direct_write_failure(
        self, mock_validate: MagicMock, mock_write: MagicMock, tmp_path: Path
    ) -> None:
        """In MONITORING state, write failure returns error without queuing."""
        mock_validate.return_value = ValidationResult(valid=True)
        mock_write.return_value = ValidationResult(
            valid=False, error_message="File not found"
        )

        wrapper = _make_wrapper_core_mock(ServerState.MONITORING)
        queue = PendingSettingsQueue()
        file_path = tmp_path / "settings.ini"

        handler = SettingsWriteHandler(wrapper, queue, file_path)
        result, was_queued = handler.submit("DayTimeSpeedRate", 1.5)

        assert result.valid is False
        assert result.error_message == "File not found"
        assert was_queued is False
        assert queue.is_empty()


class TestSubmitQueuing:
    """Tests for submit() in unsafe states (STARTING, RUNNING, STOPPING)."""

    @pytest.mark.parametrize("state", [ServerState.STARTING, ServerState.RUNNING, ServerState.STOPPING])
    @patch("src.settings_write_handler.SettingsParser.validate_setting")
    def test_queues_in_unsafe_states(
        self, mock_validate: MagicMock, state: ServerState, tmp_path: Path
    ) -> None:
        """In unsafe states, valid settings are queued instead of written."""
        mock_validate.return_value = ValidationResult(valid=True)

        wrapper = _make_wrapper_core_mock(state)
        queue = PendingSettingsQueue()
        file_path = tmp_path / "settings.ini"

        handler = SettingsWriteHandler(wrapper, queue, file_path)
        result, was_queued = handler.submit("DayTimeSpeedRate", 2.0)

        assert result.valid is True
        assert was_queued is True
        assert queue.count() == 1
        assert queue.entries() == [("DayTimeSpeedRate", 2.0)]


class TestSubmitValidation:
    """Tests for validation gating in submit()."""

    @patch("src.settings_write_handler.SettingsParser.validate_setting")
    def test_invalid_setting_rejected_without_write_or_queue(
        self, mock_validate: MagicMock, tmp_path: Path
    ) -> None:
        """Invalid settings are rejected without writing or queuing."""
        mock_validate.return_value = ValidationResult(
            valid=False, error_message="Value out of range"
        )

        wrapper = _make_wrapper_core_mock(ServerState.MONITORING)
        queue = PendingSettingsQueue()
        file_path = tmp_path / "settings.ini"

        handler = SettingsWriteHandler(wrapper, queue, file_path)
        result, was_queued = handler.submit("DayTimeSpeedRate", 999.0)

        assert result.valid is False
        assert result.error_message == "Value out of range"
        assert was_queued is False
        assert queue.is_empty()

    @pytest.mark.parametrize("state", [ServerState.STARTING, ServerState.RUNNING, ServerState.STOPPING])
    @patch("src.settings_write_handler.SettingsParser.validate_setting")
    def test_invalid_setting_rejected_in_unsafe_states(
        self, mock_validate: MagicMock, state: ServerState, tmp_path: Path
    ) -> None:
        """Invalid settings are rejected in unsafe states without queuing."""
        mock_validate.return_value = ValidationResult(
            valid=False, error_message="Invalid type"
        )

        wrapper = _make_wrapper_core_mock(state)
        queue = PendingSettingsQueue()
        file_path = tmp_path / "settings.ini"

        handler = SettingsWriteHandler(wrapper, queue, file_path)
        result, was_queued = handler.submit("DayTimeSpeedRate", "not_a_number")

        assert result.valid is False
        assert was_queued is False
        assert queue.is_empty()


class TestSubmitQueueFull:
    """Tests for queue-full case in submit()."""

    @patch("src.settings_write_handler.SettingsParser.validate_setting")
    def test_queue_full_returns_error(
        self, mock_validate: MagicMock, tmp_path: Path
    ) -> None:
        """When the queue is full, new keys are rejected with an error."""
        mock_validate.return_value = ValidationResult(valid=True)

        wrapper = _make_wrapper_core_mock(ServerState.RUNNING)
        queue = PendingSettingsQueue()
        file_path = tmp_path / "settings.ini"

        # Fill the queue to capacity
        for i in range(100):
            queue.add(f"Key{i}", f"Value{i}")

        handler = SettingsWriteHandler(wrapper, queue, file_path)
        result, was_queued = handler.submit("NewKey", "NewValue")

        assert result.valid is False
        assert result.error_message == "Pending queue is full (100 entries maximum)."
        assert was_queued is False
        assert queue.count() == 100
