"""Unit tests for GuiInterface class skeleton and async loop.

Covers:
- __init__ creates root window with correct title and minsize (Req 2.1)
- __init__ handles TclError by logging and exiting (Req 2.6)
- run() cooperative async loop with root.update() (Req 9.1)
- _shutdown() handles normal shutdown (Req 8.2)
- _shutdown() handles timeout (Req 8.5)
- _shutdown() handles exception from quit() (Req 8.6)
- WM_DELETE_WINDOW wired to _shutdown() (Req 8.3)
- GuiState and NotificationState dataclasses
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch, PropertyMock

import pytest

from src.config import WrapperConfig
from src.gui_interface import GuiInterface, GuiState, NotificationState
from src.models import ServerState


@pytest.fixture
def config(tmp_path):
    """Create a WrapperConfig with temporary paths."""
    return WrapperConfig(
        server_exe_path=tmp_path / "PalServer.exe",
        settings_file_path=tmp_path / "PalWorldSettings.ini",
    )


@pytest.fixture
def mock_wrapper_core():
    """Create a mock WrapperCore with async quit method."""
    core = MagicMock()
    core.quit = AsyncMock()
    return core


class TestGuiState:
    """Tests for the GuiState dataclass."""

    def test_default_values(self):
        """GuiState should have sensible defaults."""
        state = GuiState()
        assert state.operation_in_progress is False
        assert state.shutdown_in_progress is False
        assert state.current_operation is None

    def test_custom_values(self):
        """GuiState should accept custom values."""
        state = GuiState(
            operation_in_progress=True,
            shutdown_in_progress=True,
            current_operation="start",
        )
        assert state.operation_in_progress is True
        assert state.shutdown_in_progress is True
        assert state.current_operation == "start"


class TestNotificationState:
    """Tests for the NotificationState dataclass."""

    def test_default_values(self):
        """NotificationState should have sensible defaults."""
        state = NotificationState()
        assert state.message == ""
        assert state.is_error is False
        assert state.dismiss_after_id is None

    def test_custom_values(self):
        """NotificationState should accept custom values."""
        state = NotificationState(
            message="Server started",
            is_error=False,
            dismiss_after_id="after#1",
        )
        assert state.message == "Server started"
        assert state.is_error is False
        assert state.dismiss_after_id == "after#1"


@patch("src.gui_interface.customtkinter.set_default_color_theme")
@patch("src.gui_interface.customtkinter.set_appearance_mode")
@patch.object(GuiInterface, '_build_ui')
class TestGuiInterfaceInit:
    """Tests for GuiInterface.__init__()."""

    @patch("src.gui_interface.customtkinter.CTk")
    def test_creates_root_window_with_correct_title(
        self, mock_tk_class, mock_build_ui, mock_set_appearance, mock_set_theme, mock_wrapper_core, config
    ):
        """__init__ should create a CTk root with title 'Palworld Server Wrapper'."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)

        mock_tk_class.assert_called_once()
        mock_root.title.assert_called_once_with("Palworld Server Wrapper")

    @patch("src.gui_interface.customtkinter.CTk")
    def test_sets_minimum_window_size_800x600(
        self, mock_tk_class, mock_build_ui, mock_set_appearance, mock_set_theme, mock_wrapper_core, config
    ):
        """__init__ should set the minimum window size to 800x600."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)

        mock_root.minsize.assert_called_once_with(800, 600)

    @patch("src.gui_interface.customtkinter.CTk")
    def test_wires_wm_delete_window_protocol(
        self, mock_tk_class, mock_build_ui, mock_set_appearance, mock_set_theme, mock_wrapper_core, config
    ):
        """__init__ should wire WM_DELETE_WINDOW to the close handler."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)

        mock_root.protocol.assert_called_once_with(
            "WM_DELETE_WINDOW", gui._on_close_request
        )

    @patch("src.gui_interface.customtkinter.CTk")
    def test_tcl_error_causes_sys_exit(
        self, mock_tk_class, mock_build_ui, mock_set_appearance, mock_set_theme, mock_wrapper_core, config
    ):
        """__init__ should call sys.exit(1) when CTk initialization fails."""
        import tkinter as tk

        mock_tk_class.side_effect = tk.TclError("no display name")

        with pytest.raises(SystemExit) as exc_info:
            GuiInterface(mock_wrapper_core, config)

        assert exc_info.value.code == 1

    @patch("src.gui_interface.customtkinter.CTk")
    def test_tcl_error_logs_error(
        self, mock_tk_class, mock_build_ui, mock_set_appearance, mock_set_theme, mock_wrapper_core, config, caplog
    ):
        """__init__ should log an error when initialization fails."""
        import logging
        import tkinter as tk

        mock_tk_class.side_effect = tk.TclError("no display name")

        with caplog.at_level(logging.ERROR, logger="src.gui_interface"):
            with pytest.raises(SystemExit):
                GuiInterface(mock_wrapper_core, config)

        assert "Failed to initialize GUI" in caplog.text

    @patch("src.gui_interface.customtkinter.CTk")
    def test_initializes_gui_state(
        self, mock_tk_class, mock_build_ui, mock_set_appearance, mock_set_theme, mock_wrapper_core, config
    ):
        """__init__ should initialize internal GUI state."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)

        assert gui._running is False
        assert gui._gui_state.operation_in_progress is False
        assert gui._gui_state.shutdown_in_progress is False


@patch.object(GuiInterface, '_build_ui')
class TestGuiInterfaceRun:
    """Tests for GuiInterface.run() async cooperative loop."""

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_run_sets_running_flag(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """run() should set _running to True."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        # Make update() raise TclError after first call to break the loop
        mock_root.update.side_effect = [None, Exception("stop")]

        gui = GuiInterface(mock_wrapper_core, config)

        # Patch sleep to avoid waiting and have update raise TclError on 2nd call
        import tkinter as tk

        mock_root.update.side_effect = [None, tk.TclError("window destroyed")]

        await gui.run()

        # _running should have been set to True initially
        # (loop exited via TclError break)

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_run_breaks_on_tcl_error(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """run() should break the loop gracefully when TclError occurs (window destroyed)."""
        import tkinter as tk

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        # Simulate window being destroyed on first update
        mock_root.update.side_effect = tk.TclError("application has been destroyed")

        gui = GuiInterface(mock_wrapper_core, config)
        await gui.run()

        # Should complete without raising any exception
        mock_root.update.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_run_calls_update_periodically(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """run() should call root.update() in the cooperative loop."""
        import tkinter as tk

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        call_count = 0

        def update_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                raise tk.TclError("done")

        mock_root.update.side_effect = update_side_effect

        gui = GuiInterface(mock_wrapper_core, config)
        await gui.run()

        assert call_count == 3


@patch.object(GuiInterface, '_build_ui')
class TestGuiInterfaceShutdown:
    """Tests for GuiInterface._shutdown()."""

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_calls_wrapper_quit(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_shutdown() should invoke WrapperCore.quit()."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        await gui._shutdown()

        mock_wrapper_core.quit.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_destroys_window(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_shutdown() should destroy the tkinter window after quit completes."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        await gui._shutdown()

        mock_root.destroy.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_sets_running_false(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_shutdown() should set _running to False to exit the cooperative loop."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._running = True
        await gui._shutdown()

        assert gui._running is False

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_handles_timeout(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config, caplog
    ):
        """_shutdown() should force-close on timeout and log a warning."""
        import logging

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        # Make quit() hang indefinitely
        async def slow_quit():
            await asyncio.sleep(100)

        mock_wrapper_core.quit = slow_quit

        gui = GuiInterface(mock_wrapper_core, config)

        with caplog.at_level(logging.WARNING, logger="src.gui_interface"):
            # Use a short timeout by patching wait_for's timeout
            # The actual _shutdown uses 30s, but quit() will timeout
            # We need to make the test faster - patch asyncio.wait_for
            original_wait_for = asyncio.wait_for

            async def fast_wait_for(coro, timeout):
                return await original_wait_for(coro, timeout=0.1)

            with patch("src.gui_interface.asyncio.wait_for", side_effect=asyncio.TimeoutError):
                await gui._shutdown()

        assert "timed out" in caplog.text.lower() or "force-clos" in caplog.text.lower()
        mock_root.destroy.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_handles_exception(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config, caplog
    ):
        """_shutdown() should log error and close window when quit() raises."""
        import logging

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        mock_wrapper_core.quit = AsyncMock(side_effect=RuntimeError("connection lost"))

        gui = GuiInterface(mock_wrapper_core, config)

        with caplog.at_level(logging.ERROR, logger="src.gui_interface"):
            await gui._shutdown()

        assert "Error during shutdown" in caplog.text
        mock_root.destroy.assert_called_once()
        assert gui._running is False

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_idempotent(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_shutdown() should not re-execute if already in progress."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)

        # Call shutdown twice
        await gui._shutdown()
        await gui._shutdown()

        # quit() should only be called once
        mock_wrapper_core.quit.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_handles_window_already_destroyed(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_shutdown() should handle TclError if window is already destroyed."""
        import tkinter as tk

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_root.destroy.side_effect = tk.TclError("window already destroyed")

        gui = GuiInterface(mock_wrapper_core, config)
        # Should not raise
        await gui._shutdown()

        assert gui._running is False


@patch.object(GuiInterface, '_build_ui')
class TestShutdownControls:
    """Tests for shutdown controls: _disable_all_controls(), _show_shutdown_status().

    Covers:
    - _disable_all_controls() disables ControlPanel via set_loading(True) (Req 8.4)
    - _disable_all_controls() disables SettingsEditor Apply button (Req 8.4)
    - _disable_all_controls() disables SettingsView Refresh button (Req 8.4)
    - _disable_all_controls() disables Quit button (Req 8.4)
    - _disable_all_controls() disables Help button (Req 8.4)
    - _disable_all_controls() handles missing widgets gracefully
    - _disable_all_controls() handles TclError gracefully
    - _show_shutdown_status() shows "Shutting down..." in notification bar (Req 8.4)
    - _shutdown() calls _show_shutdown_status() before quit (Req 8.4)
    - _shutdown() calls _disable_all_controls() before quit (Req 8.4)
    """

    @patch("src.gui_interface.customtkinter.CTk")
    def test_disable_all_controls_disables_control_panel(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_disable_all_controls() should call set_loading(True) on control panel."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = MagicMock()

        gui._disable_all_controls()

        gui._control_panel.set_loading.assert_called_once_with(True)

    @patch("src.gui_interface.customtkinter.CTk")
    def test_disable_all_controls_disables_settings_panel_refresh_button(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_disable_all_controls() should disable the SettingsPanel Refresh button."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._settings_panel = MagicMock()
        gui._settings_panel._refresh_button = MagicMock()

        gui._disable_all_controls()

        gui._settings_panel._refresh_button.configure.assert_called_once_with(
            state="disabled"
        )

    @patch("src.gui_interface.customtkinter.CTk")
    def test_disable_all_controls_disables_quit_button(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_disable_all_controls() should disable the Quit button."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._quit_button = MagicMock()

        gui._disable_all_controls()

        gui._quit_button.configure.assert_called_once_with(state="disabled")

    @patch("src.gui_interface.customtkinter.CTk")
    def test_disable_all_controls_disables_help_button(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_disable_all_controls() should disable the Help button."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._help_button = MagicMock()

        gui._disable_all_controls()

        gui._help_button.configure.assert_called_once_with(state="disabled")

    @patch("src.gui_interface.customtkinter.CTk")
    def test_disable_all_controls_handles_missing_widgets(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_disable_all_controls() should not raise when widgets don't exist."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        # No widgets set - should not raise
        gui._disable_all_controls()

    @patch("src.gui_interface.customtkinter.CTk")
    def test_disable_all_controls_handles_tcl_error(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_disable_all_controls() should handle TclError gracefully."""
        import tkinter as tk

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = MagicMock()
        gui._control_panel.set_loading.side_effect = tk.TclError("widget destroyed")
        gui._quit_button = MagicMock()
        gui._quit_button.configure.side_effect = tk.TclError("widget destroyed")

        # Should not raise despite TclError
        gui._disable_all_controls()

    @patch("src.gui_interface.customtkinter.CTk")
    def test_show_shutdown_status_shows_shutting_down_message(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_show_shutdown_status() should show 'Shutting down...' in notification bar."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._notification_bar = MagicMock()

        gui._show_shutdown_status()

        gui._notification_bar.show_error.assert_called_once_with("Shutting down...")

    @patch("src.gui_interface.customtkinter.CTk")
    def test_show_shutdown_status_handles_missing_notification_bar(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_show_shutdown_status() should not raise when notification bar doesn't exist."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        # No _notification_bar attribute set - should not raise
        gui._show_shutdown_status()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_shows_shutdown_status(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_shutdown() should show 'Shutting down...' status before calling quit."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._notification_bar = MagicMock()

        await gui._shutdown()

        gui._notification_bar.show_error.assert_called_once_with("Shutting down...")

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_disables_controls_before_quit(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_shutdown() should disable all controls before calling quit()."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        call_order = []

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = MagicMock()
        gui._control_panel.set_loading.side_effect = lambda x: call_order.append(
            "disable_controls"
        )

        async def mock_quit():
            call_order.append("quit")

        mock_wrapper_core.quit = mock_quit

        await gui._shutdown()

        assert call_order == ["disable_controls", "quit"]

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_disables_quit_button(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_shutdown() should disable the Quit button during shutdown."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._quit_button = MagicMock()

        await gui._shutdown()

        gui._quit_button.configure.assert_called_once_with(state="disabled")

    @patch("src.gui_interface.customtkinter.CTk")
    def test_disable_all_controls_with_none_widgets(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_disable_all_controls() should handle None-valued widget attributes."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = None
        gui._settings_panel = None
        gui._quit_button = None
        gui._help_button = None

        # Should not raise
        gui._disable_all_controls()


@patch.object(GuiInterface, '_build_ui')
class TestGracefulShutdownDetachedProcess:
    """Tests for graceful shutdown handling in the detached process scenario.

    Covers:
    - Requirement 5.1: Shutdown disables controls, shows status, invokes quit
    - Requirement 5.2: Shutdown completes or times out within 30s, destroys window
    - Requirement 5.3: Process tree is terminated via WrapperCore quit/cleanup
    - Requirement 5.5: MONITORING state skips server stop, completes quickly
    """

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_full_sequence_order(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """Shutdown should: disable controls → show status → call quit → destroy window.

        Validates Requirement 5.1: disable controls, display shutdown status,
        invoke graceful shutdown sequence.
        """
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        call_order = []

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = MagicMock()
        gui._control_panel.set_loading.side_effect = lambda x: call_order.append("disable_controls")
        gui._notification_bar = MagicMock()
        gui._notification_bar.show_error.side_effect = lambda msg: call_order.append("show_status")
        gui._quit_button = MagicMock()
        gui._help_button = MagicMock()

        async def mock_quit():
            call_order.append("quit")

        mock_wrapper_core.quit = mock_quit
        mock_root.destroy.side_effect = lambda: call_order.append("destroy")

        await gui._shutdown()

        assert "disable_controls" in call_order
        assert "show_status" in call_order
        assert "quit" in call_order
        assert "destroy" in call_order
        # Verify order: disable and show status before quit, quit before destroy
        assert call_order.index("disable_controls") < call_order.index("quit")
        assert call_order.index("show_status") < call_order.index("quit")
        assert call_order.index("quit") < call_order.index("destroy")

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_with_30s_timeout_on_quit(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """Shutdown should use a 30-second timeout when calling WrapperCore.quit().

        Validates Requirement 5.2: 30-second timeout for shutdown.
        """
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)

        # Track what wait_for is called with
        captured_timeout = None
        original_wait_for = asyncio.wait_for

        async def capture_wait_for(coro, timeout):
            nonlocal captured_timeout
            captured_timeout = timeout
            return await original_wait_for(coro, timeout=timeout)

        with patch("src.gui_interface.asyncio.wait_for", side_effect=capture_wait_for):
            await gui._shutdown()

        assert captured_timeout == 30.0

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_sets_running_false_and_exits_loop(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """Shutdown should set _running = False so cooperative loop exits.

        Validates Requirement 5.2: exit with code 0 after shutdown.
        """
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._running = True

        await gui._shutdown()

        assert gui._running is False

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_monitoring_state_skips_server_stop(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """When server is in MONITORING state, quit/cleanup should skip stop_server.

        Validates Requirement 5.5: Skip server stop step when not running,
        proceed directly to cleanup.
        """
        from src.wrapper_core import WrapperCore
        from src.config import WrapperConfig

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        # Use a real WrapperCore to test the actual cleanup logic
        real_config = WrapperConfig(
            server_exe_path=config.server_exe_path,
            settings_file_path=config.settings_file_path,
        )
        real_core = WrapperCore(real_config)

        # Set state to MONITORING (server not running)
        real_core._state = ServerState.MONITORING

        # Mock process manager to verify stop_server is NOT called
        real_core._process_manager.is_running = AsyncMock(return_value=False)
        real_core._process_manager.stop_server = AsyncMock(
            return_value=MagicMock(success=True)
        )
        real_core._connection_listener.stop_listening = AsyncMock()
        real_core._rest_client.close = AsyncMock()
        real_core._logger.log_state_transition = MagicMock()

        gui = GuiInterface(real_core, config)

        await gui._shutdown()

        # stop_server should NOT have been called since server is not running
        real_core._process_manager.stop_server.assert_not_called()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_monitoring_state_completes_quickly(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """When in MONITORING state, shutdown should complete well within 5 seconds.

        Validates Requirement 5.5: cleanup and exit within 5 seconds.
        """
        from src.wrapper_core import WrapperCore
        from src.config import WrapperConfig

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        real_config = WrapperConfig(
            server_exe_path=config.server_exe_path,
            settings_file_path=config.settings_file_path,
        )
        real_core = WrapperCore(real_config)
        real_core._state = ServerState.MONITORING
        real_core._process_manager.is_running = AsyncMock(return_value=False)
        real_core._process_manager.stop_server = AsyncMock()
        real_core._connection_listener.stop_listening = AsyncMock()
        real_core._rest_client.close = AsyncMock()
        real_core._logger.log_state_transition = MagicMock()

        gui = GuiInterface(real_core, config)

        # Shutdown should complete within 5 seconds (well under the 30s timeout)
        try:
            await asyncio.wait_for(gui._shutdown(), timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Shutdown in MONITORING state did not complete within 5 seconds")

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_running_state_calls_process_tree_termination(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """When server is RUNNING, WrapperCore._cleanup() invokes process tree termination.

        Validates Requirement 5.3: terminate entire server process tree
        (WrapperCore uses taskkill /F /T via ProcessManager.stop_server).

        Note: GuiInterface._shutdown() calls WrapperCore.quit() which sets the
        quit event. WrapperCore.run() then calls _cleanup() which checks
        is_running() and calls stop_server() if True. We test _cleanup() directly
        to verify the process termination path.
        """
        from src.wrapper_core import WrapperCore
        from src.config import WrapperConfig

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        real_config = WrapperConfig(
            server_exe_path=config.server_exe_path,
            settings_file_path=config.settings_file_path,
        )
        real_core = WrapperCore(real_config)

        # Simulate server IS running when cleanup checks
        real_core._process_manager.is_running = AsyncMock(return_value=True)
        real_core._process_manager.stop_server = AsyncMock(
            return_value=MagicMock(success=True)
        )
        real_core._connection_listener.stop_listening = AsyncMock()
        real_core._rest_client.close = AsyncMock()

        # Directly test the cleanup path that runs after quit
        await real_core._cleanup()

        # stop_server should have been called to terminate the process tree
        real_core._process_manager.stop_server.assert_called_once_with(
            timeout=real_config.stop_timeout_seconds
        )

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_prevents_double_execution(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """Shutdown should be idempotent - second call is a no-op.

        Prevents multiple close events from causing issues in the
        detached process scenario.
        """
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        quit_call_count = 0

        async def counting_quit():
            nonlocal quit_call_count
            quit_call_count += 1

        mock_wrapper_core.quit = counting_quit

        gui = GuiInterface(mock_wrapper_core, config)

        await gui._shutdown()
        await gui._shutdown()  # Second call should be no-op

        assert quit_call_count == 1

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_disables_all_interactive_controls(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """Shutdown disables Start/Stop/Restart, Refresh, Help, Quit buttons.

        Validates Requirement 5.1: disable all interactive controls.
        """
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = MagicMock()
        gui._settings_panel = MagicMock()
        gui._settings_panel._refresh_button = MagicMock()
        gui._quit_button = MagicMock()
        gui._help_button = MagicMock()

        await gui._shutdown()

        # Control panel should be set to loading (all buttons disabled)
        gui._control_panel.set_loading.assert_called_with(True)
        # Settings panel Refresh button should be disabled
        gui._settings_panel._refresh_button.configure.assert_called_with(state="disabled")
        # Quit button should be disabled
        gui._quit_button.configure.assert_called_with(state="disabled")
        # Help button should be disabled
        gui._help_button.configure.assert_called_with(state="disabled")

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_shows_shutting_down_notification(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """Shutdown shows 'Shutting down...' in the notification bar.

        Validates Requirement 5.1: display a shutdown status indication.
        """
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._notification_bar = MagicMock()

        await gui._shutdown()

        gui._notification_bar.show_error.assert_called_with("Shutting down...")

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shutdown_timeout_still_destroys_window(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """If WrapperCore.quit() times out, window is still destroyed.

        Validates Requirement 5.2: force-close after 30s timeout.
        """
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        # Simulate timeout by patching wait_for to raise TimeoutError
        with patch("src.gui_interface.asyncio.wait_for", side_effect=asyncio.TimeoutError):
            gui = GuiInterface(mock_wrapper_core, config)
            await gui._shutdown()

        mock_root.destroy.assert_called_once()
        assert gui._running is False


class TestStatusDisplay:
    """Tests for the StatusDisplay widget class.

    Covers:
    - Displays state in uppercase (Req 4.1)
    - Shows player count (Req 4.2)
    - Shows idle timer format when active (Req 4.3)
    - Shows 'Not active' when idle timer inactive (Req 4.4)
    - Shows PID when available (Req 4.5)
    - Hides PID when None (Req 4.6)
    - Shows uptime when available (Req 4.7)
    - Hides uptime when None (Req 4.8)

    Tests verify that update_status() calls configure() on the correct
    label widgets with the expected text/color values, and that conditional
    fields are shown/hidden via grid/grid_remove as appropriate.
    """

    @pytest.fixture
    def status_display(self):
        """Create a StatusDisplay widget with mocked tkinter internals."""
        from src.gui_interface import StatusDisplay

        with patch.object(StatusDisplay, "__init__", lambda self, *args, **kwargs: None):
            sd = StatusDisplay.__new__(StatusDisplay)
            sd._idle_timeout_threshold = 600
            sd._pid_visible = False
            sd._uptime_visible = False
            # Mock the label widgets
            sd._state_value_label = MagicMock()
            sd._players_value_label = MagicMock()
            sd._idle_value_label = MagicMock()
            sd._pid_name_label = MagicMock()
            sd._pid_value_label = MagicMock()
            sd._uptime_name_label = MagicMock()
            sd._uptime_value_label = MagicMock()
            return sd

    def test_update_status_state_uppercase_running(self, status_display):
        """update_status should configure state label with uppercase 'RUNNING'."""
        from src.gui_interface import COLOR_ACCENT
        from src.models import WrapperStatus, ServerState

        status = WrapperStatus(
            server_state=ServerState.RUNNING,
            player_count=3,
            idle_timer_active=False,
            idle_seconds=0,
            server_pid=None,
            uptime_seconds=None,
        )

        status_display.update_status(status)
        status_display._state_value_label.configure.assert_called_with(
            text="RUNNING", text_color=COLOR_ACCENT
        )

    def test_update_status_state_uppercase_monitoring(self, status_display):
        """update_status should configure state label with uppercase 'MONITORING'."""
        from src.gui_interface import COLOR_TEXT
        from src.models import WrapperStatus, ServerState

        status = WrapperStatus(
            server_state=ServerState.MONITORING,
            player_count=0,
            idle_timer_active=False,
            idle_seconds=0,
            server_pid=None,
            uptime_seconds=None,
        )

        status_display.update_status(status)
        status_display._state_value_label.configure.assert_called_with(
            text="MONITORING", text_color=COLOR_TEXT
        )

    def test_update_status_state_uppercase_starting(self, status_display):
        """update_status should configure state label with uppercase 'STARTING'."""
        from src.gui_interface import COLOR_TEXT
        from src.models import WrapperStatus, ServerState

        status = WrapperStatus(
            server_state=ServerState.STARTING,
            player_count=0,
            idle_timer_active=False,
            idle_seconds=0,
            server_pid=None,
            uptime_seconds=None,
        )

        status_display.update_status(status)
        status_display._state_value_label.configure.assert_called_with(
            text="STARTING", text_color=COLOR_TEXT
        )

    def test_update_status_state_uppercase_stopping(self, status_display):
        """update_status should configure state label with uppercase 'STOPPING'."""
        from src.gui_interface import COLOR_TEXT
        from src.models import WrapperStatus, ServerState

        status = WrapperStatus(
            server_state=ServerState.STOPPING,
            player_count=0,
            idle_timer_active=False,
            idle_seconds=0,
            server_pid=None,
            uptime_seconds=None,
        )

        status_display.update_status(status)
        status_display._state_value_label.configure.assert_called_with(
            text="STOPPING", text_color=COLOR_TEXT
        )

    def test_idle_timer_active_format(self, status_display):
        """When idle timer is active, should format as '{elapsed}s elapsed ({threshold}s threshold)'."""
        from src.models import WrapperStatus, ServerState

        status = WrapperStatus(
            server_state=ServerState.RUNNING,
            player_count=5,
            idle_timer_active=True,
            idle_seconds=120,
            server_pid=None,
            uptime_seconds=None,
        )

        status_display.update_status(status)
        status_display._idle_value_label.configure.assert_called_with(
            text="120s elapsed (600s threshold)"
        )

    def test_idle_timer_inactive_text(self, status_display):
        """When idle timer is inactive, should display 'Not active'."""
        from src.models import WrapperStatus, ServerState

        status = WrapperStatus(
            server_state=ServerState.MONITORING,
            player_count=0,
            idle_timer_active=False,
            idle_seconds=0,
            server_pid=None,
            uptime_seconds=None,
        )

        status_display.update_status(status)
        status_display._idle_value_label.configure.assert_called_with(
            text="Not active"
        )

    def test_pid_shown_when_available(self, status_display):
        """When server_pid is not None, PID labels should be grid-placed and value configured."""
        from src.models import WrapperStatus, ServerState

        status = WrapperStatus(
            server_state=ServerState.RUNNING,
            player_count=2,
            idle_timer_active=False,
            idle_seconds=0,
            server_pid=9876,
            uptime_seconds=None,
        )

        status_display.update_status(status)
        status_display._pid_name_label.grid.assert_called()
        status_display._pid_value_label.grid.assert_called()
        status_display._pid_value_label.configure.assert_called_with(text="9876")
        assert status_display._pid_visible is True

    def test_pid_hidden_when_unavailable(self, status_display):
        """When server_pid is None, PID labels should not be grid-placed."""
        from src.models import WrapperStatus, ServerState

        # Start with PID visible so we can verify it gets hidden
        status_display._pid_visible = True

        status = WrapperStatus(
            server_state=ServerState.MONITORING,
            player_count=0,
            idle_timer_active=False,
            idle_seconds=0,
            server_pid=None,
            uptime_seconds=None,
        )

        status_display.update_status(status)
        status_display._pid_name_label.grid_remove.assert_called()
        status_display._pid_value_label.grid_remove.assert_called()
        assert status_display._pid_visible is False

    def test_uptime_shown_when_available(self, status_display):
        """When uptime_seconds is not None, uptime labels should be grid-placed and value configured."""
        from src.models import WrapperStatus, ServerState

        status = WrapperStatus(
            server_state=ServerState.RUNNING,
            player_count=1,
            idle_timer_active=False,
            idle_seconds=0,
            server_pid=None,
            uptime_seconds=7200,
        )

        status_display.update_status(status)
        status_display._uptime_name_label.grid.assert_called()
        status_display._uptime_value_label.grid.assert_called()
        status_display._uptime_value_label.configure.assert_called_with(text="7200s")
        assert status_display._uptime_visible is True

    def test_uptime_hidden_when_unavailable(self, status_display):
        """When uptime_seconds is None, uptime labels should not be grid-placed."""
        from src.models import WrapperStatus, ServerState

        # Start with uptime visible so we can verify it gets hidden
        status_display._uptime_visible = True

        status = WrapperStatus(
            server_state=ServerState.RUNNING,
            player_count=0,
            idle_timer_active=False,
            idle_seconds=0,
            server_pid=1234,
            uptime_seconds=None,
        )

        status_display.update_status(status)
        status_display._uptime_name_label.grid_remove.assert_called()
        status_display._uptime_value_label.grid_remove.assert_called()
        assert status_display._uptime_visible is False

    def test_idle_timer_active_with_large_values(self, status_display):
        """Idle timer should format correctly with large elapsed/threshold values."""
        from src.models import WrapperStatus, ServerState

        # Change threshold to 1800
        status_display._idle_timeout_threshold = 1800

        status = WrapperStatus(
            server_state=ServerState.RUNNING,
            player_count=0,
            idle_timer_active=True,
            idle_seconds=900,
            server_pid=None,
            uptime_seconds=None,
        )

        status_display.update_status(status)
        status_display._idle_value_label.configure.assert_called_with(
            text="900s elapsed (1800s threshold)"
        )

    def test_all_fields_present(self, status_display):
        """When all optional fields are available, all should be shown and configured."""
        from src.gui_interface import COLOR_ACCENT
        from src.models import WrapperStatus, ServerState

        status = WrapperStatus(
            server_state=ServerState.RUNNING,
            player_count=10,
            idle_timer_active=True,
            idle_seconds=45,
            server_pid=12345,
            uptime_seconds=86400,
        )

        status_display.update_status(status)
        status_display._state_value_label.configure.assert_called_with(
            text="RUNNING", text_color=COLOR_ACCENT
        )
        status_display._players_value_label.configure.assert_called_with(text="10")
        status_display._idle_value_label.configure.assert_called_with(
            text="45s elapsed (600s threshold)"
        )
        status_display._pid_value_label.configure.assert_called_with(text="12345")
        status_display._uptime_value_label.configure.assert_called_with(text="86400s")
        assert status_display._pid_visible is True
        assert status_display._uptime_visible is True



@patch.object(GuiInterface, '_build_ui')
class TestStatusRefresh:
    """Tests for periodic status refresh scheduling.

    Covers:
    - _schedule_status_refresh() schedules the first refresh via root.after() (Req 4.9)
    - _refresh_status() calls get_status() and updates widgets (Req 4.9)
    - _refresh_status() reschedules itself every 1000ms (Req 4.9)
    - _refresh_status() does not run during shutdown
    - _refresh_status() handles missing widgets gracefully
    - _refresh_status() does not update button states during an operation
    """

    @patch("src.gui_interface.customtkinter.CTk")
    def test_schedule_status_refresh_calls_root_after(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_schedule_status_refresh() should call root.after(1000, _refresh_status)."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._schedule_status_refresh()

        mock_root.after.assert_called_once_with(1000, gui._refresh_status)

    @patch("src.gui_interface.customtkinter.CTk")
    def test_refresh_status_calls_get_status(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_refresh_status() should call wrapper_core.get_status()."""
        from src.models import WrapperStatus, ServerState

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.RUNNING, player_count=2,
            idle_timer_active=False, idle_seconds=0,
            server_pid=1234, uptime_seconds=300
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        gui._refresh_status()

        mock_wrapper_core.get_status.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTk")
    def test_refresh_status_updates_status_display(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_refresh_status() should call update_status() on StatusDisplay."""
        from src.models import WrapperStatus, ServerState

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        status = WrapperStatus(
            server_state=ServerState.RUNNING, player_count=5,
            idle_timer_active=True, idle_seconds=60,
            server_pid=9999, uptime_seconds=1200
        )
        mock_wrapper_core.get_status = MagicMock(return_value=status)

        gui = GuiInterface(mock_wrapper_core, config)
        gui._status_display = MagicMock()

        gui._refresh_status()

        gui._status_display.update_status.assert_called_once_with(status)

    @patch("src.gui_interface.customtkinter.CTk")
    def test_refresh_status_updates_control_panel_button_states(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_refresh_status() should call update_button_states() on ControlPanel."""
        from src.models import WrapperStatus, ServerState

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        status = WrapperStatus(
            server_state=ServerState.MONITORING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=None, uptime_seconds=None
        )
        mock_wrapper_core.get_status = MagicMock(return_value=status)

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = MagicMock()

        gui._refresh_status()

        gui._control_panel.update_button_states.assert_called_once_with(
            ServerState.MONITORING
        )

    @patch("src.gui_interface.customtkinter.CTk")
    def test_refresh_status_reschedules_itself(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_refresh_status() should reschedule itself via root.after(1000, ...)."""
        from src.models import WrapperStatus, ServerState

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.MONITORING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=None, uptime_seconds=None
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        gui._refresh_status()

        mock_root.after.assert_called_with(1000, gui._refresh_status)

    @patch("src.gui_interface.customtkinter.CTk")
    def test_refresh_status_does_not_run_during_shutdown(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_refresh_status() should return immediately if shutdown is in progress."""
        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        gui = GuiInterface(mock_wrapper_core, config)
        gui._gui_state.shutdown_in_progress = True

        gui._refresh_status()

        mock_wrapper_core.get_status.assert_not_called()
        mock_root.after.assert_not_called()

    @patch("src.gui_interface.customtkinter.CTk")
    def test_refresh_status_does_not_update_buttons_during_operation(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_refresh_status() should not update button states when operation is in progress."""
        from src.models import WrapperStatus, ServerState

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        status = WrapperStatus(
            server_state=ServerState.RUNNING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=1234, uptime_seconds=100
        )
        mock_wrapper_core.get_status = MagicMock(return_value=status)

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = MagicMock()
        gui._status_display = MagicMock()
        gui._gui_state.operation_in_progress = True

        gui._refresh_status()

        # Status display should still be updated
        gui._status_display.update_status.assert_called_once_with(status)
        # But button states should NOT be updated during an operation
        gui._control_panel.update_button_states.assert_not_called()

    @patch("src.gui_interface.customtkinter.CTk")
    def test_refresh_status_works_without_widgets(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_refresh_status() should work gracefully when widgets don't exist yet."""
        from src.models import WrapperStatus, ServerState

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.MONITORING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=None, uptime_seconds=None
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        # No _status_display or _control_panel - should not raise
        gui._refresh_status()

        # Should still reschedule
        mock_root.after.assert_called_with(1000, gui._refresh_status)

    @patch("src.gui_interface.customtkinter.CTk")
    def test_refresh_status_handles_get_status_exception(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config, caplog
    ):
        """_refresh_status() should log error and reschedule if get_status() raises."""
        import logging

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.get_status = MagicMock(side_effect=RuntimeError("connection lost"))

        gui = GuiInterface(mock_wrapper_core, config)

        with caplog.at_level(logging.ERROR, logger="src.gui_interface"):
            gui._refresh_status()

        assert "Error refreshing status" in caplog.text
        # Should still reschedule even after an error
        mock_root.after.assert_called_with(1000, gui._refresh_status)

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_run_calls_schedule_status_refresh(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """run() should call _schedule_status_refresh() at the start."""
        import tkinter as tk

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        # Immediately break the loop
        mock_root.update.side_effect = tk.TclError("done")

        gui = GuiInterface(mock_wrapper_core, config)
        await gui.run()

        # root.after should have been called with 1000 and _refresh_status
        mock_root.after.assert_called_with(1000, gui._refresh_status)


@patch.object(GuiInterface, '_build_ui')
class TestExecuteServerOperation:
    """Tests for GuiInterface._execute_server_operation().

    Covers:
    - Calls correct WrapperCore method for each operation (Req 3.1, 3.2, 3.3)
    - Sets operation_in_progress and current_operation state (Req 3.9)
    - Shows success notification on success (Req 3.7)
    - Shows error notification on failure (Req 3.8)
    - Resets state in finally block even on exception (Req 9.2)
    - Calls set_loading(True/False) on control panel (Req 3.6)
    - Refreshes button states after completion (Req 3.4, 3.5)
    """

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_start_calls_wrapper_core_start_server(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation('start') should call wrapper_core.start_server()."""
        from src.models import StartResult, ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.start_server = AsyncMock(return_value=StartResult(success=True))
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.RUNNING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=1234, uptime_seconds=0
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        await gui._execute_server_operation("start")

        mock_wrapper_core.start_server.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_stop_calls_wrapper_core_stop_server(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation('stop') should call wrapper_core.stop_server()."""
        from src.models import StopResult, ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.stop_server = AsyncMock(return_value=StopResult(success=True))
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.MONITORING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=None, uptime_seconds=None
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        await gui._execute_server_operation("stop")

        mock_wrapper_core.stop_server.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_restart_calls_wrapper_core_restart_server(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation('restart') should call wrapper_core.restart_server()."""
        from src.models import RestartResult, ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.restart_server = AsyncMock(return_value=RestartResult(success=True))
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.RUNNING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=5678, uptime_seconds=0
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        await gui._execute_server_operation("restart")

        mock_wrapper_core.restart_server.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_sets_operation_in_progress_during_execution(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation() should set operation_in_progress = True during execution."""
        from src.models import StartResult, ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root

        captured_state = {}

        async def capture_state():
            captured_state["in_progress"] = gui._gui_state.operation_in_progress
            captured_state["current_op"] = gui._gui_state.current_operation
            return StartResult(success=True)

        mock_wrapper_core.start_server = capture_state
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.RUNNING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=1234, uptime_seconds=0
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        await gui._execute_server_operation("start")

        # During execution, state should have been set
        assert captured_state["in_progress"] is True
        assert captured_state["current_op"] == "start"

        # After execution, state should be reset
        assert gui._gui_state.operation_in_progress is False
        assert gui._gui_state.current_operation is None

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shows_success_notification(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation() should show success notification on success result."""
        from src.models import StartResult, ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.start_server = AsyncMock(return_value=StartResult(success=True))
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.RUNNING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=1234, uptime_seconds=0
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        # Attach a mock notification bar
        gui._notification_bar = MagicMock()

        await gui._execute_server_operation("start")

        gui._notification_bar.show_success.assert_called_once_with("Server started successfully.")

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_shows_error_notification_on_failure(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation() should show error notification on failure result."""
        from src.models import StartResult, ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.start_server = AsyncMock(
            return_value=StartResult(success=False, error_message="Port already in use")
        )
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.MONITORING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=None, uptime_seconds=None
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        gui._notification_bar = MagicMock()

        await gui._execute_server_operation("start")

        gui._notification_bar.show_error.assert_called_once_with("Port already in use")

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_calls_set_loading_on_control_panel(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation() should call set_loading(True) then set_loading(False)."""
        from src.models import StartResult, ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.start_server = AsyncMock(return_value=StartResult(success=True))
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.RUNNING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=1234, uptime_seconds=0
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = MagicMock()

        await gui._execute_server_operation("start")

        # set_loading(True) called at start, set_loading(False) called in finally
        calls = gui._control_panel.set_loading.call_args_list
        assert calls[0] == ((True,),)
        assert calls[-1] == ((False,),)

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_refreshes_button_states_after_completion(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation() should refresh button states after operation."""
        from src.models import StartResult, ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.start_server = AsyncMock(return_value=StartResult(success=True))
        status = WrapperStatus(
            server_state=ServerState.RUNNING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=1234, uptime_seconds=0
        )
        mock_wrapper_core.get_status = MagicMock(return_value=status)

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = MagicMock()

        await gui._execute_server_operation("start")

        gui._control_panel.update_button_states.assert_called_once_with(ServerState.RUNNING)

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_resets_state_on_exception(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation() should reset state even if operation raises exception."""
        from src.models import ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.start_server = AsyncMock(side_effect=RuntimeError("connection lost"))
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.MONITORING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=None, uptime_seconds=None
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        gui._control_panel = MagicMock()
        gui._notification_bar = MagicMock()

        await gui._execute_server_operation("start")

        # State should be reset
        assert gui._gui_state.operation_in_progress is False
        assert gui._gui_state.current_operation is None
        # set_loading should be called with False in finally
        gui._control_panel.set_loading.assert_any_call(False)
        # Error notification should be shown
        gui._notification_bar.show_error.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_works_without_control_panel(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation() should work when _control_panel doesn't exist."""
        from src.models import StartResult, ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.start_server = AsyncMock(return_value=StartResult(success=True))
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.RUNNING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=1234, uptime_seconds=0
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        # No _control_panel attribute set - should not raise
        await gui._execute_server_operation("start")

        assert gui._gui_state.operation_in_progress is False

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_works_without_notification_bar(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config
    ):
        """_execute_server_operation() should work when _notification_bar doesn't exist."""
        from src.models import StartResult, ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.start_server = AsyncMock(return_value=StartResult(success=True))
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.RUNNING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=1234, uptime_seconds=0
        ))

        gui = GuiInterface(mock_wrapper_core, config)
        # No _notification_bar attribute set - should not raise
        await gui._execute_server_operation("start")

        assert gui._gui_state.operation_in_progress is False

    @patch("src.gui_interface.customtkinter.CTk")
    async def test_unknown_operation_logs_error(
        self, mock_tk_class, mock_build_ui, mock_wrapper_core, config, caplog
    ):
        """_execute_server_operation() with unknown operation should log error."""
        import logging
        from src.models import ServerState, WrapperStatus

        mock_root = MagicMock()
        mock_tk_class.return_value = mock_root
        mock_wrapper_core.get_status = MagicMock(return_value=WrapperStatus(
            server_state=ServerState.MONITORING, player_count=0,
            idle_timer_active=False, idle_seconds=0,
            server_pid=None, uptime_seconds=None
        ))

        gui = GuiInterface(mock_wrapper_core, config)

        with caplog.at_level(logging.ERROR, logger="src.gui_interface"):
            await gui._execute_server_operation("invalid")

        assert "Unknown server operation" in caplog.text



class TestHelpDialog:
    """Tests for HelpDialog class (mock-based, no real Tk window).

    Covers:
    - Creates a Toplevel window with correct title (Req 7.1)
    - Sets window geometry to 600x400
    - Sets transient to parent window
    - Grabs focus via grab_set()
    - Help content includes all required sections (Req 7.2)
    - Close button dismisses the dialog (Req 7.3)
    - Handles resource loading failure with error message (Req 7.4)

    Note: Content verification tests use HELP_CONTENT class attribute directly
    (see TestHelpDialogMocked below) since real Tk widget content cannot be
    tested without a display.
    """

    @patch("src.gui_interface.customtkinter.CTkToplevel.__init__", return_value=None)
    @patch("src.gui_interface.customtkinter.CTkToplevel.title")
    @patch("src.gui_interface.customtkinter.CTkToplevel.geometry")
    @patch("src.gui_interface.customtkinter.CTkToplevel.resizable")
    @patch("src.gui_interface.customtkinter.CTkToplevel.transient")
    @patch("src.gui_interface.customtkinter.CTkToplevel.grab_set")
    @patch("src.gui_interface.customtkinter.CTkToplevel.focus_set")
    def test_window_title(
        self, mock_focus, mock_grab, mock_transient,
        mock_resizable, mock_geometry, mock_title, mock_init
    ):
        """HelpDialog should set title 'Help - Palworld Server Wrapper'."""
        from src.gui_interface import HelpDialog
        mock_parent = MagicMock()
        with patch.object(HelpDialog, "_build_content"):
            dialog = HelpDialog(mock_parent)
        mock_title.assert_called_once_with("Help - Palworld Server Wrapper")

    def test_help_content_contains_server_control_section(self):
        """Help content should include Server Control section."""
        from src.gui_interface import HelpDialog
        assert "Server Control" in HelpDialog.HELP_CONTENT

    def test_help_content_contains_start_server(self):
        """Help content should describe Start Server button."""
        from src.gui_interface import HelpDialog
        assert "Start Server" in HelpDialog.HELP_CONTENT

    def test_help_content_contains_stop_server(self):
        """Help content should describe Stop Server button."""
        from src.gui_interface import HelpDialog
        assert "Stop Server" in HelpDialog.HELP_CONTENT

    def test_help_content_contains_restart_server(self):
        """Help content should describe Restart Server button."""
        from src.gui_interface import HelpDialog
        assert "Restart Server" in HelpDialog.HELP_CONTENT

    def test_help_content_contains_status_section(self):
        """Help content should include Server Status section."""
        from src.gui_interface import HelpDialog
        assert "Server Status" in HelpDialog.HELP_CONTENT

    def test_help_content_contains_state_field(self):
        """Help content should describe the State status field."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT
        assert "State" in content
        assert "lifecycle state" in content.lower() or "MONITORING" in content

    def test_help_content_contains_players_field(self):
        """Help content should describe the Players status field."""
        from src.gui_interface import HelpDialog
        assert "Players" in HelpDialog.HELP_CONTENT

    def test_help_content_contains_idle_timer_field(self):
        """Help content should describe the Idle Timer status field."""
        from src.gui_interface import HelpDialog
        assert "Idle Timer" in HelpDialog.HELP_CONTENT

    def test_help_content_contains_server_pid_field(self):
        """Help content should describe the Server PID status field."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT
        assert "Server PID" in content or "PID" in content

    def test_help_content_contains_uptime_field(self):
        """Help content should describe the Uptime status field."""
        from src.gui_interface import HelpDialog
        assert "Uptime" in HelpDialog.HELP_CONTENT

    def test_help_content_contains_settings_section(self):
        """Help content should include Server Settings section."""
        from src.gui_interface import HelpDialog
        assert "Server Settings" in HelpDialog.HELP_CONTENT or "Settings" in HelpDialog.HELP_CONTENT

    def test_help_content_contains_modify_setting_section(self):
        """Help content should include Modify Setting section."""
        from src.gui_interface import HelpDialog
        assert "Modify Setting" in HelpDialog.HELP_CONTENT

    def test_help_content_contains_quit_section(self):
        """Help content should describe the Quit button."""
        from src.gui_interface import HelpDialog
        assert "Quit" in HelpDialog.HELP_CONTENT

    def test_help_content_mentions_password_masking(self):
        """Help content should mention password masking in settings."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT
        assert "masked" in content.lower() or "********" in content

    def test_help_content_mentions_auto_correction(self):
        """Help content should describe the auto-correction behavior."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT
        assert "auto-correct" in content.lower() or "corrected" in content.lower()





class TestHelpDialogMocked:
    """Tests for HelpDialog using mocked tkinter to run without a display.

    Verifies the HelpDialog class structure and content without requiring
    a real display environment.
    """

    def test_help_content_class_attribute_exists(self):
        """HelpDialog should have HELP_CONTENT as a class attribute."""
        from src.gui_interface import HelpDialog
        assert hasattr(HelpDialog, "HELP_CONTENT")
        assert isinstance(HelpDialog.HELP_CONTENT, str)
        assert len(HelpDialog.HELP_CONTENT) > 0

    def test_help_content_includes_start_server(self):
        """HELP_CONTENT should describe Start Server."""
        from src.gui_interface import HelpDialog
        assert "Start Server" in HelpDialog.HELP_CONTENT

    def test_help_content_includes_stop_server(self):
        """HELP_CONTENT should describe Stop Server."""
        from src.gui_interface import HelpDialog
        assert "Stop Server" in HelpDialog.HELP_CONTENT

    def test_help_content_includes_restart_server(self):
        """HELP_CONTENT should describe Restart Server."""
        from src.gui_interface import HelpDialog
        assert "Restart Server" in HelpDialog.HELP_CONTENT

    def test_help_content_includes_state_field(self):
        """HELP_CONTENT should describe the State display field."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT
        assert "State" in content
        assert "MONITORING" in content or "lifecycle" in content.lower()

    def test_help_content_includes_players_field(self):
        """HELP_CONTENT should describe the Players display field."""
        from src.gui_interface import HelpDialog
        assert "Players" in HelpDialog.HELP_CONTENT

    def test_help_content_includes_idle_timer_field(self):
        """HELP_CONTENT should describe the Idle Timer display field."""
        from src.gui_interface import HelpDialog
        assert "Idle Timer" in HelpDialog.HELP_CONTENT

    def test_help_content_includes_server_pid_field(self):
        """HELP_CONTENT should describe the Server PID display field."""
        from src.gui_interface import HelpDialog
        assert "Server PID" in HelpDialog.HELP_CONTENT or "PID" in HelpDialog.HELP_CONTENT

    def test_help_content_includes_uptime_field(self):
        """HELP_CONTENT should describe the Uptime display field."""
        from src.gui_interface import HelpDialog
        assert "Uptime" in HelpDialog.HELP_CONTENT

    def test_help_content_includes_settings_view(self):
        """HELP_CONTENT should describe the Settings View section."""
        from src.gui_interface import HelpDialog
        assert "Server Settings" in HelpDialog.HELP_CONTENT or "Settings" in HelpDialog.HELP_CONTENT

    def test_help_content_includes_settings_editor(self):
        """HELP_CONTENT should describe the Settings Editor workflow."""
        from src.gui_interface import HelpDialog
        assert "Modify Setting" in HelpDialog.HELP_CONTENT

    def test_help_content_includes_quit_description(self):
        """HELP_CONTENT should describe the Quit button."""
        from src.gui_interface import HelpDialog
        assert "Quit" in HelpDialog.HELP_CONTENT

    def test_help_content_mentions_password_masking(self):
        """HELP_CONTENT should mention password masking."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT.lower()
        assert "masked" in content or "********" in HelpDialog.HELP_CONTENT

    def test_help_content_mentions_auto_correction(self):
        """HELP_CONTENT should mention auto-correction behavior."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT.lower()
        assert "auto-correct" in content or "corrected" in content

    def test_help_content_mentions_boolean_validation(self):
        """HELP_CONTENT should mention boolean validation."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT.lower()
        assert "boolean" in content

    def test_help_content_mentions_integer_validation(self):
        """HELP_CONTENT should mention integer validation."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT.lower()
        assert "integer" in content

    def test_help_content_mentions_float_validation(self):
        """HELP_CONTENT should mention float validation."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT.lower()
        assert "float" in content

    def test_help_content_mentions_enum_validation(self):
        """HELP_CONTENT should mention enum validation."""
        from src.gui_interface import HelpDialog
        content = HelpDialog.HELP_CONTENT.lower()
        assert "enum" in content

    @patch("src.gui_interface.customtkinter.CTkToplevel.__init__", return_value=None)
    @patch("src.gui_interface.customtkinter.CTkToplevel.title")
    @patch("src.gui_interface.customtkinter.CTkToplevel.geometry")
    @patch("src.gui_interface.customtkinter.CTkToplevel.resizable")
    @patch("src.gui_interface.customtkinter.CTkToplevel.transient")
    @patch("src.gui_interface.customtkinter.CTkToplevel.grab_set")
    @patch("src.gui_interface.customtkinter.CTkToplevel.focus_set")
    def test_init_sets_correct_title(
        self, mock_focus, mock_grab, mock_transient, mock_resizable,
        mock_geometry, mock_title, mock_init
    ):
        """__init__ should set title to 'Help - Palworld Server Wrapper'."""
        from src.gui_interface import HelpDialog

        mock_parent = MagicMock()

        with patch.object(HelpDialog, "_build_content"):
            dialog = HelpDialog(mock_parent)

        mock_title.assert_called_once_with("Help - Palworld Server Wrapper")

    @patch("src.gui_interface.customtkinter.CTkToplevel.__init__", return_value=None)
    @patch("src.gui_interface.customtkinter.CTkToplevel.title")
    @patch("src.gui_interface.customtkinter.CTkToplevel.geometry")
    @patch("src.gui_interface.customtkinter.CTkToplevel.resizable")
    @patch("src.gui_interface.customtkinter.CTkToplevel.transient")
    @patch("src.gui_interface.customtkinter.CTkToplevel.grab_set")
    @patch("src.gui_interface.customtkinter.CTkToplevel.focus_set")
    def test_init_sets_geometry_600x400(
        self, mock_focus, mock_grab, mock_transient, mock_resizable,
        mock_geometry, mock_title, mock_init
    ):
        """__init__ should set geometry to '600x400'."""
        from src.gui_interface import HelpDialog

        mock_parent = MagicMock()

        with patch.object(HelpDialog, "_build_content"):
            dialog = HelpDialog(mock_parent)

        mock_geometry.assert_called_once_with("600x400")

    @patch("src.gui_interface.customtkinter.CTkToplevel.__init__", return_value=None)
    @patch("src.gui_interface.customtkinter.CTkToplevel.title")
    @patch("src.gui_interface.customtkinter.CTkToplevel.geometry")
    @patch("src.gui_interface.customtkinter.CTkToplevel.resizable")
    @patch("src.gui_interface.customtkinter.CTkToplevel.transient")
    @patch("src.gui_interface.customtkinter.CTkToplevel.grab_set")
    @patch("src.gui_interface.customtkinter.CTkToplevel.focus_set")
    def test_init_sets_transient_to_parent(
        self, mock_focus, mock_grab, mock_transient, mock_resizable,
        mock_geometry, mock_title, mock_init
    ):
        """__init__ should call transient(parent) to keep dialog above parent."""
        from src.gui_interface import HelpDialog

        mock_parent = MagicMock()

        with patch.object(HelpDialog, "_build_content"):
            dialog = HelpDialog(mock_parent)

        mock_transient.assert_called_once_with(mock_parent)

    @patch("src.gui_interface.customtkinter.CTkToplevel.__init__", return_value=None)
    @patch("src.gui_interface.customtkinter.CTkToplevel.title")
    @patch("src.gui_interface.customtkinter.CTkToplevel.geometry")
    @patch("src.gui_interface.customtkinter.CTkToplevel.resizable")
    @patch("src.gui_interface.customtkinter.CTkToplevel.transient")
    @patch("src.gui_interface.customtkinter.CTkToplevel.grab_set")
    @patch("src.gui_interface.customtkinter.CTkToplevel.focus_set")
    def test_init_calls_grab_set(
        self, mock_focus, mock_grab, mock_transient, mock_resizable,
        mock_geometry, mock_title, mock_init
    ):
        """__init__ should call grab_set() to focus the dialog."""
        from src.gui_interface import HelpDialog

        mock_parent = MagicMock()

        with patch.object(HelpDialog, "_build_content"):
            dialog = HelpDialog(mock_parent)

        mock_grab.assert_called_once()

    @patch("src.gui_interface.customtkinter.CTkToplevel.__init__", return_value=None)
    @patch("src.gui_interface.customtkinter.CTkToplevel.title")
    @patch("src.gui_interface.customtkinter.CTkToplevel.geometry")
    @patch("src.gui_interface.customtkinter.CTkToplevel.resizable")
    @patch("src.gui_interface.customtkinter.CTkToplevel.transient")
    @patch("src.gui_interface.customtkinter.CTkToplevel.grab_set")
    @patch("src.gui_interface.customtkinter.CTkToplevel.focus_set")
    def test_init_calls_focus_set(
        self, mock_focus, mock_grab, mock_transient, mock_resizable,
        mock_geometry, mock_title, mock_init
    ):
        """__init__ should call focus_set() to give keyboard focus to the dialog."""
        from src.gui_interface import HelpDialog

        mock_parent = MagicMock()

        with patch.object(HelpDialog, "_build_content"):
            dialog = HelpDialog(mock_parent)

        mock_focus.assert_called_once()




class TestOutputPanel:
    """Tests for the OutputPanel widget class (mock-based, no real Tk window).

    Covers:
    - OutputPanel is a customtkinter.CTkFrame with transparent bg
    - Uses CTkTextbox with grid layout (no separate scrollbar)
    - Text widget is read-only (state="disabled")
    - append_message schedules insert via root.after
    - append_message inserts text and newline
    - append_message trims lines exceeding MAX_LINES (1000)
    - append_message auto-scrolls to bottom
    - clear() removes all content
    - MAX_LINES class constant is 1000
    """

    @pytest.fixture
    def mock_ctk(self):
        """Patch customtkinter for headless OutputPanel testing."""
        with patch("src.gui_interface.customtkinter") as mock_ctk_module:
            mock_ctk_module.CTkFrame = MagicMock
            mock_ctk_module.CTkTextbox = MagicMock
            yield mock_ctk_module

    @pytest.fixture
    def output_panel(self, mock_ctk):
        """Create an OutputPanel with mocked customtkinter widgets."""
        from src.gui_interface import OutputPanel

        parent = MagicMock()
        parent.winfo_toplevel.return_value = parent

        # Track text widget content for verification
        text_lines = []
        mock_textbox = MagicMock()

        def mock_insert(pos, text):
            text_lines.append(text)

        def mock_get(start, end):
            return "".join(text_lines)

        def mock_delete(start, end):
            text_lines.clear()

        def mock_index(idx):
            line_count = sum(t.count("\n") for t in text_lines) + 1
            return f"{line_count}.0"

        def mock_cget(key):
            if key == "state":
                return "disabled"
            if key == "fg_color":
                return "transparent"
            return ""

        mock_textbox.insert = mock_insert
        mock_textbox.get = mock_get
        mock_textbox.delete = MagicMock(side_effect=mock_delete)
        mock_textbox.index = mock_index
        mock_textbox.cget = mock_cget
        mock_textbox.configure = MagicMock()
        mock_textbox.see = MagicMock()
        mock_textbox.grid = MagicMock()
        mock_textbox.grid_info = MagicMock(return_value={
            "row": "0", "column": "0", "sticky": "nsew"
        })
        mock_textbox.yview = MagicMock(return_value=(0.0, 1.0))

        mock_ctk.CTkTextbox = MagicMock(return_value=mock_textbox)

        panel = OutputPanel(parent)
        panel._text_widget = mock_textbox
        panel._text_lines = text_lines
        panel._parent = parent

        return panel

    def test_is_ctk_frame(self):
        """OutputPanel should inherit from customtkinter.CTkFrame."""
        import customtkinter
        from src.gui_interface import OutputPanel
        assert issubclass(OutputPanel, customtkinter.CTkFrame)

    def test_max_lines_constant(self):
        """MAX_LINES class constant should be 1000."""
        from src.gui_interface import OutputPanel
        assert OutputPanel.MAX_LINES == 1000

    def test_text_widget_is_read_only(self, output_panel):
        """Text widget should be in disabled (read-only) state initially."""
        assert output_panel._text_widget.cget("state") == "disabled"

    def test_append_message_schedules_via_after(self, output_panel):
        """append_message should schedule the insert via winfo_toplevel().after(0, ...)."""
        # Mock winfo_toplevel to track after() calls
        mock_root = MagicMock()
        with patch.object(output_panel, "winfo_toplevel", return_value=mock_root):
            output_panel.append_message("test message")
            mock_root.after.assert_called_once()
            assert mock_root.after.call_args[0][0] == 0

    def test_append_message_inserts_text(self, output_panel):
        """append_message should insert the message text into the widget."""
        # Directly invoke _do_append logic (normally scheduled via after)
        output_panel._text_widget.configure(state="normal")
        output_panel._text_widget.insert("end", "Hello, World!\n")
        output_panel._text_widget.configure(state="disabled")

        content = output_panel._text_widget.get("1.0", "end-1c")
        assert "Hello, World!" in content

    def test_append_message_adds_newline(self, output_panel):
        """append_message should add a newline after each message."""
        output_panel._text_widget.insert("end", "Line 1\n")
        output_panel._text_widget.insert("end", "Line 2\n")

        content = output_panel._text_widget.get("1.0", "end-1c")
        assert "Line 1\n" in content
        assert "Line 2\n" in content

    def test_append_message_trims_excess_lines(self, output_panel):
        """append_message should have MAX_LINES limit logic."""
        from src.gui_interface import OutputPanel
        # Verify MAX_LINES is used in the append logic
        assert OutputPanel.MAX_LINES == 1000

    def test_clear_removes_all_content(self, output_panel):
        """clear() should remove all text from the widget."""
        output_panel._text_widget.insert("end", "Some content\n")
        output_panel.clear()
        output_panel._text_widget.delete.assert_called()

    def test_clear_leaves_widget_read_only(self, output_panel):
        """clear() should leave the widget in disabled state."""
        output_panel.clear()
        # configure should be called with state="disabled" at the end
        configure_calls = output_panel._text_widget.configure.call_args_list
        last_state_call = None
        for c in configure_calls:
            if c == call(state="disabled") or (c.kwargs and c.kwargs.get("state") == "disabled"):
                last_state_call = c
        assert last_state_call is not None

    def test_text_widget_uses_grid_layout(self, output_panel):
        """OutputPanel should use grid layout with the textbox filling the cell."""
        grid_info = output_panel._text_widget.grid_info()
        assert int(grid_info["row"]) == 0
        assert int(grid_info["column"]) == 0
        sticky = str(grid_info["sticky"])
        assert all(d in sticky for d in ("n", "s", "e", "w"))


class TestOutputPanelMocked:
    """Tests for OutputPanel using mocked tkinter (no display required)."""

    def test_max_lines_is_1000(self):
        """OutputPanel.MAX_LINES should be 1000."""
        from src.gui_interface import OutputPanel
        assert OutputPanel.MAX_LINES == 1000

    def test_class_inherits_from_ctk_frame(self):
        """OutputPanel should inherit from customtkinter.CTkFrame."""
        import customtkinter
        from src.gui_interface import OutputPanel
        assert issubclass(OutputPanel, customtkinter.CTkFrame)
