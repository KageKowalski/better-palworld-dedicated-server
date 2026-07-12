"""Unit tests for the WrapperLogger module."""

import logging
import re
from pathlib import Path

from src.logger import GuiLogHandler, WrapperLogger


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



class TestWrapperLoggerSetupMode:
    """Tests for logger setup with mode parameter."""

    def test_setup_console_mode_adds_stream_handler(self, tmp_path: Path) -> None:
        from logging.handlers import RotatingFileHandler

        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file, mode="console")

        handlers = logger._logger.handlers
        handler_types = [type(h) for h in handlers]
        assert RotatingFileHandler in handler_types
        assert logging.StreamHandler in handler_types

    def test_setup_gui_mode_adds_gui_handler(self, tmp_path: Path) -> None:
        from logging.handlers import RotatingFileHandler

        log_file = tmp_path / "test.log"
        messages: list[str] = []
        logger = WrapperLogger()
        logger.setup(log_file, mode="gui", gui_callback=messages.append)

        handlers = logger._logger.handlers
        handler_types = [type(h) for h in handlers]
        assert RotatingFileHandler in handler_types
        assert GuiLogHandler in handler_types

    def test_setup_gui_mode_no_stream_handler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        messages: list[str] = []
        logger = WrapperLogger()
        logger.setup(log_file, mode="gui", gui_callback=messages.append)

        handlers = logger._logger.handlers
        # Ensure no StreamHandler is present (only RotatingFileHandler and GuiLogHandler)
        for h in handlers:
            assert not (isinstance(h, logging.StreamHandler) and not isinstance(h, GuiLogHandler)
                        and not isinstance(h, logging.handlers.RotatingFileHandler))

    def test_setup_console_mode_no_gui_handler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file, mode="console")

        handlers = logger._logger.handlers
        handler_types = [type(h) for h in handlers]
        assert GuiLogHandler not in handler_types

    def test_setup_gui_mode_without_callback_no_gui_handler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file, mode="gui", gui_callback=None)

        handlers = logger._logger.handlers
        handler_types = [type(h) for h in handlers]
        assert GuiLogHandler not in handler_types

    def test_setup_handles_file_open_error(self, tmp_path: Path) -> None:
        # Use a path to a non-existent directory to trigger an error
        log_file = tmp_path / "nonexistent_dir" / "subdir" / "test.log"
        logger = WrapperLogger()
        # Should not raise, just continue without file logging
        logger.setup(log_file, mode="console")

        # Logger should still have the console handler
        has_stream_handler = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, GuiLogHandler)
            for h in logger._logger.handlers
        )
        assert has_stream_handler

    def test_setup_file_error_still_adds_mode_handler(self, tmp_path: Path) -> None:
        from logging.handlers import RotatingFileHandler

        log_file = tmp_path / "nonexistent_dir" / "subdir" / "test.log"
        messages: list[str] = []
        logger = WrapperLogger()
        logger.setup(log_file, mode="gui", gui_callback=messages.append)

        handler_types = [type(h) for h in logger._logger.handlers]
        # No file handler since path is invalid
        assert RotatingFileHandler not in handler_types
        # But GUI handler is still present
        assert GuiLogHandler in handler_types


class TestGuiLogHandler:
    """Tests for the GuiLogHandler class."""

    def test_gui_handler_receives_info_messages(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        messages: list[str] = []
        logger = WrapperLogger()
        logger.setup(log_file, mode="gui", gui_callback=messages.append)

        logger.log_state_transition("MONITORING", "STARTING")

        assert len(messages) == 1
        assert "State transition: MONITORING -> STARTING" in messages[0]

    def test_gui_handler_does_not_receive_debug_messages(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        messages: list[str] = []
        logger = WrapperLogger()
        logger.setup(log_file, mode="gui", gui_callback=messages.append)

        # Log at DEBUG level directly
        logger._logger.debug("debug message")

        assert len(messages) == 0

    def test_gui_handler_receives_error_messages(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        messages: list[str] = []
        logger = WrapperLogger()
        logger.setup(log_file, mode="gui", gui_callback=messages.append)

        logger.log_error("Test error", RuntimeError("test"))

        assert len(messages) == 1
        assert "Test error: test" in messages[0]

    def test_gui_handler_callback_exception_handled(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"

        def bad_callback(msg: str) -> None:
            raise RuntimeError("callback failed")

        logger = WrapperLogger()
        logger.setup(log_file, mode="gui", gui_callback=bad_callback)

        # Should not raise - handleError should catch it
        logger.log_state_transition("MONITORING", "STARTING")

    def test_gui_handler_formats_messages(self) -> None:
        messages: list[str] = []
        handler = GuiLogHandler(messages.append)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        handler.setFormatter(formatter)

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Hello %s",
            args=("world",),
            exc_info=None,
        )
        handler.emit(record)

        assert len(messages) == 1
        assert "Hello world" in messages[0]
        assert "[INFO]" in messages[0]

    def test_gui_handler_level_is_info(self) -> None:
        handler = GuiLogHandler(lambda msg: None)
        assert handler.level == logging.INFO


class TestWrapperLoggerAddConsoleHandler:
    """Tests for the add_console_handler method."""

    def test_add_console_handler_creates_stream_handler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "test.log"
        logger = WrapperLogger()
        logger.setup(log_file, mode="gui", gui_callback=lambda m: None)

        # Now manually add console handler
        logger.add_console_handler()

        has_stream = any(
            isinstance(h, logging.StreamHandler) and not isinstance(h, GuiLogHandler)
            and not isinstance(h, logging.handlers.RotatingFileHandler)
            for h in logger._logger.handlers
        )
        assert has_stream

    def test_add_console_handler_sets_info_level(self) -> None:
        logger = WrapperLogger()
        logger._logger.setLevel(logging.DEBUG)
        logger.add_console_handler()

        assert logger._console_handler is not None
        assert logger._console_handler.level == logging.INFO


class TestWrapperLoggerAddGuiHandler:
    """Tests for the add_gui_handler method."""

    def test_add_gui_handler_creates_gui_log_handler(self) -> None:
        logger = WrapperLogger()
        logger._logger.setLevel(logging.DEBUG)
        messages: list[str] = []
        logger.add_gui_handler(messages.append)

        assert logger._gui_handler is not None
        assert isinstance(logger._gui_handler, GuiLogHandler)

    def test_add_gui_handler_routes_messages(self) -> None:
        logger = WrapperLogger()
        logger._logger.setLevel(logging.DEBUG)
        messages: list[str] = []
        logger.add_gui_handler(messages.append)

        logger._logger.info("test message")

        assert len(messages) == 1
        assert "test message" in messages[0]
