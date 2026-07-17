"""GUI Management Interface for the Palworld Server Wrapper.

Provides a CustomTkinter-based graphical interface for interacting with the
wrapper. Integrates with asyncio via cooperative scheduling (periodic
root.update() calls from an asyncio coroutine), ensuring neither the GUI
event loop nor the asyncio event loop is blocked for more than ~33ms.

This module mirrors the role of ManagementInterface but with a graphical
window instead of a CLI prompt.
"""

import asyncio
import logging
import sys
import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass, field

import customtkinter

from src.config import WrapperConfig
from src.gui_theme import (
    BUTTON_CORNER_RADIUS,
    CARD_INNER_PADDING,
    CARD_OUTER_MARGIN,
    COLOR_ACCENT,
    COLOR_ALERT,
    COLOR_BASE_BG,
    COLOR_DISABLED,
    COLOR_INPUT_BG,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    FONT_BODY,
    FONT_HEADING,
    FONT_MONO,
    FONT_SUBHEADING,
    WIDGET_INNER_SPACING,
    create_card_frame,
)
from src.models import ServerState, WrapperStatus
from src.pending_settings import ApplyResult
from src.settings_panel import SettingsPanel
from src.settings_write_handler import SettingsWriteHandler
from src.wrapper_core import WrapperCore

logger = logging.getLogger(__name__)


@dataclass
class NotificationState:
    """Tracks the current notification display state."""

    message: str = ""
    is_error: bool = False
    dismiss_after_id: str | None = None  # tkinter after() callback ID


@dataclass
class GuiState:
    """Internal GUI state tracking for operation management."""

    operation_in_progress: bool = False
    shutdown_in_progress: bool = False
    current_operation: str | None = None  # "start", "stop", "restart"


class GuiInterface:
    """CustomTkinter-based GUI management interface for the Palworld Server Wrapper.

    Integrates with asyncio via cooperative scheduling (periodic root.update()
    calls from an asyncio coroutine). The run() method is an async coroutine
    that runs concurrently with WrapperCore.run() via asyncio.gather().
    """

    def __init__(self, wrapper_core: WrapperCore, config: WrapperConfig) -> None:
        """Initialize the GUI interface.

        Creates the customtkinter CTk root window with appearance mode "dark",
        color theme "blue", title "Palworld Server Wrapper", and minimum size
        800x600. Wires WM_DELETE_WINDOW to _shutdown().

        Args:
            wrapper_core: The WrapperCore instance for command execution.
            config: The wrapper configuration.

        Raises:
            SystemExit: If customtkinter cannot initialize (no display environment).
        """
        self._wrapper_core = wrapper_core
        self._config = config
        self._settings_write_handler = SettingsWriteHandler(
            wrapper_core=wrapper_core,
            pending_queue=wrapper_core.pending_queue,
            settings_file_path=config.settings_file_path,
        )
        wrapper_core.register_apply_callback(self._on_apply_result)
        self._running = False
        self._gui_state = GuiState()
        self._notification_state = NotificationState()

        try:
            customtkinter.set_appearance_mode("dark")
            customtkinter.set_default_color_theme("blue")
            self._root = customtkinter.CTk()
            self._root.title("Palworld Server Wrapper")
            self._root.minsize(800, 600)
            self._root.protocol("WM_DELETE_WINDOW", self._on_close_request)
        except Exception as e:
            logger.error("Failed to initialize GUI: %s", e)
            sys.exit(1)

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the complete GUI layout using grid geometry manager.

        Instantiates and arranges all GUI components in a vertical grid layout
        with Card_Frame containers for visual grouping per Requirements 2.1-2.6
        and 4.4-4.5.

        Grid layout (top to bottom):
        - Row 0: ControlPanel Card_Frame (weight=0, fixed)
        - Row 1: StatusDisplay Card_Frame (weight=0, fixed)
        - Row 2: OutputPanel Card_Frame (weight=1, expand)
        - Row 3: SettingsPanel Card_Frame (weight=1, expand)
        - Row 4: Button frame - Help and Quit (weight=0, fixed)
        - Row 5: NotificationBar Card_Frame (weight=0, fixed)

        All widget instances are stored as self._ attributes so
        _disable_all_controls() and other methods can access them.
        """
        # Configure root grid weights
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=0)  # ControlPanel
        self._root.rowconfigure(1, weight=0)  # StatusDisplay
        self._root.rowconfigure(2, weight=1)  # OutputPanel (expand)
        self._root.rowconfigure(3, weight=1)  # SettingsPanel (expand)
        self._root.rowconfigure(4, weight=0)  # Button frame
        self._root.rowconfigure(5, weight=0)  # NotificationBar

        # Row 0: Control Panel - Server lifecycle buttons
        cp_card = create_card_frame(self._root)
        cp_card.grid(row=0, column=0, sticky="nsew", padx=CARD_OUTER_MARGIN, pady=(CARD_OUTER_MARGIN, CARD_OUTER_MARGIN // 2))
        cp_card.columnconfigure(0, weight=1)
        customtkinter.CTkLabel(
            cp_card, text="Server Controls", font=FONT_HEADING, text_color=COLOR_TEXT, anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=CARD_INNER_PADDING, pady=(CARD_INNER_PADDING, 0))
        self._control_panel = ControlPanel(
            cp_card,
            on_start=lambda: asyncio.create_task(
                self._execute_server_operation("start")
            ),
            on_stop=lambda: asyncio.create_task(
                self._execute_server_operation("stop")
            ),
            on_restart=lambda: asyncio.create_task(
                self._execute_server_operation("restart")
            ),
        )
        self._control_panel.grid(row=1, column=0, sticky="nsew", padx=CARD_INNER_PADDING, pady=CARD_INNER_PADDING)

        # Row 1: Status Display - Real-time status fields
        sd_card = create_card_frame(self._root)
        sd_card.grid(row=1, column=0, sticky="nsew", padx=CARD_OUTER_MARGIN, pady=CARD_OUTER_MARGIN // 2)
        sd_card.columnconfigure(0, weight=1)
        customtkinter.CTkLabel(
            sd_card, text="Server Status", font=FONT_HEADING, text_color=COLOR_TEXT, anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=CARD_INNER_PADDING, pady=(CARD_INNER_PADDING, 0))
        self._status_display = StatusDisplay(
            sd_card,
            idle_timeout_threshold=self._config.idle_timeout_seconds,
        )
        self._status_display.grid(row=1, column=0, sticky="nsew", padx=CARD_INNER_PADDING, pady=CARD_INNER_PADDING)

        # Row 2: Output Panel - Operational log output
        op_card = create_card_frame(self._root)
        op_card.grid(row=2, column=0, sticky="nsew", padx=CARD_OUTER_MARGIN, pady=CARD_OUTER_MARGIN // 2)
        op_card.columnconfigure(0, weight=1)
        op_card.rowconfigure(1, weight=1)
        customtkinter.CTkLabel(
            op_card, text="Output Log", font=FONT_HEADING, text_color=COLOR_TEXT, anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=CARD_INNER_PADDING, pady=(CARD_INNER_PADDING, 0))
        self._output_panel = OutputPanel(op_card)
        self._output_panel.grid(row=1, column=0, sticky="nsew", padx=CARD_INNER_PADDING, pady=CARD_INNER_PADDING)

        # NotificationBar created early (SettingsPanel needs it), placed at row 5 later
        nb_card = create_card_frame(self._root)
        nb_card.grid(row=5, column=0, sticky="nsew", padx=CARD_OUTER_MARGIN, pady=(CARD_OUTER_MARGIN // 2, CARD_OUTER_MARGIN))
        nb_card.columnconfigure(0, weight=1)
        self._notification_bar = NotificationBar(nb_card)
        self._notification_bar.grid(row=0, column=0, sticky="nsew", padx=CARD_INNER_PADDING, pady=CARD_INNER_PADDING)

        # Row 3: SettingsPanel - Unified settings display and modification
        sp_card = create_card_frame(self._root)
        sp_card.grid(row=3, column=0, sticky="nsew", padx=CARD_OUTER_MARGIN, pady=CARD_OUTER_MARGIN // 2)
        sp_card.columnconfigure(0, weight=1)
        sp_card.rowconfigure(1, weight=1)
        customtkinter.CTkLabel(
            sp_card, text="Server Settings", font=FONT_HEADING, text_color=COLOR_TEXT, anchor="w"
        ).grid(row=0, column=0, sticky="ew", padx=CARD_INNER_PADDING, pady=(CARD_INNER_PADDING, 0))
        self._settings_panel = SettingsPanel(
            parent=sp_card,
            config=self._config,
            wrapper_core=self._wrapper_core,
            settings_write_handler=self._settings_write_handler,
            notification_bar=self._notification_bar,
        )
        self._settings_panel.grid(row=1, column=0, sticky="nsew", padx=CARD_INNER_PADDING, pady=CARD_INNER_PADDING)

        # Row 4: Button frame - Help and Quit buttons
        button_frame = customtkinter.CTkFrame(self._root, fg_color="transparent")
        button_frame.grid(row=4, column=0, sticky="ew", padx=CARD_OUTER_MARGIN, pady=CARD_OUTER_MARGIN // 2)

        self._help_button = customtkinter.CTkButton(
            button_frame,
            text="Help",
            fg_color=COLOR_PRIMARY,
            corner_radius=BUTTON_CORNER_RADIUS,
            command=lambda: HelpDialog(self._root),
        )
        self._help_button.grid(row=0, column=0, padx=(0, WIDGET_INNER_SPACING))

        self._quit_button = customtkinter.CTkButton(
            button_frame,
            text="Quit",
            fg_color=COLOR_PRIMARY,
            corner_radius=BUTTON_CORNER_RADIUS,
            command=self._on_close_request,
        )
        self._quit_button.grid(row=0, column=1)

    def _schedule_status_refresh(self) -> None:
        """Schedule periodic status display updates (every 1 second).

        Initiates the first call to _refresh_status(), which then reschedules
        itself every 1000ms via root.after(). This satisfies the requirement
        that status refreshes between 500ms and 2 seconds.
        """
        self._root.after(1000, self._refresh_status)

    def get_log_callback(self) -> Callable[[str], None]:
        """Return the callback function for routing log messages to the GUI.

        This provides the OutputPanel's append_message method for use as
        the gui_callback in WrapperLogger.add_gui_handler().

        Returns:
            The OutputPanel.append_message method.
        """
        return self._output_panel.append_message

    def _refresh_status(self) -> None:
        """Refresh the status display and control panel button states.

        Calls WrapperCore.get_status() and updates the StatusDisplay and
        ControlPanel widgets if they exist. Reschedules itself every 1 second
        unless a shutdown is in progress.
        """
        if self._gui_state.shutdown_in_progress:
            return

        try:
            status = self._wrapper_core.get_status()

            # Update StatusDisplay if it exists
            if hasattr(self, "_status_display") and self._status_display is not None:
                self._status_display.update_status(status)

            # Update ControlPanel button states if it exists and no operation in progress
            if (
                hasattr(self, "_control_panel")
                and self._control_panel is not None
                and not self._gui_state.operation_in_progress
            ):
                self._control_panel.update_button_states(status.server_state)

            # Update pending indicator in settings panel
            if hasattr(self, "_settings_panel") and self._settings_panel is not None:
                self._settings_panel.update_pending_indicator()

        except Exception as e:
            logger.error("Error refreshing status: %s", e)

        # Reschedule the next refresh (only if not shutting down)
        if not self._gui_state.shutdown_in_progress:
            self._root.after(1000, self._refresh_status)

    async def run(self) -> None:
        """Main entry point - runs the tkinter event loop cooperatively with asyncio.

        Calls root.update() every ~33ms (30 FPS equivalent) to process tkinter
        events without blocking the asyncio event loop. This allows WrapperCore's
        background tasks (REST API polling, idle timer, maintenance timer, connection
        listener) to continue executing on schedule.

        The loop continues until self._running is set to False (via _shutdown())
        or the window is destroyed externally.
        """
        self._running = True
        self._schedule_status_refresh()

        while self._running:
            try:
                self._root.update()
            except tk.TclError:
                # Window has been destroyed (e.g., user closed it or shutdown completed)
                break

            await asyncio.sleep(0.033)

    def _on_close_request(self) -> None:
        """Handle the WM_DELETE_WINDOW event (user clicks window close button).

        Schedules the async _shutdown() method as a task on the running event loop.
        """
        asyncio.create_task(self._shutdown())

    def _on_apply_result(self, result: ApplyResult) -> None:
        """Handle notification when pending settings are applied."""
        if result.failed_key is not None:
            error_msg = result.error_message or "Unknown error"
            msg = f"Failed to apply pending settings: {error_msg}. {result.remaining_count} change(s) remain queued."
            if hasattr(self, "_notification_bar") and self._notification_bar is not None:
                self._notification_bar.show_error(msg)
        elif result.applied_count > 0:
            msg = f"{result.applied_count} pending setting(s) applied."
            if hasattr(self, "_notification_bar") and self._notification_bar is not None:
                self._notification_bar.show_success(msg)
        if hasattr(self, "_settings_panel") and self._settings_panel is not None:
            self._settings_panel.update_pending_indicator()

    async def _execute_server_operation(self, operation: str) -> None:
        """Execute a server control operation in a non-blocking manner.

        Sets operation_in_progress state, shows loading indicator on control panel,
        calls the corresponding WrapperCore method, and handles the result by
        showing success/error notifications and refreshing button states.

        Uses try/finally to ensure cleanup (resetting operation state and refreshing
        buttons) happens even if an unexpected exception occurs.

        Args:
            operation: One of "start", "stop", "restart".
        """
        self._gui_state.operation_in_progress = True
        self._gui_state.current_operation = operation

        if hasattr(self, "_control_panel") and self._control_panel is not None:
            self._control_panel.set_loading(True)

        try:
            # Call the corresponding WrapperCore method
            if operation == "start":
                result = await self._wrapper_core.start_server()
            elif operation == "stop":
                result = await self._wrapper_core.stop_server()
            elif operation == "restart":
                result = await self._wrapper_core.restart_server()
            else:
                logger.error("Unknown server operation: %s", operation)
                return

            # Show success or error notification based on result
            if result.success:
                success_messages = {
                    "start": "Server started successfully.",
                    "stop": "Server stopped successfully.",
                    "restart": "Server restarted successfully.",
                }
                message = success_messages.get(operation, f"Operation '{operation}' completed.")
                if hasattr(self, "_notification_bar") and self._notification_bar is not None:
                    self._notification_bar.show_success(message)
            else:
                error_message = result.error_message or f"Operation '{operation}' failed."
                if hasattr(self, "_notification_bar") and self._notification_bar is not None:
                    self._notification_bar.show_error(error_message)

        except Exception as e:
            logger.error("Unexpected error during %s operation: %s", operation, e)
            if hasattr(self, "_notification_bar") and self._notification_bar is not None:
                self._notification_bar.show_error(f"Unexpected error: {e}")

        finally:
            # Reset operation state
            self._gui_state.operation_in_progress = False
            self._gui_state.current_operation = None

            # Refresh button states based on current server state
            if hasattr(self, "_control_panel") and self._control_panel is not None:
                self._control_panel.set_loading(False)
                current_status = self._wrapper_core.get_status()
                self._control_panel.update_button_states(current_status.server_state)

    async def _shutdown(self) -> None:
        """Perform graceful shutdown sequence.

        1. Disables all interactive controls.
        2. Shows "Shutting down..." status in the notification bar.
        3. Invokes WrapperCore.quit() with a 30-second timeout.
        4. Destroys the tkinter window.
        5. Sets _running = False to exit the cooperative loop.

        If quit() does not complete within 30 seconds, force-closes the window
        and logs a warning. If quit() raises an exception, logs the error and
        closes the window anyway.
        """
        if self._gui_state.shutdown_in_progress:
            return

        self._gui_state.shutdown_in_progress = True

        # Disable all controls
        self._disable_all_controls()

        # Show "Shutting down..." status in the notification bar
        self._show_shutdown_status()

        try:
            await asyncio.wait_for(self._wrapper_core.quit(), timeout=30.0)
        except asyncio.TimeoutError:
            logger.warning(
                "Shutdown timed out after 30 seconds, force-closing window"
            )
        except Exception as e:
            logger.error("Error during shutdown: %s", e)

        # Destroy the tkinter window and stop the loop
        try:
            self._root.destroy()
        except tk.TclError:
            pass  # Window already destroyed

        self._running = False

    def _show_shutdown_status(self) -> None:
        """Display 'Shutting down...' status in the notification bar.

        If the notification bar exists, shows an error-style (persistent)
        notification with the shutdown message. This provides visual feedback
        that the application is in the process of shutting down.
        """
        if hasattr(self, "_notification_bar") and self._notification_bar is not None:
            self._notification_bar.show_error("Shutting down...")

    def _disable_all_controls(self) -> None:
        """Disable all interactive controls during shutdown.

        Iterates through known widget attributes and disables them.
        Uses hasattr() checks since widgets may not exist yet.

        Disables:
        - ControlPanel buttons (Start, Stop, Restart)
        - SettingsPanel Refresh button
        - Quit button
        - Help button
        """
        # Disable control panel buttons
        if hasattr(self, "_control_panel") and self._control_panel is not None:
            try:
                self._control_panel.set_loading(True)
            except tk.TclError:
                pass

        # Disable settings panel Refresh button
        if hasattr(self, "_settings_panel") and self._settings_panel is not None:
            try:
                if hasattr(self._settings_panel, "_refresh_button"):
                    self._settings_panel._refresh_button.configure(state="disabled")
            except tk.TclError:
                pass

        # Disable Quit button
        if hasattr(self, "_quit_button") and self._quit_button is not None:
            try:
                self._quit_button.configure(state="disabled")
            except tk.TclError:
                pass

        # Disable Help button
        if hasattr(self, "_help_button") and self._help_button is not None:
            try:
                self._help_button.configure(state="disabled")
            except tk.TclError:
                pass


class ControlPanel(customtkinter.CTkFrame):
    """Server control buttons with state-aware enable/disable logic.

    Provides "Start Server", "Stop Server", and "Restart Server" buttons
    arranged in a horizontal row using grid layout. Button states update
    automatically based on the current ServerState:

    - MONITORING: Start=enabled, Restart=enabled, Stop=disabled
    - RUNNING: Start=disabled, Stop=enabled, Restart=enabled
    - STARTING/STOPPING: All disabled, loading indicator shown
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_restart: Callable[[], None],
    ) -> None:
        """Initialize the ControlPanel.

        Args:
            parent: The parent widget.
            on_start: Callback invoked when the "Start Server" button is clicked.
            on_stop: Callback invoked when the "Stop Server" button is clicked.
            on_restart: Callback invoked when the "Restart Server" button is clicked.
        """
        super().__init__(parent)

        self._on_start = on_start
        self._on_stop = on_stop
        self._on_restart = on_restart

        # Configure grid columns with equal weight for uniform button sizing
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)

        # Create server control buttons in row 0
        self._start_button = customtkinter.CTkButton(
            self,
            text="Start Server",
            command=self._on_start,
            fg_color=COLOR_PRIMARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._start_button.grid(
            row=0, column=0, padx=WIDGET_INNER_SPACING, pady=WIDGET_INNER_SPACING, sticky="ew"
        )

        self._stop_button = customtkinter.CTkButton(
            self,
            text="Stop Server",
            command=self._on_stop,
            fg_color=COLOR_PRIMARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._stop_button.grid(
            row=0, column=1, padx=WIDGET_INNER_SPACING, pady=WIDGET_INNER_SPACING, sticky="ew"
        )

        self._restart_button = customtkinter.CTkButton(
            self,
            text="Restart Server",
            command=self._on_restart,
            fg_color=COLOR_PRIMARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._restart_button.grid(
            row=0, column=2, padx=WIDGET_INNER_SPACING, pady=WIDGET_INNER_SPACING, sticky="ew"
        )

        # Loading indicator label in row 1 spanning all columns (hidden by default)
        self._loading_label = customtkinter.CTkLabel(
            self,
            text="Operation in progress...",
            text_color=COLOR_TEXT_SECONDARY,
            font=FONT_BODY,
        )
        # Do not grid yet — shown only when set_loading(True) is called

        # Initialize with MONITORING state (default)
        self.update_button_states(ServerState.MONITORING)

    def update_button_states(self, state: ServerState) -> None:
        """Enable/disable buttons based on current server state.

        Args:
            state: The current ServerState value.

        Button enable/disable logic:
            MONITORING: Start=enabled, Stop=disabled, Restart=enabled
            RUNNING:    Start=disabled, Stop=enabled, Restart=enabled
            STARTING/STOPPING: All disabled, loading indicator shown
        """
        if state == ServerState.MONITORING:
            self._start_button.configure(state="normal", fg_color=COLOR_PRIMARY)
            self._stop_button.configure(state="disabled", fg_color=COLOR_DISABLED)
            self._restart_button.configure(state="normal", fg_color=COLOR_PRIMARY)
            self._hide_loading()
        elif state == ServerState.RUNNING:
            self._start_button.configure(state="disabled", fg_color=COLOR_DISABLED)
            self._stop_button.configure(state="normal", fg_color=COLOR_PRIMARY)
            self._restart_button.configure(state="normal", fg_color=COLOR_PRIMARY)
            self._hide_loading()
        elif state in (ServerState.STARTING, ServerState.STOPPING):
            self._start_button.configure(state="disabled", fg_color=COLOR_DISABLED)
            self._stop_button.configure(state="disabled", fg_color=COLOR_DISABLED)
            self._restart_button.configure(state="disabled", fg_color=COLOR_DISABLED)
            self._show_loading()

    def set_loading(self, loading: bool) -> None:
        """Show/hide loading indicator and disable all buttons during operations.

        Args:
            loading: If True, disables all buttons and shows the loading indicator.
                    If False, hides the loading indicator (button states should be
                    updated separately via update_button_states()).
        """
        if loading:
            self._start_button.configure(state="disabled", fg_color=COLOR_DISABLED)
            self._stop_button.configure(state="disabled", fg_color=COLOR_DISABLED)
            self._restart_button.configure(state="disabled", fg_color=COLOR_DISABLED)
            self._show_loading()
        else:
            self._hide_loading()

    def _show_loading(self) -> None:
        """Show the loading indicator label in row 1 spanning all columns."""
        self._loading_label.grid(
            row=1, column=0, columnspan=3, padx=WIDGET_INNER_SPACING, pady=(0, WIDGET_INNER_SPACING), sticky="ew"
        )

    def _hide_loading(self) -> None:
        """Hide the loading indicator label."""
        self._loading_label.grid_remove()


class OutputPanel(customtkinter.CTkFrame):
    """Scrollable text area displaying operational log output.

    Provides a read-only CTkTextbox widget that receives log messages via
    append_message(). Auto-scrolls to the latest entry. Maintains
    a maximum of 1000 lines to prevent unbounded memory growth.

    Thread-safe: append_message() schedules the actual insert via
    root.after() so it can be called from any thread (e.g., logging handler).
    """

    MAX_LINES = 1000

    def __init__(self, parent: tk.Widget) -> None:
        """Initialize the OutputPanel.

        Args:
            parent: The parent tkinter widget.
        """
        super().__init__(parent, fg_color="transparent")

        # Grid layout - textbox fills the entire frame
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # CTkTextbox replaces tk.Text + ttk.Scrollbar (CTkTextbox has built-in scrollbar)
        self._text_widget = customtkinter.CTkTextbox(
            self,
            state="disabled",
            font=FONT_MONO,
            fg_color=COLOR_INPUT_BG,
            text_color=COLOR_TEXT,
            wrap="word",
        )
        self._text_widget.grid(row=0, column=0, sticky="nsew")

    def append_message(self, message: str) -> None:
        """Append a log message to the output panel.

        Thread-safe via root.after() scheduling. Trims oldest lines
        if MAX_LINES is exceeded. Auto-scrolls to bottom.

        Args:
            message: The formatted log message string.
        """
        def _do_append() -> None:
            self._text_widget.configure(state="normal")
            self._text_widget.insert("end", message + "\n")

            # Trim lines exceeding MAX_LINES
            line_count = int(self._text_widget.index("end-1c").split(".")[0])
            if line_count > self.MAX_LINES:
                excess = line_count - self.MAX_LINES
                self._text_widget.delete("1.0", f"{excess + 1}.0")

            self._text_widget.configure(state="disabled")
            self._text_widget.see("end")

        self.winfo_toplevel().after(0, _do_append)

    def clear(self) -> None:
        """Clear all content from the output panel."""
        self._text_widget.configure(state="normal")
        self._text_widget.delete("1.0", "end")
        self._text_widget.configure(state="disabled")


class NotificationBar(customtkinter.CTkFrame):
    """Status notification bar at the bottom of the main window.

    Success messages auto-dismiss after 5 seconds.
    Error messages persist until user dismisses them.

    The bar is hidden when there is no active notification (uses grid_remove()).
    Tracks the current after() callback ID so it can be cancelled if a new
    notification replaces an old one.
    """

    def __init__(self, parent: tk.Widget) -> None:
        """Initialize the NotificationBar.

        Args:
            parent: The parent tkinter widget (typically the root window or
                    a container frame). When shown/hidden, the parent card
                    frame is also toggled to avoid an empty visible container.
        """
        super().__init__(parent, fg_color="transparent")

        self._after_id: str | None = None
        self._is_visible: bool = False
        self._parent_card = parent

        # Configure grid columns: message expands, dismiss button fixed
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)

        # Message label - takes up most of the horizontal space
        self._message_label = customtkinter.CTkLabel(
            self, text="", anchor="w", text_color=COLOR_TEXT, font=FONT_BODY
        )
        self._message_label.grid(row=0, column=0, sticky="ew")

        # Dismiss button [×]
        self._dismiss_button = customtkinter.CTkButton(
            self, text="\u00d7", width=30, fg_color="transparent",
            command=self.dismiss
        )
        self._dismiss_button.grid(row=0, column=1)

        # Start hidden since there's no notification to show
        self.grid_remove()
        self._parent_card.grid_remove()

    def show_success(self, message: str) -> None:
        """Display a success notification that auto-dismisses after 5 seconds.

        If a previous notification is visible, it is replaced. Any pending
        auto-dismiss callback is cancelled before scheduling a new one.

        Args:
            message: The success message to display.
        """
        self._cancel_pending_dismiss()
        self._message_label.configure(text=message, text_color=COLOR_SUCCESS)
        self._show()

        # Schedule auto-dismiss after 5 seconds (5000 ms)
        self._after_id = self.winfo_toplevel().after(5000, self.dismiss)

    def show_error(self, message: str) -> None:
        """Display an error notification that persists until user dismisses.

        If a previous notification is visible, it is replaced. Any pending
        auto-dismiss callback is cancelled (errors do not auto-dismiss).

        Args:
            message: The error message to display.
        """
        self._cancel_pending_dismiss()
        self._message_label.configure(text=message, text_color=COLOR_ALERT)
        self._show()

    def dismiss(self) -> None:
        """Dismiss the current notification and hide the bar.

        Cancels any pending auto-dismiss callback. Safe to call even when
        no notification is visible.
        """
        self._cancel_pending_dismiss()
        self._hide()

    def _show(self) -> None:
        """Make the notification bar visible."""
        if not self._is_visible:
            self._parent_card.grid()
            self.grid()
            self._is_visible = True

    def _hide(self) -> None:
        """Hide the notification bar."""
        if self._is_visible:
            self.grid_remove()
            self._parent_card.grid_remove()
            self._is_visible = False

    def _cancel_pending_dismiss(self) -> None:
        """Cancel any pending auto-dismiss after() callback."""
        if self._after_id is not None:
            self.winfo_toplevel().after_cancel(self._after_id)
            self._after_id = None



class StatusDisplay(customtkinter.CTkFrame):
    """Real-time server status display using CTkFrame with grid layout.

    Displays: State (uppercase), Player Count, Idle Timer status,
    Server PID (only when available), and Uptime (only when available).

    Fields are arranged in a two-column grid (labels in column 0, values in
    column 1). Always-visible fields (State, Players, Idle Timer) are created
    once and updated in-place via configure() to avoid flicker. Conditional
    fields (PID, Uptime) are shown/hidden as needed.
    """

    def __init__(self, parent: tk.Widget, idle_timeout_threshold: int) -> None:
        """Initialize the StatusDisplay.

        Args:
            parent: The parent tkinter widget.
            idle_timeout_threshold: The configured idle timeout threshold in seconds,
                used to display the idle timer format "{elapsed}s elapsed ({threshold}s threshold)".
        """
        super().__init__(parent, fg_color="transparent")

        self._idle_timeout_threshold = idle_timeout_threshold

        # Configure grid columns: labels fixed, values expand
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)

        # Track whether conditional fields are currently visible
        self._pid_visible = False
        self._uptime_visible = False

        # --- Always-visible fields (created once, updated in-place) ---

        # Row 0: State
        self._state_name_label = customtkinter.CTkLabel(
            self, text="State:", font=FONT_SUBHEADING, text_color=COLOR_TEXT
        )
        self._state_name_label.grid(
            row=0, column=0, sticky="w", pady=(0, WIDGET_INNER_SPACING), padx=(0, WIDGET_INNER_SPACING)
        )
        self._state_value_label = customtkinter.CTkLabel(
            self, text="MONITORING", font=FONT_BODY, text_color=COLOR_TEXT
        )
        self._state_value_label.grid(
            row=0, column=1, sticky="w", pady=(0, WIDGET_INNER_SPACING)
        )

        # Row 1: Players
        self._players_name_label = customtkinter.CTkLabel(
            self, text="Players:", font=FONT_SUBHEADING, text_color=COLOR_TEXT
        )
        self._players_name_label.grid(
            row=1, column=0, sticky="w", pady=(0, WIDGET_INNER_SPACING), padx=(0, WIDGET_INNER_SPACING)
        )
        self._players_value_label = customtkinter.CTkLabel(
            self, text="0", font=FONT_BODY, text_color=COLOR_TEXT
        )
        self._players_value_label.grid(
            row=1, column=1, sticky="w", pady=(0, WIDGET_INNER_SPACING)
        )

        # Row 2: Idle Timer
        self._idle_name_label = customtkinter.CTkLabel(
            self, text="Idle Timer:", font=FONT_SUBHEADING, text_color=COLOR_TEXT
        )
        self._idle_name_label.grid(
            row=2, column=0, sticky="w", pady=(0, WIDGET_INNER_SPACING), padx=(0, WIDGET_INNER_SPACING)
        )
        self._idle_value_label = customtkinter.CTkLabel(
            self, text="Not active", font=FONT_BODY, text_color=COLOR_TEXT
        )
        self._idle_value_label.grid(
            row=2, column=1, sticky="w", pady=(0, WIDGET_INNER_SPACING)
        )

        # --- Conditional fields (created once, shown/hidden via grid) ---

        # Row 3: Server PID
        self._pid_name_label = customtkinter.CTkLabel(
            self, text="Server PID:", font=FONT_SUBHEADING, text_color=COLOR_TEXT
        )
        self._pid_value_label = customtkinter.CTkLabel(
            self, text="", font=FONT_BODY, text_color=COLOR_TEXT
        )

        # Row 4: Uptime
        self._uptime_name_label = customtkinter.CTkLabel(
            self, text="Uptime:", font=FONT_SUBHEADING, text_color=COLOR_TEXT
        )
        self._uptime_value_label = customtkinter.CTkLabel(
            self, text="", font=FONT_BODY, text_color=COLOR_TEXT
        )

    def update_status(self, status: WrapperStatus) -> None:
        """Update all status fields from a WrapperStatus snapshot.

        Updates always-visible labels in-place via configure() to avoid flicker.
        Shows or hides conditional PID/Uptime fields only when their visibility
        state changes.

        Args:
            status: The current WrapperStatus snapshot from WrapperCore.
        """
        # --- Update always-visible fields in-place ---

        # State
        state_text = status.server_state.name.upper()
        state_value_color = COLOR_ACCENT if state_text == "RUNNING" else COLOR_TEXT
        self._state_value_label.configure(text=state_text, text_color=state_value_color)

        # Players
        self._players_value_label.configure(text=str(status.player_count))

        # Idle Timer
        if status.idle_timer_active:
            idle_timer_text = (
                f"{status.idle_seconds}s elapsed "
                f"({self._idle_timeout_threshold}s threshold)"
            )
        else:
            idle_timer_text = "Not active"
        self._idle_value_label.configure(text=idle_timer_text)

        # --- Update conditional fields (show/hide only on visibility change) ---

        # Server PID
        pid_should_show = status.server_pid is not None
        if pid_should_show != self._pid_visible:
            if pid_should_show:
                self._pid_name_label.grid(
                    row=3, column=0, sticky="w", pady=(0, WIDGET_INNER_SPACING), padx=(0, WIDGET_INNER_SPACING)
                )
                self._pid_value_label.grid(
                    row=3, column=1, sticky="w", pady=(0, WIDGET_INNER_SPACING)
                )
            else:
                self._pid_name_label.grid_remove()
                self._pid_value_label.grid_remove()
            self._pid_visible = pid_should_show

        if pid_should_show:
            self._pid_value_label.configure(text=str(status.server_pid))

        # Uptime
        uptime_should_show = status.uptime_seconds is not None
        if uptime_should_show != self._uptime_visible:
            if uptime_should_show:
                self._uptime_name_label.grid(
                    row=4, column=0, sticky="w", pady=(0, WIDGET_INNER_SPACING), padx=(0, WIDGET_INNER_SPACING)
                )
                self._uptime_value_label.grid(
                    row=4, column=1, sticky="w", pady=(0, WIDGET_INNER_SPACING)
                )
            else:
                self._uptime_name_label.grid_remove()
                self._uptime_value_label.grid_remove()
            self._uptime_visible = uptime_should_show

        if uptime_should_show:
            self._uptime_value_label.configure(text=f"{status.uptime_seconds}s")



class HelpDialog(customtkinter.CTkToplevel):
    """Modal help dialog with feature documentation.

    Displays a scrollable read-only text area containing descriptions of all
    GUI features: server control buttons, status display fields, settings view,
    settings editor workflow, and the quit button.

    The dialog is non-blocking (uses transient() and grab_set() for focus but
    does not call wait_window()), allowing the user to dismiss it and return
    to the main interface without affecting server state.

    Window title: "Help - Palworld Server Wrapper"
    Size: 600x400 pixels
    """

    HELP_CONTENT = """\
=== Server Control ===

Start Server
  Starts the Palworld dedicated server process. The server will transition \
from MONITORING state to STARTING, then to RUNNING once fully initialized.

Stop Server
  Gracefully stops the running server. The server will transition from \
RUNNING to STOPPING, then back to MONITORING once fully shut down.

Restart Server
  Stops the server (if running) and starts it again. This is equivalent to \
performing a Stop followed by a Start.

=== Server Status ===

State
  Displays the current server lifecycle state (MONITORING, STARTING, \
RUNNING, or STOPPING).

Players
  Shows the number of players currently connected to the server.

Idle Timer
  When active, shows how long the server has been idle (no players connected) \
and the configured threshold before automatic shutdown. Displays "Not active" \
when players are connected or the timer is disabled.

Server PID
  The process ID of the running server. Only displayed while the server is running.

Uptime
  How long the server has been running in seconds. Only displayed while the \
server is active.

=== Server Settings ===

Displays all settings read from PalWorldSettings.ini sorted alphabetically \
in "Key = Value" format. Password values are masked with "********" for security.

Click "Refresh" to reload settings from the configuration file.

=== Modify Setting ===

Enter a setting key name and a new value to modify server configuration.

The system validates and auto-corrects values based on the setting type:
  - Booleans are normalized to True/False
  - Integers are checked against min/max ranges
  - Floats are checked against min/max ranges
  - Enums are validated against allowed values

If auto-correction is applied, both the original and corrected values are shown.
If validation fails, an error message is displayed and no changes are written.

If the server is currently running, a warning is shown indicating that a \
restart is required for changes to take effect.

Unknown setting keys are written as raw strings without type validation.

=== Quit ===

Gracefully shuts down the wrapper, stopping the server if running, and \
closes the application window. The shutdown process has a 30-second timeout \
to ensure the application does not hang indefinitely.
"""

    def __init__(self, parent: tk.Widget) -> None:
        """Initialize the HelpDialog.

        Creates a CTkToplevel window with scrollable help text content and a
        Close button. The dialog is set as transient to the parent and
        grabs focus via grab_set().

        Args:
            parent: The parent tkinter widget (typically the root window).
        """
        super().__init__(parent)

        self.configure(fg_color=COLOR_BASE_BG)
        self.title("Help - Palworld Server Wrapper")
        self.geometry("600x400")
        self.resizable(True, True)

        # Set as transient to parent (keeps dialog above parent window)
        self.transient(parent)

        self._build_content()

        # Grab focus so the dialog is the active window
        self.grab_set()
        self.focus_set()

    def _build_content(self) -> None:
        """Build the scrollable help text content and Close button.

        Creates a CTkTextbox with built-in scrollbar for the help content,
        and a Close button at the bottom to dismiss the dialog.

        If help content cannot be loaded (resource failure), displays an
        error message instead.
        """
        # Configure grid layout for the toplevel
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        # CTkTextbox with built-in scrollbar for help content
        self._text_widget = customtkinter.CTkTextbox(
            self,
            wrap="word",
            font=FONT_BODY,
            text_color=COLOR_TEXT,
            fg_color=COLOR_INPUT_BG,
        )
        self._text_widget.grid(
            row=0, column=0, sticky="nsew", padx=10, pady=(10, 5)
        )

        # Insert help content
        try:
            self._text_widget.insert("1.0", self.HELP_CONTENT)
        except Exception:
            self._text_widget.insert(
                "1.0", "Error: Help content is unavailable."
            )

        # Make the text widget read-only
        self._text_widget.configure(state="disabled")

        # Close button at the bottom
        close_button = customtkinter.CTkButton(
            self,
            text="Close",
            command=self.destroy,
            fg_color=COLOR_PRIMARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        close_button.grid(row=1, column=0, sticky="e", padx=10, pady=(5, 10))
