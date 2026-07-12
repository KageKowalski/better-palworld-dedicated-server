"""Unit tests for the PendingSettingsQueue module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.models import ValidationResult
from src.pending_settings import (
    MAX_PENDING_ENTRIES,
    ApplyResult,
    PendingSettingsQueue,
)


class TestApplyResult:
    """Tests for the ApplyResult dataclass."""

    def test_default_values(self):
        result = ApplyResult(applied_count=3)
        assert result.applied_count == 3
        assert result.failed_key is None
        assert result.error_message is None
        assert result.remaining_count == 0

    def test_failure_values(self):
        result = ApplyResult(
            applied_count=2,
            failed_key="BadKey",
            error_message="Write failed",
            remaining_count=5,
        )
        assert result.applied_count == 2
        assert result.failed_key == "BadKey"
        assert result.error_message == "Write failed"
        assert result.remaining_count == 5


class TestPendingSettingsQueue:
    """Tests for the PendingSettingsQueue class."""

    def test_empty_on_creation(self):
        queue = PendingSettingsQueue()
        assert queue.is_empty()
        assert queue.count() == 0
        assert queue.entries() == []

    def test_add_single_entry(self):
        queue = PendingSettingsQueue()
        result = queue.add("DayTimeSpeedRate", 1.5)
        assert result is True
        assert queue.count() == 1
        assert not queue.is_empty()
        assert queue.entries() == [("DayTimeSpeedRate", 1.5)]

    def test_add_multiple_entries(self):
        queue = PendingSettingsQueue()
        queue.add("DayTimeSpeedRate", 1.5)
        queue.add("NightTimeSpeedRate", 2.0)
        queue.add("ExpRate", 3.0)
        assert queue.count() == 3
        assert queue.entries() == [
            ("DayTimeSpeedRate", 1.5),
            ("NightTimeSpeedRate", 2.0),
            ("ExpRate", 3.0),
        ]

    def test_last_writer_wins_same_key(self):
        queue = PendingSettingsQueue()
        queue.add("DayTimeSpeedRate", 1.0)
        queue.add("NightTimeSpeedRate", 2.0)
        queue.add("DayTimeSpeedRate", 3.0)
        # Count should still be 2 (deduplication)
        assert queue.count() == 2
        # Order preserved (DayTimeSpeedRate was first-seen first)
        assert queue.entries() == [
            ("DayTimeSpeedRate", 3.0),
            ("NightTimeSpeedRate", 2.0),
        ]

    def test_add_returns_true_for_existing_key_update(self):
        queue = PendingSettingsQueue()
        queue.add("DayTimeSpeedRate", 1.0)
        result = queue.add("DayTimeSpeedRate", 2.0)
        assert result is True

    def test_capacity_limit(self):
        queue = PendingSettingsQueue()
        # Fill to capacity
        for i in range(MAX_PENDING_ENTRIES):
            result = queue.add(f"Key{i}", i)
            assert result is True
        assert queue.count() == MAX_PENDING_ENTRIES

        # New key should be rejected
        result = queue.add("NewKey", "value")
        assert result is False
        assert queue.count() == MAX_PENDING_ENTRIES

    def test_update_existing_key_at_capacity(self):
        queue = PendingSettingsQueue()
        # Fill to capacity
        for i in range(MAX_PENDING_ENTRIES):
            queue.add(f"Key{i}", i)

        # Updating existing key should succeed
        result = queue.add("Key50", "updated")
        assert result is True
        assert queue.count() == MAX_PENDING_ENTRIES

    def test_clear(self):
        queue = PendingSettingsQueue()
        queue.add("DayTimeSpeedRate", 1.5)
        queue.add("NightTimeSpeedRate", 2.0)
        queue.clear()
        assert queue.is_empty()
        assert queue.count() == 0
        assert queue.entries() == []

    def test_clear_empty_queue(self):
        queue = PendingSettingsQueue()
        queue.clear()  # Should not raise
        assert queue.is_empty()

    def test_apply_empty_queue(self):
        queue = PendingSettingsQueue()
        result = queue.apply(Path("/nonexistent/path"))
        assert result.applied_count == 0
        assert result.remaining_count == 0
        assert result.failed_key is None
        assert result.error_message is None

    @patch("src.pending_settings.SettingsParser.write_setting")
    def test_apply_success(self, mock_write):
        mock_write.return_value = ValidationResult(valid=True)
        queue = PendingSettingsQueue()
        queue.add("DayTimeSpeedRate", 1.5)
        queue.add("NightTimeSpeedRate", 2.0)

        result = queue.apply(Path("/fake/path"))

        assert result.applied_count == 2
        assert result.remaining_count == 0
        assert result.failed_key is None
        assert queue.is_empty()
        assert mock_write.call_count == 2

    @patch("src.pending_settings.SettingsParser.write_setting")
    def test_apply_failure_retains_remaining(self, mock_write):
        # First call succeeds, second fails
        mock_write.side_effect = [
            ValidationResult(valid=True),
            ValidationResult(valid=False, error_message="Disk full"),
        ]
        queue = PendingSettingsQueue()
        queue.add("Key1", "val1")
        queue.add("Key2", "val2")
        queue.add("Key3", "val3")

        result = queue.apply(Path("/fake/path"))

        assert result.applied_count == 1
        assert result.failed_key == "Key2"
        assert result.error_message == "Disk full"
        assert result.remaining_count == 2
        # Queue retains Key2 and Key3
        assert queue.count() == 2
        assert queue.entries() == [("Key2", "val2"), ("Key3", "val3")]

    @patch("src.pending_settings.SettingsParser.write_setting")
    def test_apply_first_entry_fails(self, mock_write):
        mock_write.return_value = ValidationResult(
            valid=False, error_message="Cannot write"
        )
        queue = PendingSettingsQueue()
        queue.add("Key1", "val1")
        queue.add("Key2", "val2")

        result = queue.apply(Path("/fake/path"))

        assert result.applied_count == 0
        assert result.failed_key == "Key1"
        assert result.error_message == "Cannot write"
        assert result.remaining_count == 2
        # All entries retained
        assert queue.count() == 2
        assert queue.entries() == [("Key1", "val1"), ("Key2", "val2")]


class TestMaxPendingEntries:
    """Tests for the MAX_PENDING_ENTRIES constant."""

    def test_value_is_100(self):
        assert MAX_PENDING_ENTRIES == 100
