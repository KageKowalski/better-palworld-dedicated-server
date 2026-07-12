"""Pending settings queue for buffering setting changes during unsafe server states.

Provides an in-memory ordered queue that accumulates setting changes while the
server is running, and applies them atomically when the server transitions to
a safe state (MONITORING).
"""

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.settings_parser import SettingsParser


MAX_PENDING_ENTRIES = 100


@dataclass
class ApplyResult:
    """Result of applying pending settings to the settings file.

    Attributes:
        applied_count: Number of entries successfully written to the file.
        failed_key: The setting key that failed to write (if any).
        error_message: Error description for the failed write (if any).
        remaining_count: Number of entries still in the queue after apply.
    """

    applied_count: int
    failed_key: str | None = None
    error_message: str | None = None
    remaining_count: int = 0


class PendingSettingsQueue:
    """In-memory ordered queue for pending setting changes.

    Stores key-value pairs with last-writer-wins semantics:
    - If a key already exists, its value is updated in-place (position preserved).
    - If a key is new, it is appended at the end.
    - Maximum capacity: 100 distinct keys.
    """

    def __init__(self) -> None:
        self._queue: OrderedDict[str, Any] = OrderedDict()

    def add(self, key: str, value: Any) -> bool:
        """Add or update an entry in the queue.

        If the key already exists, its value is updated in-place without
        changing its position in the queue (last-writer-wins).
        If the key is new, it is appended at the end.

        Args:
            key: The setting key name.
            value: The setting value.

        Returns:
            True if the entry was accepted (added or updated).
            False if the queue is full and the key is new.
        """
        if key in self._queue:
            # Update existing key in-place (position preserved by OrderedDict)
            self._queue[key] = value
            return True
        if len(self._queue) >= MAX_PENDING_ENTRIES:
            return False
        self._queue[key] = value
        return True

    def clear(self) -> None:
        """Remove all entries from the queue."""
        self._queue.clear()

    def is_empty(self) -> bool:
        """Return True if the queue has no entries."""
        return len(self._queue) == 0

    def count(self) -> int:
        """Return the number of distinct keys in the queue."""
        return len(self._queue)

    def entries(self) -> list[tuple[str, Any]]:
        """Return all entries as (key, value) tuples in insertion order."""
        return list(self._queue.items())

    def apply(self, file_path: Path) -> ApplyResult:
        """Write all queued entries to the settings file in order.

        Each entry is written via SettingsParser.write_setting. On success,
        the queue is cleared. On failure, the failed entry and all subsequent
        entries are retained in the queue.

        Args:
            file_path: Path to the PalWorldSettings.ini file.

        Returns:
            ApplyResult describing the outcome of the apply operation.
        """
        if self.is_empty():
            return ApplyResult(applied_count=0, remaining_count=0)

        applied = 0
        entries = list(self._queue.items())

        for key, value in entries:
            result = SettingsParser.write_setting(file_path, key, value)
            if not result.valid:
                # Retain failed entry + all subsequent entries
                remaining_keys = [k for k, _ in entries[applied:]]
                new_queue: OrderedDict[str, Any] = OrderedDict()
                for k in remaining_keys:
                    new_queue[k] = self._queue[k]
                self._queue = new_queue
                return ApplyResult(
                    applied_count=applied,
                    failed_key=key,
                    error_message=result.error_message,
                    remaining_count=len(self._queue),
                )
            applied += 1

        self._queue.clear()
        return ApplyResult(applied_count=applied, remaining_count=0)
