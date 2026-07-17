"""Unit tests for the ControlPanel widget class.

Covers:
- __init__ creates buttons with correct labels (Req 6.1, 6.2, 6.3)
- update_button_states() with MONITORING state (Req 6.7)
- update_button_states() with RUNNING state (Req 6.7)
- update_button_states() with STARTING state (Req 6.7)
- update_button_states() with STOPPING state (Req 6.7)
- set_loading(True) disables all buttons and shows indicator (Req 6.5)
- set_loading(False) hides indicator (Req 6.6)
- Button callbacks wired correctly
- CTkButton styling (fg_color, corner_radius) (Req 6.1, 6.2, 6.3)
- Grid layout with equal column weights (Req 6.4)
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.models import ServerState
from src.gui_theme import (
    BUTTON_CORNER_RADIUS,
    COLOR_DISABLED,
    COLOR_PRIMARY,
    COLOR_TEXT_SECONDARY,
    FONT_BODY,
    WIDGET_INNER_SPACING,
)


@pytest.fixture
def mock_ctk():
    """Patch customtkinter for headless testing."""
    with patch("src.gui_interface.customtkinter") as mock_ctk_module:
        # Set up mock CTkFrame
        mock_frame_cls = MagicMock()
        mock_ctk_module.CTkFrame = mock_frame_cls

        # Set up mock CTkButton
        mock_button_cls = MagicMock()
        mock_ctk_module.CTkButton = mock_button_cls

        # Set up mock CTkLabel
        mock_label_cls = MagicMock()
        mock_ctk_module.CTkLabel = mock_label_cls

        yield mock_ctk_module


@pytest.fixture
def callbacks():
    """Create mock callback functions for the control panel."""
    return {
        "on_start": MagicMock(),
        "on_stop": MagicMock(),
        "on_restart": MagicMock(),
    }


@pytest.fixture
def control_panel(mock_ctk, callbacks):
    """Create a ControlPanel instance with mocked customtkinter."""
    from src.gui_interface import ControlPanel

    parent = MagicMock()
    panel = ControlPanel(
        parent,
        on_start=callbacks["on_start"],
        on_stop=callbacks["on_stop"],
        on_restart=callbacks["on_restart"],
    )
    return panel


class TestControlPanelInit:
    """Tests for ControlPanel initialization."""

    def test_is_ctk_frame(self, mock_ctk, callbacks):
        """ControlPanel should inherit from customtkinter.CTkFrame."""
        from src.gui_interface import ControlPanel
        import customtkinter

        # CTkFrame is the base class (patched)
        assert ControlPanel.__bases__[0] is customtkinter.CTkFrame

    def test_has_start_button(self, control_panel, mock_ctk):
        """ControlPanel should create a 'Start Server' CTkButton."""
        # Verify CTkButton was called with 'Start Server' text
        calls = mock_ctk.CTkButton.call_args_list
        start_call = [c for c in calls if c[1].get("text") == "Start Server"]
        assert len(start_call) == 1

    def test_has_stop_button(self, control_panel, mock_ctk):
        """ControlPanel should create a 'Stop Server' CTkButton."""
        calls = mock_ctk.CTkButton.call_args_list
        stop_call = [c for c in calls if c[1].get("text") == "Stop Server"]
        assert len(stop_call) == 1

    def test_has_restart_button(self, control_panel, mock_ctk):
        """ControlPanel should create a 'Restart Server' CTkButton."""
        calls = mock_ctk.CTkButton.call_args_list
        restart_call = [c for c in calls if c[1].get("text") == "Restart Server"]
        assert len(restart_call) == 1

    def test_buttons_use_primary_color(self, control_panel, mock_ctk):
        """CTkButtons should use COLOR_PRIMARY as fg_color."""
        calls = mock_ctk.CTkButton.call_args_list
        for call in calls:
            assert call[1].get("fg_color") == COLOR_PRIMARY

    def test_buttons_use_button_corner_radius(self, control_panel, mock_ctk):
        """CTkButtons should use BUTTON_CORNER_RADIUS."""
        calls = mock_ctk.CTkButton.call_args_list
        for call in calls:
            assert call[1].get("corner_radius") == BUTTON_CORNER_RADIUS

    def test_has_loading_label(self, control_panel, mock_ctk):
        """ControlPanel should create a loading indicator CTkLabel."""
        calls = mock_ctk.CTkLabel.call_args_list
        loading_call = [c for c in calls if c[1].get("text") == "Operation in progress..."]
        assert len(loading_call) == 1

    def test_loading_label_uses_secondary_text_color(self, control_panel, mock_ctk):
        """Loading label should use COLOR_TEXT_SECONDARY."""
        calls = mock_ctk.CTkLabel.call_args_list
        loading_call = [c for c in calls if c[1].get("text") == "Operation in progress..."]
        assert loading_call[0][1].get("text_color") == COLOR_TEXT_SECONDARY

    def test_grid_columns_configured_with_equal_weight(self, control_panel):
        """ControlPanel should configure 3 columns with equal weight."""
        # columnconfigure is called on the panel (self) which is the mock's return value
        columnconfigure_calls = control_panel.columnconfigure.call_args_list
        assert len(columnconfigure_calls) == 3
        for i, call in enumerate(columnconfigure_calls):
            assert call[0][0] == i
            assert call[1].get("weight") == 1


class TestControlPanelButtonStates:
    """Tests for update_button_states() with different ServerState values."""

    def test_monitoring_enables_start_and_restart(self, control_panel):
        """MONITORING: Start=enabled (primary), Stop=disabled (gray), Restart=enabled (primary)."""
        control_panel.update_button_states(ServerState.MONITORING)

        control_panel._start_button.configure.assert_any_call(state="normal", fg_color=COLOR_PRIMARY)
        control_panel._stop_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)
        control_panel._restart_button.configure.assert_any_call(state="normal", fg_color=COLOR_PRIMARY)

    def test_running_enables_stop_and_restart(self, control_panel):
        """RUNNING: Start=disabled (gray), Stop=enabled (primary), Restart=enabled (primary)."""
        control_panel.update_button_states(ServerState.RUNNING)

        control_panel._start_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)
        control_panel._stop_button.configure.assert_any_call(state="normal", fg_color=COLOR_PRIMARY)
        control_panel._restart_button.configure.assert_any_call(state="normal", fg_color=COLOR_PRIMARY)

    def test_starting_disables_all(self, control_panel):
        """STARTING: All buttons disabled with gray color."""
        control_panel.update_button_states(ServerState.STARTING)

        control_panel._start_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)
        control_panel._stop_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)
        control_panel._restart_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)

    def test_stopping_disables_all(self, control_panel):
        """STOPPING: All buttons disabled with gray color."""
        control_panel.update_button_states(ServerState.STOPPING)

        control_panel._start_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)
        control_panel._stop_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)
        control_panel._restart_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)

    def test_starting_shows_loading_indicator(self, control_panel):
        """STARTING: Loading indicator should be shown via grid."""
        control_panel.update_button_states(ServerState.STARTING)

        control_panel._loading_label.grid.assert_called()

    def test_stopping_shows_loading_indicator(self, control_panel):
        """STOPPING: Loading indicator should be shown via grid."""
        control_panel.update_button_states(ServerState.STOPPING)

        control_panel._loading_label.grid.assert_called()

    def test_monitoring_hides_loading_indicator(self, control_panel):
        """MONITORING: Loading indicator should be hidden via grid_remove."""
        control_panel.update_button_states(ServerState.STARTING)
        control_panel.update_button_states(ServerState.MONITORING)

        control_panel._loading_label.grid_remove.assert_called()

    def test_running_hides_loading_indicator(self, control_panel):
        """RUNNING: Loading indicator should be hidden via grid_remove."""
        control_panel.update_button_states(ServerState.STARTING)
        control_panel.update_button_states(ServerState.RUNNING)

        control_panel._loading_label.grid_remove.assert_called()


class TestControlPanelLoading:
    """Tests for set_loading() method."""

    def test_set_loading_true_disables_all_buttons(self, control_panel):
        """set_loading(True) should disable all buttons with disabled color."""
        control_panel.set_loading(True)

        control_panel._start_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)
        control_panel._stop_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)
        control_panel._restart_button.configure.assert_any_call(state="disabled", fg_color=COLOR_DISABLED)

    def test_set_loading_true_shows_indicator(self, control_panel):
        """set_loading(True) should show the loading indicator via grid."""
        control_panel.set_loading(True)

        control_panel._loading_label.grid.assert_called()

    def test_set_loading_false_hides_indicator(self, control_panel):
        """set_loading(False) should hide the loading indicator via grid_remove."""
        control_panel.set_loading(True)
        control_panel.set_loading(False)

        control_panel._loading_label.grid_remove.assert_called()


class TestControlPanelCallbacks:
    """Tests for button callback wiring."""

    def test_start_button_wired_to_on_start(self, control_panel, mock_ctk, callbacks):
        """Start button should be created with on_start command."""
        calls = mock_ctk.CTkButton.call_args_list
        start_call = [c for c in calls if c[1].get("text") == "Start Server"]
        assert start_call[0][1].get("command") == callbacks["on_start"]

    def test_stop_button_wired_to_on_stop(self, control_panel, mock_ctk, callbacks):
        """Stop button should be created with on_stop command."""
        calls = mock_ctk.CTkButton.call_args_list
        stop_call = [c for c in calls if c[1].get("text") == "Stop Server"]
        assert stop_call[0][1].get("command") == callbacks["on_stop"]

    def test_restart_button_wired_to_on_restart(self, control_panel, mock_ctk, callbacks):
        """Restart button should be created with on_restart command."""
        calls = mock_ctk.CTkButton.call_args_list
        restart_call = [c for c in calls if c[1].get("text") == "Restart Server"]
        assert restart_call[0][1].get("command") == callbacks["on_restart"]


class TestControlPanelGridLayout:
    """Tests for grid-based layout (Req 6.4)."""

    def test_start_button_in_column_0(self, control_panel):
        """Start button should be placed in row 0, column 0."""
        grid_call = control_panel._start_button.grid.call_args
        assert grid_call[1].get("row") == 0
        assert grid_call[1].get("column") == 0

    def test_stop_button_in_column_1(self, control_panel):
        """Stop button should be placed in row 0, column 1."""
        grid_call = control_panel._stop_button.grid.call_args
        assert grid_call[1].get("row") == 0
        assert grid_call[1].get("column") == 1

    def test_restart_button_in_column_2(self, control_panel):
        """Restart button should be placed in row 0, column 2."""
        grid_call = control_panel._restart_button.grid.call_args
        assert grid_call[1].get("row") == 0
        assert grid_call[1].get("column") == 2

    def test_loading_label_spans_all_columns_when_shown(self, control_panel):
        """Loading label should span 3 columns when shown."""
        control_panel._show_loading()
        grid_call = control_panel._loading_label.grid.call_args
        assert grid_call[1].get("columnspan") == 3
        assert grid_call[1].get("row") == 1
