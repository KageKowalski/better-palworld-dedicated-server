"""Settings write handler that gates writes based on server state.

Routes setting writes to either the live settings file (when the server is in
a safe state) or to the pending queue (when the server is in an unsafe state).
This prevents writes to PalWorldSettings.ini while the server is running,
which could lead to data corruption or silently lost changes.
"""

from pathlib import Path
from typing import Any

from src.models import ServerState, ValidationResult
from src.pending_settings import PendingSettingsQueue
from src.settings_parser import SettingsParser
from src.wrapper_core import WrapperCore


class SettingsWriteHandler:
    """Routes setting writes to file or pending queue based on server state.

    - Safe state (MONITORING): write directly via SettingsParser.write_setting
    - Unsafe state (STARTING, RUNNING, STOPPING): validate then queue

    The handler guarantees that every submitted setting change that passes
    validation is either written to the settings file or stored in the pending
    queue (no silent discard).
    """

    SAFE_STATES = {ServerState.MONITORING}

    def __init__(
        self,
        wrapper_core: WrapperCore,
        pending_queue: PendingSettingsQueue,
        settings_file_path: Path,
    ) -> None:
        """Initialize the settings write handler.

        Args:
            wrapper_core: The WrapperCore instance to query server state.
            pending_queue: The PendingSettingsQueue instance for buffering changes.
            settings_file_path: Path to the PalWorldSettings.ini file.
        """
        self._wrapper_core = wrapper_core
        self._pending_queue = pending_queue
        self._settings_file_path = settings_file_path

    def submit(self, key: str, value: Any) -> tuple[ValidationResult, bool]:
        """Submit a setting change for writing or queuing.

        The method first validates the key-value pair. If validation fails,
        the invalid result is returned immediately without writing or queuing.

        If validation passes, the current server state determines routing:
        - MONITORING (safe): write directly to the settings file
        - STARTING/RUNNING/STOPPING (unsafe): add to the pending queue

        Args:
            key: The setting key name.
            value: The setting value to write or queue.

        Returns:
            A tuple of (ValidationResult, was_queued) where:
            - ValidationResult indicates success or failure with error details.
            - was_queued is True if the setting was added to the pending queue,
              False if it was written directly or if validation/write failed.
        """
        # Always validate first
        validation = SettingsParser.validate_setting(key, value)
        if not validation.valid:
            return (validation, False)

        # Check server state
        state = self._wrapper_core.get_status().server_state

        if state in self.SAFE_STATES:
            # Direct write to file
            result = SettingsParser.write_setting(self._settings_file_path, key, value)
            return (result, False)
        else:
            # Queue the change for later application
            if not self._pending_queue.add(key, value):
                return (
                    ValidationResult(
                        valid=False,
                        error_message="Pending queue is full (100 entries maximum).",
                    ),
                    False,
                )
            return (ValidationResult(valid=True), True)
