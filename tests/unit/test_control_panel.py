"""Unit tests for the ControlPanel widget class.

Covers:
- __init__ creates buttons with correct labels (Req 3.1, 3.2, 3.3)
- update_button_states() with MONITORING state (Req 3.4)
- update_button_states() with RUNNING state (Req 3.5)
- update_button_states() with STARTING state (Req 3.6)
- update_button_states() with STOPPING state (Req 3.6)
- set_loading(True) disables all buttons and shows indicator (Req 3.9)
- set_loading(False) hides indicator (Req 3.9)
- Button callbacks wired correctly
"""

import tkinter as tk
from tkinter import ttk
from unittest.mock import MagicMock, patch

import pytest

from src.gui_interface import ControlPanel
from src.models import ServerState


@pytest.fixture
def root():
    """Create a tkinter root window for testing (requires display)."""
    try:
        root = tk.Tk()
        root.withdraw()  # Hide window during tests
        yield root
        root.destroy()
    except tk.TclError:
        pytest.skip("No display environment available for tkinter tests")


@pytest.fixture
def callbacks():
    """Create mock callback functions for the control panel."""
    return {
        "on_start": MagicMock(),
        "on_stop": MagicMock(),
        "on_restart": MagicMock(),
    }


@pytest.fixture
def control_panel(root, callbacks):
    """Create a ControlPanel instance for testing."""
    panel = ControlPanel(
        root,
        on_start=callbacks["on_start"],
        on_stop=callbacks["on_stop"],
        on_restart=callbacks["on_restart"],
    )
    panel.pack()
    return panel


class TestControlPanelInit:
    """Tests for ControlPanel initialization."""

    def test_is_labeled_frame_with_server_control_text(self, control_panel):
        """ControlPanel should be a LabelFrame with 'Server Control' label."""
        assert isinstance(control_panel, ttk.LabelFrame)
        assert control_panel.cget("text") == "Server Control"

    def test_has_start_button(self, control_panel):
        """ControlPanel should contain a 'Start Server' button."""
        assert control_panel._start_button.cget("text") == "Start Server"

    def test_has_stop_button(self, control_panel):
        """ControlPanel should contain a 'Stop Server' button."""
        assert control_panel._stop_button.cget("text") == "Stop Server"

    def test_has_restart_button(self, control_panel):
        """ControlPanel should contain a 'Restart Server' button."""
        assert control_panel._restart_button.cget("text") == "Restart Server"

    def test_has_loading_label(self, control_panel):
        """ControlPanel should have a loading indicator label."""
        assert control_panel._loading_label.cget("text") == "Operation in progress..."

    def test_default_state_is_monitoring(self, control_panel):
        """ControlPanel should initialize with MONITORING state (Start/Restart enabled, Stop disabled)."""
        assert str(control_panel._start_button.cget("state")) == "normal"
        assert str(control_panel._stop_button.cget("state")) == "disabled"
        assert str(control_panel._restart_button.cget("state")) == "normal"


class TestControlPanelButtonStates:
    """Tests for update_button_states() with different ServerState values."""

    def test_monitoring_enables_start_and_restart(self, control_panel):
        """MONITORING: Start=enabled, Stop=disabled, Restart=enabled."""
        control_panel.update_button_states(ServerState.MONITORING)

        assert str(control_panel._start_button.cget("state")) == "normal"
        assert str(control_panel._stop_button.cget("state")) == "disabled"
        assert str(control_panel._restart_button.cget("state")) == "normal"

    def test_running_enables_stop_and_restart(self, control_panel):
        """RUNNING: Start=disabled, Stop=enabled, Restart=enabled."""
        control_panel.update_button_states(ServerState.RUNNING)

        assert str(control_panel._start_button.cget("state")) == "disabled"
        assert str(control_panel._stop_button.cget("state")) == "normal"
        assert str(control_panel._restart_button.cget("state")) == "normal"

    def test_starting_disables_all(self, control_panel):
        """STARTING: All buttons disabled."""
        control_panel.update_button_states(ServerState.STARTING)

        assert str(control_panel._start_button.cget("state")) == "disabled"
        assert str(control_panel._stop_button.cget("state")) == "disabled"
        assert str(control_panel._restart_button.cget("state")) == "disabled"

    def test_stopping_disables_all(self, control_panel):
        """STOPPING: All buttons disabled."""
        control_panel.update_button_states(ServerState.STOPPING)

        assert str(control_panel._start_button.cget("state")) == "disabled"
        assert str(control_panel._stop_button.cget("state")) == "disabled"
        assert str(control_panel._restart_button.cget("state")) == "disabled"

    def test_starting_shows_loading_indicator(self, control_panel):
        """STARTING: Loading indicator should be shown."""
        control_panel.update_button_states(ServerState.STARTING)

        # Loading label should be packed (visible)
        assert control_panel._loading_label.winfo_manager() == "pack"

    def test_stopping_shows_loading_indicator(self, control_panel):
        """STOPPING: Loading indicator should be shown."""
        control_panel.update_button_states(ServerState.STOPPING)

        assert control_panel._loading_label.winfo_manager() == "pack"

    def test_monitoring_hides_loading_indicator(self, control_panel):
        """MONITORING: Loading indicator should be hidden."""
        # First show it
        control_panel.update_button_states(ServerState.STARTING)
        # Then go to monitoring
        control_panel.update_button_states(ServerState.MONITORING)

        assert control_panel._loading_label.winfo_manager() == ""

    def test_running_hides_loading_indicator(self, control_panel):
        """RUNNING: Loading indicator should be hidden."""
        # First show it
        control_panel.update_button_states(ServerState.STARTING)
        # Then go to running
        control_panel.update_button_states(ServerState.RUNNING)

        assert control_panel._loading_label.winfo_manager() == ""


class TestControlPanelLoading:
    """Tests for set_loading() method."""

    def test_set_loading_true_disables_all_buttons(self, control_panel):
        """set_loading(True) should disable all buttons."""
        control_panel.set_loading(True)

        assert str(control_panel._start_button.cget("state")) == "disabled"
        assert str(control_panel._stop_button.cget("state")) == "disabled"
        assert str(control_panel._restart_button.cget("state")) == "disabled"

    def test_set_loading_true_shows_indicator(self, control_panel):
        """set_loading(True) should show the loading indicator."""
        control_panel.set_loading(True)

        assert control_panel._loading_label.winfo_manager() == "pack"

    def test_set_loading_false_hides_indicator(self, control_panel):
        """set_loading(False) should hide the loading indicator."""
        control_panel.set_loading(True)
        control_panel.set_loading(False)

        assert control_panel._loading_label.winfo_manager() == ""


class TestControlPanelCallbacks:
    """Tests for button callback wiring."""

    def test_start_button_invokes_on_start(self, control_panel, callbacks):
        """Clicking 'Start Server' should invoke the on_start callback."""
        control_panel._start_button.invoke()
        callbacks["on_start"].assert_called_once()

    def test_stop_button_invokes_on_stop(self, control_panel, callbacks):
        """Clicking 'Stop Server' should invoke the on_stop callback."""
        # Enable stop button first (it's disabled in MONITORING state)
        control_panel.update_button_states(ServerState.RUNNING)
        control_panel._stop_button.invoke()
        callbacks["on_stop"].assert_called_once()

    def test_restart_button_invokes_on_restart(self, control_panel, callbacks):
        """Clicking 'Restart Server' should invoke the on_restart callback."""
        control_panel._restart_button.invoke()
        callbacks["on_restart"].assert_called_once()
