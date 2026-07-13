"""Centralized logging with file rotation for the Palworld Server Wrapper."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable


class GuiLogHandler(logging.Handler):
    """Custom logging handler that routes messages to a GUI callback.

    Thread-safe: uses the handler's lock. Filters to INFO level and above
    to show only operational messages (not DEBUG noise).
    """

    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__(level=logging.INFO)
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        """Format the record and invoke the GUI callback."""
        try:
            msg = self.format(record)
            self._callback(msg)
        except Exception:
            self.handleError(record)


class WrapperLogger:
    """Provides structured logging with rotating file output and
    optional additional handlers for console or GUI output.

    All log entries include ISO 8601 timestamps. Log files rotate at a
    configurable size limit with a configurable number of backups retained.
    """

    _FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
    _DATEFMT = "%Y-%m-%dT%H:%M:%S%z"

    def __init__(self) -> None:
        self._logger: logging.Logger = logging.getLogger("src")
        self._gui_handler: logging.Handler | None = None
        self._console_handler: logging.Handler | None = None

    @classmethod
    def _make_formatter(cls) -> logging.Formatter:
        """Create a standard log formatter with ISO 8601 timestamps."""
        formatter = logging.Formatter(fmt=cls._FORMAT, datefmt=cls._DATEFMT)
        formatter.default_time_format = "%Y-%m-%dT%H:%M:%S"
        formatter.default_msec_format = None
        return formatter

    def setup(
        self,
        log_path: Path,
        max_size_mb: int = 10,
        backup_count: int = 3,
        mode: str = "console",
        gui_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Configure the logger with appropriate handlers based on mode.

        Always adds RotatingFileHandler.
        If mode == "console": adds StreamHandler(stdout) for operational info.
        If mode == "gui": adds GuiLogHandler that routes to gui_callback.

        Args:
            log_path: Path to the log file.
            max_size_mb: Maximum size of a single log file in megabytes.
            backup_count: Number of rotated backup files to retain.
            mode: Interface mode ("console" or "gui").
            gui_callback: Callback for GUI mode to receive log messages.
        """
        self._logger.setLevel(logging.DEBUG)

        # Prevent propagation to root logger to avoid duplicates with basicConfig
        self._logger.propagate = False

        # Remove any existing handlers to avoid duplicates on re-setup
        self._logger.handlers.clear()

        max_bytes = max_size_mb * 1024 * 1024
        formatter = self._make_formatter()

        # Always add RotatingFileHandler, but handle open errors gracefully
        try:
            file_handler = RotatingFileHandler(
                filename=str(log_path),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)
        except (OSError, IOError):
            # Log file cannot be opened; continue without file logging
            pass

        # Add mode-specific handlers
        if mode == "console":
            self.add_console_handler()
        elif mode == "gui" and gui_callback is not None:
            self.add_gui_handler(gui_callback)

    def add_console_handler(self) -> None:
        """Add a StreamHandler writing to stdout (INFO level)."""
        formatter = self._make_formatter()

        self._console_handler = logging.StreamHandler(sys.stdout)
        self._console_handler.setLevel(logging.INFO)
        self._console_handler.setFormatter(formatter)
        self._logger.addHandler(self._console_handler)

    def add_gui_handler(self, callback: Callable[[str], None]) -> None:
        """Add a handler that routes formatted messages to a GUI callback.

        Args:
            callback: Function accepting a formatted log string, called for
                each operational-level message (INFO and above).
        """
        formatter = self._make_formatter()

        self._gui_handler = GuiLogHandler(callback)
        self._gui_handler.setFormatter(formatter)
        self._logger.addHandler(self._gui_handler)

    def log_state_transition(self, from_state: str, to_state: str) -> None:
        """Log a server state transition.

        Args:
            from_state: The state being transitioned from.
            to_state: The state being transitioned to.
        """
        self._logger.info("State transition: %s -> %s", from_state, to_state)

    def log_player_event(self, event_type: str, count: int) -> None:
        """Log a player connection or disconnection event.

        Args:
            event_type: Type of event (e.g. 'connected', 'disconnected').
            count: Current player count after the event.
        """
        self._logger.info("Player %s (count: %d)", event_type, count)

    def log_error(self, context: str, error: Exception) -> None:
        """Log an error with context information.

        Args:
            context: Description of what was happening when the error occurred.
            error: The exception that was raised.
        """
        self._logger.error("%s: %s", context, error, exc_info=True)
