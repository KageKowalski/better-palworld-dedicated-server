"""Unit tests for the NotificationBar widget class.

Uses mock-based approach to avoid creating real tkinter/customtkinter windows,
which would cause process hangs on Windows due to customtkinter's Tcl/Tk
C-library cleanup issues.
"""

from unittest.mock import MagicMock

import pytest

from src.gui_theme import COLOR_ALERT, COLOR_SUCCESS


@pytest.fixture
def notification_bar():
    """Create a NotificationBar with manually-constructed internal state.

    Rather than trying to mock every tkinter widget call in __init__,
    we use object.__new__() to bypass __init__ entirely and set up only
    the attributes that the public methods need.
    """
    from src.gui_interface import NotificationBar

    # Create instance without calling __init__
    bar = object.__new__(NotificationBar)

    # Set up internal state that __init__ normally creates
    bar._after_id = None
    bar._is_visible = False

    # Mock message label (tracks text and text_color via configure)
    label_state = {"text": "", "text_color": ""}
    mock_label = MagicMock()
    mock_label.configure = lambda **kwargs: label_state.update(kwargs)
    mock_label.cget = lambda key: label_state.get(key, "")
    bar._message_label = mock_label
    bar._label_state = label_state

    # Mock dismiss button
    bar._dismiss_button = MagicMock()

    # Mock the toplevel winfo_toplevel (needed for after() scheduling)
    mock_toplevel = MagicMock()
    # after() returns a unique ID each time
    _after_counter = [0]

    def mock_after(ms, callback):
        _after_counter[0] += 1
        return f"after#{_after_counter[0]}"

    mock_toplevel.after = mock_after
    mock_toplevel.after_cancel = MagicMock()
    bar.winfo_toplevel = lambda: mock_toplevel
    bar._mock_toplevel = mock_toplevel

    # Mock grid/grid_remove for visibility tracking
    bar.grid = MagicMock()
    bar.grid_remove = MagicMock()

    # Mock parent card frame (NotificationBar shows/hides its parent card)
    mock_parent_card = MagicMock()
    bar._parent_card = mock_parent_card

    return bar


class TestNotificationBarInit:
    """Tests for NotificationBar initialization state."""

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
        """show_success should configure the message label with the text."""
        notification_bar.show_success("Server started successfully")
        assert notification_bar._label_state["text"] == "Server started successfully"

    def test_sets_success_text_color(self, notification_bar):
        """show_success should set COLOR_SUCCESS text color for success messages."""
        notification_bar.show_success("Success!")
        assert notification_bar._label_state["text_color"] == COLOR_SUCCESS

    def test_schedules_auto_dismiss(self, notification_bar):
        """show_success should schedule an auto-dismiss callback."""
        notification_bar.show_success("Auto dismiss me")
        assert notification_bar._after_id is not None

    def test_replaces_previous_notification(self, notification_bar):
        """show_success should replace any existing notification."""
        notification_bar.show_error("Error first")
        notification_bar.show_success("Now success")
        assert notification_bar._label_state["text"] == "Now success"
        assert notification_bar._label_state["text_color"] == COLOR_SUCCESS

    def test_cancels_previous_auto_dismiss(self, notification_bar):
        """show_success should cancel any previous auto-dismiss callback."""
        notification_bar.show_success("First message")
        first_after_id = notification_bar._after_id
        notification_bar.show_success("Second message")
        # The after_id should be different (new callback scheduled)
        assert notification_bar._after_id != first_after_id

    def test_auto_dismiss_hides_bar(self, notification_bar):
        """After auto-dismiss fires, the bar should be hidden."""
        notification_bar.show_success("Temporary message")
        # Simulate the after() callback firing by calling dismiss directly
        notification_bar.dismiss()
        assert notification_bar._is_visible is False
        assert notification_bar._after_id is None

    def test_show_uses_grid(self, notification_bar):
        """show_success should use grid() to make the bar visible."""
        notification_bar.show_success("Test")
        notification_bar.grid.assert_called()


class TestShowError:
    """Tests for NotificationBar.show_error()."""

    def test_shows_bar(self, notification_bar):
        """show_error should make the bar visible."""
        notification_bar.show_error("Something went wrong")
        assert notification_bar._is_visible is True

    def test_sets_message_text(self, notification_bar):
        """show_error should set the message label text."""
        notification_bar.show_error("Connection failed")
        assert notification_bar._label_state["text"] == "Connection failed"

    def test_sets_alert_text_color(self, notification_bar):
        """show_error should set COLOR_ALERT text color for error messages."""
        notification_bar.show_error("Error!")
        assert notification_bar._label_state["text_color"] == COLOR_ALERT

    def test_no_auto_dismiss(self, notification_bar):
        """show_error should NOT schedule an auto-dismiss callback."""
        notification_bar.show_error("Persistent error")
        assert notification_bar._after_id is None

    def test_replaces_previous_success(self, notification_bar):
        """show_error should replace a previous success notification."""
        notification_bar.show_success("Was success")
        notification_bar.show_error("Now error")
        assert notification_bar._label_state["text"] == "Now error"
        assert notification_bar._label_state["text_color"] == COLOR_ALERT
        # Previous auto-dismiss should be cancelled
        assert notification_bar._after_id is None

    def test_show_uses_grid(self, notification_bar):
        """show_error should use grid() to make the bar visible."""
        notification_bar.show_error("Test error")
        notification_bar.grid.assert_called()


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

    def test_hide_uses_grid_remove(self, notification_bar):
        """dismiss should use grid_remove() to hide the bar."""
        notification_bar.show_success("Dismiss me")
        notification_bar.dismiss()
        notification_bar.grid_remove.assert_called()
