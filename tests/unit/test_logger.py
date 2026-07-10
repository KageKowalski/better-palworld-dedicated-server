"""Unit tests for the WrapperLogger module."""

import re
from pathlib import Path

from src.logger import WrapperLogger


# ISO 8601 timestamp pattern (e.g., 2024-01-15T10:30:00+0000)
ISO_8601_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


class TestWrapperLoggerSetup:
    """Tests for logger setup and configuration."""

    def test_setup_creates_log_file(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        # Trigger a log entry so the file is created
        logger.log_state_transition("MONITORING", "STARTING")
        assert log_file.exists()

    def test_setup_configures_rotation_parameters(self, tmp_path: Path) -> None:
        from logging.handlers import RotatingFileHandler

        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file, max_size_mb=10, backup_count=3)

        handler = logger._logger.handlers[0]
        assert isinstance(handler, RotatingFileHandler)
        assert handler.maxBytes == 10 * 1024 * 1024
        assert handler.backupCount == 3

    def test_setup_custom_rotation_parameters(self, tmp_path: Path) -> None:
        from logging.handlers import RotatingFileHandler

        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file, max_size_mb=5, backup_count=2)

        handler = logger._logger.handlers[0]
        assert isinstance(handler, RotatingFileHandler)
        assert handler.maxBytes == 5 * 1024 * 1024
        assert handler.backupCount == 2


class TestWrapperLoggerStateTransition:
    """Tests for state transition logging."""

    def test_log_state_transition_format(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        logger.log_state_transition("MONITORING", "STARTING")

        content = log_file.read_text(encoding="utf-8")
        assert "State transition: MONITORING -> STARTING" in content

    def test_log_state_transition_includes_iso_timestamp(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        logger.log_state_transition("RUNNING", "STOPPING")

        content = log_file.read_text(encoding="utf-8")
        assert ISO_8601_PATTERN.search(content) is not None

    def test_log_state_transition_uses_info_level(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        logger.log_state_transition("STARTING", "RUNNING")

        content = log_file.read_text(encoding="utf-8")
        assert "[INFO]" in content


class TestWrapperLoggerPlayerEvent:
    """Tests for player event logging."""

    def test_log_player_connected(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        logger.log_player_event("connected", 3)

        content = log_file.read_text(encoding="utf-8")
        assert "Player connected (count: 3)" in content

    def test_log_player_disconnected(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        logger.log_player_event("disconnected", 2)

        content = log_file.read_text(encoding="utf-8")
        assert "Player disconnected (count: 2)" in content

    def test_log_player_event_includes_iso_timestamp(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        logger.log_player_event("connected", 1)

        content = log_file.read_text(encoding="utf-8")
        assert ISO_8601_PATTERN.search(content) is not None


class TestWrapperLoggerError:
    """Tests for error logging."""

    def test_log_error_includes_context_and_message(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        error = RuntimeError("connection refused")
        logger.log_error("RCON query failed", error)

        content = log_file.read_text(encoding="utf-8")
        assert "RCON query failed: connection refused" in content

    def test_log_error_uses_error_level(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        error = ValueError("invalid port")
        logger.log_error("Configuration error", error)

        content = log_file.read_text(encoding="utf-8")
        assert "[ERROR]" in content

    def test_log_error_includes_traceback(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        try:
            raise FileNotFoundError("PalServer.exe not found")
        except FileNotFoundError as e:
            logger.log_error("Server start failed", e)

        content = log_file.read_text(encoding="utf-8")
        assert "Traceback" in content
        assert "FileNotFoundError" in content

    def test_log_error_includes_iso_timestamp(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file)

        error = RuntimeError("timeout")
        logger.log_error("Operation failed", error)

        content = log_file.read_text(encoding="utf-8")
        assert ISO_8601_PATTERN.search(content) is not None
