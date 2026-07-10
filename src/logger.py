"""Centralized logging with file rotation for the Palworld Server Wrapper."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class WrapperLogger:
    """Provides structured logging with rotating file output.

    All log entries include ISO 8601 timestamps. Log files rotate at a
    configurable size limit with a configurable number of backups retained.
    """

    def __init__(self) -> None:
        self._logger: logging.Logger = logging.getLogger("palworld_wrapper")

    def setup(
        self,
        log_path: Path,
        max_size_mb: int = 10,
        backup_count: int = 3,
    ) -> None:
        """Configure the logger with a rotating file handler.

        Args:
            log_path: Path to the log file.
            max_size_mb: Maximum size of a single log file in megabytes.
            backup_count: Number of rotated backup files to retain.
        """
        self._logger.setLevel(logging.DEBUG)

        # Remove any existing handlers to avoid duplicates on re-setup
        self._logger.handlers.clear()

        max_bytes = max_size_mb * 1024 * 1024

        handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        formatter.default_time_format = "%Y-%m-%dT%H:%M:%S"
        formatter.default_msec_format = None

        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

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
