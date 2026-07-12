"""Unit tests for the NotificationBar widget class."""

import tkinter as tk
from unittest.mock import patch, MagicMock

import pytest

from src.gui_interface import NotificationBar


@pytest.fixture
def root():
    """Create a tkinter root window for testing."""
    try:
        root = tk.Tk()
        root.withdraw()  # Hide the window during tests
        yield root
        root.destroy()
    except tk.TclError:
        pytest.skip("No display available for tkinter tests")


@pytest.fixture
def notification_bar(root):
    """Create a NotificationBar instance for testing."""
    bar = NotificationBar(root)
    return bar


class TestNotificationBarInit:
    """Tests for NotificationBar initialization."""

    def test_starts_hidden(self, notification_bar):
        """NotificationBar should be hidden initially (no notification)."""
        assert notification_bar._is_visible is False

    def test_has_message_label(self, notification_bar):
        """NotificationBar should have a message label widget."""
        assert notification_bar._message_label is not None

    def test_has_dismiss_button(self, notification_bar):
        """NotificationBar should have a dismiss button."""
        assert notification_bar._dismiss_button is not None

    def test_no_pending_after_id(self, notification_bar):
        """NotificationBar should have no pending after callback initially."""
        assert notification_bar._after_id is None


class TestShowSuccess:
    """Tests for NotificationBar.show_success()."""

    def test_shows_bar(self, notification_bar):
        """show_success should make the bar visible."""
        notification_bar.show_success("Operation completed")
        assert notification_bar._is_visible is True

    def test_sets_message_text(self, notification_bar):
        """show_success should set the message label text."""
        notification_bar.show_success("Server started successfully")
        assert notification_bar._message_label.cget("text") == "Server started successfully"

    def test_sets_green_foreground(self, notification_bar):
        """show_success should set green text color for success messages."""
        notification_bar.show_success("Success!")
        assert str(notification_bar._message_label.cget("foreground")) == "green"

    def test_schedules_auto_dismiss(self, notification_bar):
        """show_success should schedule an auto-dismiss callback."""
        notification_bar.show_success("Auto dismiss me")
        assert notification_bar._after_id is not None

    def test_replaces_previous_notification(self, notification_bar):
        """show_success should replace any existing notification."""
        notification_bar.show_error("Error first")
        notification_bar.show_success("Now success")
        assert notification_bar._message_label.cget("text") == "Now success"
        assert str(notification_bar._message_label.cget("foreground")) == "green"

    def test_cancels_previous_auto_dismiss(self, notification_bar, root):
        """show_success should cancel any previous auto-dismiss callback."""
        notification_bar.show_success("First message")
        first_after_id = notification_bar._after_id
        notification_bar.show_success("Second message")
        # The after_id should be different (new callback scheduled)
        assert notification_bar._after_id != first_after_id

    def test_auto_dismiss_hides_bar(self, notification_bar, root):
        """After 5 seconds, the bar should be hidden via auto-dismiss."""
        notification_bar.show_success("Temporary message")
        # Simulate the after() callback firing
        notification_bar.dismiss()
        assert notification_bar._is_visible is False
        assert notification_bar._after_id is None


class TestShowError:
    """Tests for NotificationBar.show_error()."""

    def test_shows_bar(self, notification_bar):
        """show_error should make the bar visible."""
        notification_bar.show_error("Something went wrong")
        assert notification_bar._is_visible is True

    def test_sets_message_text(self, notification_bar):
        """show_error should set the message label text."""
        notification_bar.show_error("Connection failed")
        assert notification_bar._message_label.cget("text") == "Connection failed"

    def test_sets_red_foreground(self, notification_bar):
        """show_error should set red text color for error messages."""
        notification_bar.show_error("Error!")
        assert str(notification_bar._message_label.cget("foreground")) == "red"

    def test_no_auto_dismiss(self, notification_bar):
        """show_error should NOT schedule an auto-dismiss callback."""
        notification_bar.show_error("Persistent error")
        assert notification_bar._after_id is None

    def test_persists_until_dismissed(self, notification_bar, root):
        """Error notification should remain visible until explicitly dismissed."""
        notification_bar.show_error("Stay visible")
        # Process events but bar should stay
        root.update_idletasks()
        assert notification_bar._is_visible is True

    def test_replaces_previous_success(self, notification_bar):
        """show_error should replace a previous success notification."""
        notification_bar.show_success("Was success")
        notification_bar.show_error("Now error")
        assert notification_bar._message_label.cget("text") == "Now error"
        assert str(notification_bar._message_label.cget("foreground")) == "red"
        # Previous auto-dismiss should be cancelled
        assert notification_bar._after_id is None


class TestDismiss:
    """Tests for NotificationBar.dismiss()."""

    def test_hides_bar(self, notification_bar):
        """dismiss should hide the notification bar."""
        notification_bar.show_success("Dismiss me")
        notification_bar.dismiss()
        assert notification_bar._is_visible is False

    def test_cancels_pending_callback(self, notification_bar):
        """dismiss should cancel any pending auto-dismiss callback."""
        notification_bar.show_success("Has callback")
        assert notification_bar._after_id is not None
        notification_bar.dismiss()
        assert notification_bar._after_id is None

    def test_safe_when_no_notification(self, notification_bar):
        """dismiss should be safe to call when no notification is visible."""
        # Should not raise any exception
        notification_bar.dismiss()
        assert notification_bar._is_visible is False

    def test_dismiss_error_notification(self, notification_bar):
        """dismiss should hide error notifications when called."""
        notification_bar.show_error("Error to dismiss")
        notification_bar.dismiss()
        assert notification_bar._is_visible is False
