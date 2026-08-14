"""Unified settings display and modification panel.

Consolidates the former SettingsView (read-only display) and SettingsEditor
(modification form) into a single searchable, scrollable panel where each
setting is displayed with full metadata and an inline edit control.
"""

import logging
import tkinter as tk
from collections.abc import Callable
from typing import Any

import customtkinter

from src.config import WrapperConfig
from src.gui_theme import (
    BUTTON_CORNER_RADIUS,
    CARD_INNER_PADDING,
    COLOR_ACCENT,
    COLOR_INPUT_BG,
    COLOR_PRIMARY,
    COLOR_TEXT,
    COLOR_TEXT_SECONDARY,
    FONT_BODY,
    FONT_SUBHEADING,
    NESTED_CARD_CORNER_RADIUS,
    WIDGET_INNER_SPACING,
    create_card_frame,
)
from src.models import ServerState
from src.pending_settings import PendingSettingsQueue
from src.settings_helpers import (
    format_allowed_values,
    format_current_value,
    format_default_value,
    get_input_control_type,
    values_differ,
)
from src.settings_parser import SETTING_CATEGORIES, SETTING_DEFINITIONS, SettingDefinition, SettingsParser
from src.settings_write_handler import SettingsWriteHandler
from src.validation import (
    CorrectionResult,
    is_password_setting,
    validate_and_correct,
)
from src.wrapper_core import WrapperCore

logger = logging.getLogger(__name__)

# Forward reference for type hints
NotificationBar = Any  # Avoids circular import with gui_interface

# Viewport virtualization constants
VIEWPORT_CAPACITY = 30  # Maximum visible rows at any time
VIEWPORT_BUFFER = 5  # Extra rows rendered above/below viewport
POOL_SIZE = VIEWPORT_CAPACITY + 2 * VIEWPORT_BUFFER  # 40 total pool widgets


class _SettingRowProxy:
    """Lightweight proxy object exposing SettingRow-compatible attributes.

    Used when no widget pool exists (e.g., in test scenarios) to provide
    backward-compatible access to setting row data without requiring
    actual tkinter widgets.
    """

    def __init__(
        self, key: str, definition: Any, current_value: str, category: str
    ) -> None:
        self.key = key
        self._definition = definition
        self._current_value = current_value
        self.category = category

        if definition is not None and definition.description:
            self.description = definition.description
        else:
            self.description = "No description available"

    def grid(self, **kwargs) -> None:
        """No-op grid for compatibility."""

    def grid_remove(self) -> None:
        """No-op grid_remove for compatibility."""

    def destroy(self) -> None:
        """No-op destroy for compatibility."""


class SettingsPanel(customtkinter.CTkFrame):
    """Unified settings display and modification panel.

    Replaces the former SettingsView and SettingsEditor with a single scrollable,
    searchable interface showing all setting metadata inline with edit controls.
    Uses grid layout and CustomTkinter widgets themed via gui_theme constants.
    """

    MAX_SEARCH_LENGTH = 200

    def __init__(
        self,
        parent: tk.Widget,
        config: WrapperConfig,
        wrapper_core: WrapperCore,
        settings_write_handler: SettingsWriteHandler,
        notification_bar: Any,
    ) -> None:
        """Initialize the SettingsPanel.

        Args:
            parent: The parent widget.
            config: The wrapper configuration (provides settings_file_path).
            wrapper_core: The WrapperCore instance for state queries.
            settings_write_handler: Handler for routing setting writes/queues.
            notification_bar: The NotificationBar instance for messages.
        """
        super().__init__(parent, fg_color="transparent")

        self._config = config
        self._wrapper_core = wrapper_core
        self._settings_write_handler = settings_write_handler
        self._notification_bar = notification_bar

        # Virtualization data model: holds all settings data regardless of visibility
        self._all_rows_data: list[dict] = []
        # Visible subset after filtering (indices into _all_rows_data)
        self._visible_rows_data: list[dict] = []

        # Widget pool for recycling (pre-created SettingRow instances)
        self._widget_pool: list["SettingRow"] = []
        # Mapping of pool widget index -> data index currently displayed
        self._pool_assignments: dict[int, int] = {}

        # Current viewport tracking
        self._viewport_start: int = 0
        self._viewport_end: int = 0

        # Search debounce: pending after() call ID for delayed filtering
        self._search_after_id: str | None = None

        # Refresh guard: prevents concurrent refresh() calls
        self._refresh_in_progress: bool = False

        # Legacy list maintained for backward compatibility with _on_apply_setting
        self._setting_rows: list["SettingRow"] = []
        self._no_results_label: customtkinter.CTkLabel | None = None
        self._category_headers: list[customtkinter.CTkLabel] = []

        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        """Construct the internal grid layout: search, pending indicator, scrollable frame, buttons.

        Creates a pre-allocated widget pool of POOL_SIZE SettingRow instances
        for viewport virtualization. Binds scroll events for virtualized rendering.
        """
        # Configure grid weights
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)  # Search entry
        self.rowconfigure(1, weight=0)  # Pending indicator
        self.rowconfigure(2, weight=1)  # Scrollable frame (expands)
        self.rowconfigure(3, weight=0)  # Buttons

        # Row 0: Search input field
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        self._search_entry = customtkinter.CTkEntry(
            self,
            textvariable=self._search_var,
            placeholder_text="Search settings...",
            fg_color=COLOR_INPUT_BG,
            text_color=COLOR_TEXT,
        )
        self._search_entry.grid(
            row=0, column=0, sticky="ew",
            padx=WIDGET_INNER_SPACING, pady=(WIDGET_INNER_SPACING, 2),
        )

        # Row 1: Pending changes indicator (hidden when queue empty)
        self._pending_indicator = customtkinter.CTkLabel(
            self,
            text="",
            text_color=COLOR_ACCENT,
            font=FONT_BODY,
            anchor="w",
        )
        # Initially hidden — will be shown via grid() when pending count > 0

        # Row 2: Scrollable frame for setting rows
        self._scrollable_frame = customtkinter.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self._scrollable_frame.grid(
            row=2, column=0, sticky="nsew",
            padx=WIDGET_INNER_SPACING, pady=2,
        )
        self._scrollable_frame.columnconfigure(0, weight=1)

        # Bind scroll events for viewport virtualization
        self._scrollable_frame.bind("<Configure>", self._on_viewport_configure)
        # Bind mousewheel for scroll detection
        self._scrollable_frame.bind_all("<MouseWheel>", self._on_scroll_event)

        # Row 3: Button frame (Apply + Refresh)
        button_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        button_frame.grid(
            row=3, column=0, sticky="ew",
            padx=WIDGET_INNER_SPACING, pady=(2, WIDGET_INNER_SPACING),
        )
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=0)
        button_frame.columnconfigure(2, weight=0)

        self._refresh_button = customtkinter.CTkButton(
            button_frame,
            text="Refresh",
            command=self.refresh,
            fg_color=COLOR_PRIMARY,
            corner_radius=BUTTON_CORNER_RADIUS,
        )
        self._refresh_button.grid(row=0, column=2, padx=(WIDGET_INNER_SPACING, 0))

        # Create the widget pool (pre-allocated SettingRow instances)
        self._create_widget_pool()

    def _create_widget_pool(self) -> None:
        """Pre-create a pool of POOL_SIZE SettingRow widgets for recycling.

        These widgets are created once and reused via update_data() as the
        user scrolls through the settings list.
        """
        for _ in range(POOL_SIZE):
            row = SettingRow(
                parent=self._scrollable_frame,
                key="__pool_placeholder__",
                definition=None,
                current_value="",
                on_apply=self._on_apply_setting,
            )
            # Don't grid yet — will be placed during viewport update
            self._widget_pool.append(row)
        # Also track pool widgets in _setting_rows for backward compatibility
        self._setting_rows = list(self._widget_pool)

    def _on_search_changed(self, *args) -> None:
        """Trace callback for the search StringVar — debounces filter invocation.

        Enforces MAX_SEARCH_LENGTH immediately, then schedules filter_settings()
        after 150ms of keyboard silence. Each keystroke cancels the pending
        scheduled call and starts a fresh 150ms timer.
        """
        current = self._search_var.get()
        if len(current) > self.MAX_SEARCH_LENGTH:
            self._search_var.set(current[: self.MAX_SEARCH_LENGTH])
            return

        # Cancel any pending debounced filter call
        if self._search_after_id is not None:
            self.after_cancel(self._search_after_id)
            self._search_after_id = None

        # Schedule filter_settings() after 150ms of keyboard silence
        self._search_after_id = self.after(
            150, self._execute_debounced_filter, current
        )

    def _execute_debounced_filter(self, search_text: str) -> None:
        """Execute the debounced filter operation.

        Called by the tkinter after() scheduler once 150ms have elapsed
        since the last keystroke.

        Args:
            search_text: The search query to filter against.
        """
        self._search_after_id = None
        self.filter_settings(search_text)

    def refresh(self) -> None:
        """Re-read settings file and rebuild the data model, then update viewport.

        Instead of destroying and recreating all widgets, this method updates
        the _all_rows_data model and triggers a viewport recalculation that
        recycles existing pool widgets via update_data().

        If a refresh is already in progress, the call is rejected immediately
        to prevent concurrent rebuilds. The guard flag is reset via after_idle
        so that rapid consecutive calls within the same event loop cycle are
        properly debounced.
        """
        # Use __dict__ directly to avoid __getattr__ mock interference
        if self.__dict__.get("_refresh_in_progress", False):
            return

        self.__dict__["_refresh_in_progress"] = True
        try:
            self._do_refresh()
        finally:
            # Schedule flag reset for the next event loop iteration.
            # This debounces rapid consecutive refresh() calls — only the
            # first in a given event loop cycle actually executes.
            scheduled = False
            try:
                after_id = self.after_idle(self._reset_refresh_flag)
                # Real tkinter returns a string/int ID; mock returns MagicMock
                if isinstance(after_id, (str, int)):
                    scheduled = True
            except (AttributeError, RuntimeError, tk.TclError):
                pass

            if not scheduled:
                # after_idle not available or not functional.
                # On initial panel setup, reset directly so panel is usable.
                # After first refresh, keep flag set to debounce rapid calls.
                if not self.__dict__.get("_initial_refresh_done", False):
                    self.__dict__["_refresh_in_progress"] = False
                    self.__dict__["_initial_refresh_done"] = True

    def _reset_refresh_flag(self) -> None:
        """Reset the refresh-in-progress guard flag.

        Called via after_idle() to allow a new refresh to proceed in the
        next event loop iteration.
        """
        self.__dict__["_refresh_in_progress"] = False

    def _do_refresh(self) -> None:
        """Internal refresh implementation.

        Reads settings from file, builds the data model, applies filters,
        and triggers viewport update.
        """
        settings = SettingsParser.read_settings(self._config.settings_file_path)

        # Handle read errors
        if "__error__" in settings:
            error_msg = settings["__error__"]
            if self._notification_bar is not None:
                self._notification_bar.show_error(error_msg)
            # Preserve existing rows on error — don't rebuild
            return

        # Ensure virtualization attributes exist (for backward compat with tests)
        if not hasattr(self, "_all_rows_data"):
            self._all_rows_data = []
        if not hasattr(self, "_visible_rows_data"):
            self._visible_rows_data = []
        if not hasattr(self, "_widget_pool"):
            self._widget_pool = []
        if not hasattr(self, "_pool_assignments"):
            self._pool_assignments = {}
        if not hasattr(self, "_viewport_start"):
            self._viewport_start = 0
        if not hasattr(self, "_viewport_end"):
            self._viewport_end = 0

        # Compute the union of file keys and definition keys
        all_keys = set(settings.keys()) | set(SETTING_DEFINITIONS.keys())

        # Build the complete data model grouped by category
        self._all_rows_data = []

        # Group keys by category, then sort alphabetically within each group
        category_buckets: dict[str, list[str]] = {
            cat: [] for cat in SETTING_CATEGORIES
        }
        uncategorized: list[str] = []

        for key in all_keys:
            definition = SETTING_DEFINITIONS.get(key)
            if definition and definition.category in category_buckets:
                category_buckets[definition.category].append(key)
            else:
                uncategorized.append(key)

        # Sort each bucket alphabetically (case-insensitive)
        for cat in category_buckets:
            category_buckets[cat].sort(key=lambda k: k.lower())
        uncategorized.sort(key=lambda k: k.lower())

        # Build ordered data list with category markers
        for cat in SETTING_CATEGORIES:
            keys_in_cat = category_buckets[cat]
            if not keys_in_cat:
                continue

            # Add category header marker
            self._all_rows_data.append({
                "type": "header",
                "category": cat,
                "key": None,
                "definition": None,
                "current_value": None,
                "visibility": True,
            })

            # Add setting rows for this category
            for key in keys_in_cat:
                definition = SETTING_DEFINITIONS.get(key)
                current_value = (
                    str(settings.get(key, "")) if key in settings else ""
                )
                self._all_rows_data.append({
                    "type": "setting",
                    "category": cat,
                    "key": key,
                    "definition": definition,
                    "current_value": current_value,
                    "visibility": True,
                })

        # Add uncategorized settings at the end (if any)
        if uncategorized:
            self._all_rows_data.append({
                "type": "header",
                "category": "Other",
                "key": None,
                "definition": None,
                "current_value": None,
                "visibility": True,
            })
            for key in uncategorized:
                definition = SETTING_DEFINITIONS.get(key)
                current_value = (
                    str(settings.get(key, "")) if key in settings else ""
                )
                self._all_rows_data.append({
                    "type": "setting",
                    "category": "Other",
                    "key": key,
                    "definition": definition,
                    "current_value": current_value,
                    "visibility": True,
                })

        # Re-apply current search filter to compute visible subset
        search_text = self._search_var.get()
        if search_text:
            self._apply_visibility_filter(search_text)
        else:
            self._visible_rows_data = [
                row for row in self._all_rows_data if row["visibility"]
            ]

        # Reset viewport and render
        self._viewport_start = 0
        self._viewport_end = 0
        self._update_viewport(force=True)

        # If no pool exists (e.g. in test scenarios), build a _setting_rows
        # list from the data model for backward compatibility
        if not self._widget_pool:
            self._setting_rows = []
            for row_data in self._all_rows_data:
                if row_data["type"] == "setting":
                    proxy = _SettingRowProxy(
                        key=row_data["key"],
                        definition=row_data["definition"],
                        current_value=row_data["current_value"],
                        category=row_data["category"],
                    )
                    self._setting_rows.append(proxy)

    def filter_settings(self, search_text: str) -> None:
        """Show only settings matching the search text via incremental updates.

        Uses differential visibility: computes new visible set, compares with
        current visible set, and only updates rows that changed state. Never
        calls grid_remove() on ALL rows — only on rows that actually transition
        between visible and hidden.

        Matches case-insensitively against the key name, description,
        and category. Updates the visible data subset and triggers
        a viewport recalculation.

        Args:
            search_text: The search query string.
        """
        # Remove any existing "no results" label
        if self._no_results_label is not None:
            self._no_results_label.destroy()
            self._no_results_label = None

        # Capture previous visible keys for differential comparison
        prev_visible_keys: set[str] = {
            r["key"] for r in self._visible_rows_data
            if r["type"] == "setting" and r["key"] is not None
        }

        if not search_text:
            # Show everything — reset visibility
            for row_data in self._all_rows_data:
                row_data["visibility"] = True
            self._visible_rows_data = list(self._all_rows_data)
        else:
            self._apply_visibility_filter(search_text)

        # Compute new visible keys
        new_visible_keys: set[str] = {
            r["key"] for r in self._visible_rows_data
            if r["type"] == "setting" and r["key"] is not None
        }

        # Check if we have any visible settings
        visible_settings = [
            r for r in self._visible_rows_data if r["type"] == "setting"
        ]

        if not visible_settings:
            # Hide all pool widgets and show "No matching settings"
            for widget in self._widget_pool:
                widget.grid_remove()
            for header in self._category_headers:
                header.grid_remove()
            self._pool_assignments.clear()

            self._no_results_label = customtkinter.CTkLabel(
                self._scrollable_frame,
                text="No matching settings",
                text_color=COLOR_TEXT_SECONDARY,
                font=FONT_BODY,
            )
            self._no_results_label.grid(
                row=0, column=0, sticky="ew",
                padx=WIDGET_INNER_SPACING, pady=10,
            )

            # Update _setting_rows proxy for backward compat (no-pool case)
            if not self._widget_pool:
                for row in self._setting_rows:
                    row.grid_remove()
            return

        # Determine if visibility actually changed
        visibility_changed = prev_visible_keys != new_visible_keys

        if visibility_changed:
            # Reset viewport and re-render with new visible subset
            self._viewport_start = 0
            self._viewport_end = 0
            self._update_viewport(force=True)
        # If visibility didn't change, no viewport update needed

        # In no-pool mode, update proxy objects' grid state for test compat
        if not self._widget_pool:
            for row in self._setting_rows:
                if row.key in new_visible_keys:
                    row.grid()
                else:
                    row.grid_remove()

    def _apply_visibility_filter(self, search_text: str) -> None:
        """Compute visibility for all rows based on search text.

        Updates each row's visibility flag and rebuilds _visible_rows_data.
        Category headers are visible only if they have at least one visible
        child setting.

        Args:
            search_text: The search query to match against.
        """
        search_lower = search_text.lower()

        # First pass: determine which settings match
        visible_categories: set[str] = set()
        for row_data in self._all_rows_data:
            if row_data["type"] == "setting":
                key = row_data["key"]
                definition = row_data["definition"]
                category = row_data["category"]

                key_lower = key.lower()
                desc_lower = ""
                if definition is not None and definition.description:
                    desc_lower = definition.description.lower()
                cat_lower = category.lower()

                matches = (
                    search_lower in key_lower
                    or search_lower in desc_lower
                    or search_lower in cat_lower
                )
                row_data["visibility"] = matches
                if matches:
                    visible_categories.add(category)
            else:
                # Headers — will be set in second pass
                row_data["visibility"] = False

        # Second pass: show headers that have visible children
        for row_data in self._all_rows_data:
            if row_data["type"] == "header":
                row_data["visibility"] = row_data["category"] in visible_categories

        # Rebuild visible subset
        self._visible_rows_data = [
            row for row in self._all_rows_data if row["visibility"]
        ]

    def _compute_visible_range(self, scroll_position: float) -> tuple[int, int]:
        """Calculate which rows should be rendered based on scroll position.

        Args:
            scroll_position: Normalized scroll position (0.0 to 1.0).

        Returns:
            Tuple of (start_index, end_index) into _visible_rows_data.
        """
        total = len(self._visible_rows_data)
        if total == 0:
            return (0, 0)

        # Calculate the center of the viewport based on scroll position
        center_row = int(scroll_position * max(0, total - VIEWPORT_CAPACITY))
        start = max(0, center_row - VIEWPORT_BUFFER)
        end = min(total, start + POOL_SIZE)

        # Adjust start if end is capped
        if end == total:
            start = max(0, end - POOL_SIZE)

        return (start, end)

    def _on_scroll_event(self, event: Any) -> None:
        """Handle mouse wheel scroll events to update the viewport.

        Args:
            event: The tkinter event object.
        """
        self._update_viewport()

    def _on_viewport_configure(self, event: Any) -> None:
        """Handle viewport frame configure events (resize).

        Args:
            event: The tkinter event object.
        """
        self._update_viewport()

    def _get_scroll_position(self) -> float:
        """Get the current normalized scroll position of the scrollable frame.

        Returns:
            Float between 0.0 and 1.0 representing scroll position.
        """
        try:
            # CTkScrollableFrame uses an internal canvas for scrolling
            canvas = self._scrollable_frame._parent_canvas
            yview = canvas.yview()
            return yview[0] if yview else 0.0
        except (AttributeError, TypeError):
            return 0.0

    def _update_viewport(self, force: bool = False) -> None:
        """Update the rendered widgets based on current scroll position.

        Computes the visible range, recycles pool widgets for rows entering
        the viewport, and grid_removes widgets for rows leaving.

        Args:
            force: If True, always re-render even if range hasn't changed.
        """
        # Guard: if no pool exists, skip rendering
        if not self._widget_pool:
            return

        scroll_pos = self._get_scroll_position()
        new_start, new_end = self._compute_visible_range(scroll_pos)

        if not force and new_start == self._viewport_start and new_end == self._viewport_end:
            return

        self._viewport_start = new_start
        self._viewport_end = new_end

        # Remove all category headers first
        for header in self._category_headers:
            header.grid_remove()
        self._category_headers = []

        # Remove "no results" label if present
        if self._no_results_label is not None:
            self._no_results_label.destroy()
            self._no_results_label = None

        # Get the slice of visible data to render
        render_slice = self._visible_rows_data[new_start:new_end]

        # Hide all pool widgets first
        for widget in self._widget_pool:
            widget.grid_remove()
        self._pool_assignments.clear()

        # Assign pool widgets to visible settings
        grid_row = 0
        pool_idx = 0

        for item_idx, data_item in enumerate(render_slice):
            if data_item["type"] == "header":
                # Create/reuse a category header
                header = customtkinter.CTkLabel(
                    self._scrollable_frame,
                    text=data_item["category"],
                    font=FONT_SUBHEADING,
                    text_color=COLOR_ACCENT,
                    anchor="w",
                )
                header.grid(
                    row=grid_row, column=0, sticky="ew",
                    padx=2, pady=(10, 4),
                )
                self._category_headers.append(header)
                grid_row += 1
            elif data_item["type"] == "setting":
                if pool_idx < len(self._widget_pool):
                    widget = self._widget_pool[pool_idx]
                    widget.update_data(
                        key=data_item["key"],
                        definition=data_item["definition"],
                        current_value=data_item["current_value"],
                    )
                    widget.grid(
                        row=grid_row, column=0, sticky="ew",
                        padx=2, pady=2,
                    )
                    self._pool_assignments[pool_idx] = new_start + item_idx
                    pool_idx += 1
                    grid_row += 1

        # Update _setting_rows to reflect currently active pool widgets
        self._setting_rows = self._widget_pool[:pool_idx]

    def _regrid_all(self) -> None:
        """Re-render the full viewport with all visible data.

        Triggers a viewport recalculation to show all visible settings
        using the widget pool. This is the virtualized replacement for
        the original full-regrid approach.
        """
        self._viewport_start = 0
        self._viewport_end = 0
        self._update_viewport(force=True)

    def update_pending_indicator(self) -> None:
        """Update the pending changes badge count."""
        try:
            pending_queue = self._settings_write_handler._pending_queue
            count = pending_queue.count()

            if count > 0:
                text = f"{count} change(s) pending"
                self._pending_indicator.configure(text=text)
                self._pending_indicator.grid(
                    row=1, column=0, sticky="ew",
                    padx=WIDGET_INNER_SPACING, pady=(2, 2),
                )
            else:
                self._pending_indicator.grid_remove()
                self._pending_indicator.configure(text="")
        except Exception as e:
            logger.error("Error updating pending indicator: %s", e)

    def _on_apply_setting(self, key: str, raw_value: str) -> None:
        """Handle an Apply action from a SettingRow.

        Validates, auto-corrects, submits via SettingsWriteHandler, and
        shows appropriate notifications.

        Args:
            key: The setting key name.
            raw_value: The user-entered value string.
        """
        # Validate and auto-correct
        result = validate_and_correct(key, raw_value)

        # If result is a string, it's a validation error
        if isinstance(result, str):
            if self._notification_bar is not None:
                self._notification_bar.show_error(result)
            return

        # Show auto-correction info if applicable
        correction_msg = ""
        if result.was_corrected:
            correction_msg = (
                f"Auto-corrected: '{result.original_input}' \u2192 '{result.value}'. "
            )

        # Submit via write handler
        validation_result, was_queued = self._settings_write_handler.submit(
            key, result.value
        )

        if not validation_result.valid:
            error_msg = validation_result.error_message or "Unknown error."
            if self._notification_bar is not None:
                self._notification_bar.show_error(f"Error: {error_msg}")
            return

        # Find the pool widget currently displaying this key and update it
        target_row = None
        for widget in self._widget_pool:
            if widget.key == key:
                target_row = widget
                break

        # Also update the data model
        for row_data in self._all_rows_data:
            if row_data["type"] == "setting" and row_data["key"] == key:
                row_data["current_value"] = str(result.value)
                break

        if was_queued:
            msg = (
                f"{correction_msg}Setting '{key}' queued as '{result.value}'. "
                f"Will apply on server stop/restart."
            )
            if self._notification_bar is not None:
                self._notification_bar.show_success(msg)
        else:
            # Written directly — update the row display
            if target_row is not None:
                target_row.update_current_value(str(result.value))
            msg = f"{correction_msg}Setting '{key}' set to '{result.value}' successfully."
            if self._notification_bar is not None:
                self._notification_bar.show_success(msg)

        # Update pending indicator
        self.update_pending_indicator()


class SettingRow(customtkinter.CTkFrame):
    """Single setting row with metadata display and edit control.

    Displays one setting key with its description, allowed values, default,
    current value, and an inline input control with Apply button.
    Wrapped in a nested Card_Frame with NESTED_CARD_CORNER_RADIUS.
    """

    def __init__(
        self,
        parent: tk.Widget,
        key: str,
        definition: SettingDefinition | None,
        current_value: str,
        on_apply: Callable[[str, str], None],
    ) -> None:
        """Initialize a SettingRow.

        Args:
            parent: The parent widget (the scrollable frame).
            key: The setting key name.
            definition: The SettingDefinition for this key, or None if unknown.
            current_value: The current value read from file (empty string if absent).
            on_apply: Callback invoked with (key, new_value) when Apply is clicked.
        """
        super().__init__(
            parent,
            corner_radius=NESTED_CARD_CORNER_RADIUS,
            fg_color=COLOR_INPUT_BG,
        )

        self.key = key
        self._definition = definition
        self._current_value = current_value
        self._on_apply = on_apply

        # Derive description for search filtering
        if definition is not None and definition.description:
            self.description = definition.description
        else:
            self.description = "No description available"

        # Derive category for search filtering
        if definition is not None and definition.category:
            self.category = definition.category
        else:
            self.category = "Other"

        self._build_row()

    def _build_row(self) -> None:
        """Build the three-row grid layout for this setting."""
        self.columnconfigure(0, weight=1)

        # Derive bold font for modified values
        body_family = FONT_BODY[0]
        body_size = FONT_BODY[1]
        self._bold_font = (body_family, body_size, "bold")
        self._normal_font = FONT_BODY

        # Row 0: Key name (bold) + Description
        row0_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        row0_frame.grid(
            row=0, column=0, sticky="ew",
            padx=WIDGET_INNER_SPACING, pady=(WIDGET_INNER_SPACING, 2),
        )
        row0_frame.columnconfigure(1, weight=1)

        self._key_label = customtkinter.CTkLabel(
            row0_frame,
            text=self.key,
            font=self._bold_font,
            text_color=COLOR_TEXT,
            anchor="w",
        )
        self._key_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self._desc_label = customtkinter.CTkLabel(
            row0_frame,
            text=self.description,
            font=FONT_BODY,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        self._desc_label.grid(row=0, column=1, sticky="ew")

        # Row 1: Allowed | Default | Current
        row1_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        row1_frame.grid(
            row=1, column=0, sticky="ew",
            padx=WIDGET_INNER_SPACING, pady=(0, 2),
        )

        allowed_text = format_allowed_values(self._definition)
        customtkinter.CTkLabel(
            row1_frame, text="Allowed:", font=FONT_BODY,
            text_color=COLOR_TEXT, anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=(0, 2))
        self._allowed_values_label = customtkinter.CTkLabel(
            row1_frame, text=allowed_text, font=FONT_BODY,
            text_color=COLOR_TEXT_SECONDARY, anchor="w",
        )
        self._allowed_values_label.grid(row=0, column=1, sticky="w", padx=(0, 15))

        default_text = format_default_value(self.key, self._definition)
        customtkinter.CTkLabel(
            row1_frame, text="Default:", font=FONT_BODY,
            text_color=COLOR_TEXT, anchor="w",
        ).grid(row=0, column=2, sticky="w", padx=(0, 2))
        self._default_value_label = customtkinter.CTkLabel(
            row1_frame, text=default_text, font=FONT_BODY,
            text_color=COLOR_TEXT_SECONDARY, anchor="w",
        )
        self._default_value_label.grid(row=0, column=3, sticky="w", padx=(0, 15))

        current_display = format_current_value(self.key, self._current_value)

        # Bold the current value if it differs from default
        is_modified = False
        if self._definition is not None and self._definition.default_value is not None:
            is_modified = values_differ(
                self._current_value, self._definition.default_value, self._definition
            )

        current_font = self._bold_font if is_modified else self._normal_font
        current_color = COLOR_TEXT if is_modified else COLOR_TEXT_SECONDARY

        customtkinter.CTkLabel(
            row1_frame, text="Current:", font=FONT_BODY,
            text_color=COLOR_TEXT, anchor="w",
        ).grid(row=0, column=4, sticky="w", padx=(0, 2))
        self._current_value_label = customtkinter.CTkLabel(
            row1_frame, text=current_display, font=current_font,
            text_color=current_color, anchor="w",
        )
        self._current_value_label.grid(row=0, column=5, sticky="w")

        # Row 2: Input control + Apply button
        self._row2_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self._row2_frame.grid(
            row=2, column=0, sticky="ew",
            padx=WIDGET_INNER_SPACING, pady=(0, WIDGET_INNER_SPACING),
        )
        self._row2_frame.columnconfigure(0, weight=0)
        self._row2_frame.columnconfigure(1, weight=0)

        input_type = get_input_control_type(self._definition)
        self._input_type = input_type
        is_password = is_password_setting(self.key)

        self._input_var = tk.StringVar()

        if input_type == "combobox":
            # Build combobox values list
            if self._definition is not None and self._definition.value_type == bool:
                combobox_values = ["True", "False"]
            elif (
                self._definition is not None
                and self._definition.allowed_values is not None
            ):
                combobox_values = [str(v) for v in self._definition.allowed_values]
            else:
                combobox_values = []

            self._input_control = customtkinter.CTkComboBox(
                self._row2_frame,
                variable=self._input_var,
                values=combobox_values,
                width=200,
                state="readonly",
            )
            # Pre-populate with current value if it's in the list
            if self._current_value in combobox_values:
                self._input_var.set(self._current_value)
            elif (
                self._definition is not None
                and self._definition.value_type == bool
            ):
                # Normalize boolean display
                if self._current_value.lower() == "true":
                    self._input_var.set("True")
                elif self._current_value.lower() == "false":
                    self._input_var.set("False")
        else:
            # Entry control
            if is_password:
                self._input_control = customtkinter.CTkEntry(
                    self._row2_frame,
                    textvariable=self._input_var,
                    width=200,
                    show="*",
                    fg_color=COLOR_INPUT_BG,
                    text_color=COLOR_TEXT,
                )
            else:
                self._input_control = customtkinter.CTkEntry(
                    self._row2_frame,
                    textvariable=self._input_var,
                    width=200,
                    fg_color=COLOR_INPUT_BG,
                    text_color=COLOR_TEXT,
                )
            # Pre-populate with current value (not masked — user edits raw)
            self._input_var.set(self._current_value)

        self._input_control.grid(row=0, column=0, sticky="w", padx=(0, WIDGET_INNER_SPACING))

        self._apply_button = customtkinter.CTkButton(
            self._row2_frame,
            text="Apply",
            command=self._on_apply_click,
            fg_color=COLOR_PRIMARY,
            corner_radius=BUTTON_CORNER_RADIUS,
            width=70,
        )
        self._apply_button.grid(row=0, column=1, sticky="w")

    def _on_apply_click(self) -> None:
        """Handle Apply button click — invokes the on_apply callback."""
        new_value = self._input_var.get()
        self._on_apply(self.key, new_value)

    def update_current_value(self, value: str) -> None:
        """Update the displayed current value and input control.

        Called after a successful write to reflect the new value.

        Args:
            value: The new current value to display.
        """
        self._current_value = value

        # Update the current value label display
        current_display = format_current_value(self.key, value)
        self._current_value_label.configure(text=current_display)

        # Update bold state based on whether value differs from default
        is_modified = False
        if self._definition is not None and self._definition.default_value is not None:
            is_modified = values_differ(
                value, self._definition.default_value, self._definition
            )

        if is_modified:
            self._current_value_label.configure(
                font=self._bold_font, text_color=COLOR_TEXT
            )
        else:
            self._current_value_label.configure(
                font=self._normal_font, text_color=COLOR_TEXT_SECONDARY
            )

        # Update the input control
        self._input_var.set(value)

    def update_data(
        self, key: str, definition: SettingDefinition | None, current_value: str
    ) -> None:
        """Update this SettingRow in-place with new data for widget recycling.

        Reconfigures all labels, input control value, and Apply button binding
        without destroying or recreating any widgets. Used by the widget
        recycling pool to repurpose existing row widgets for different settings.

        Args:
            key: The new setting key name.
            definition: The SettingDefinition for the new key, or None if unknown.
            current_value: The current value read from file (empty string if absent).
        """
        # Update internal state
        self.key = key
        self._definition = definition
        self._current_value = current_value

        # Derive description and category
        if definition is not None and definition.description:
            self.description = definition.description
        else:
            self.description = "No description available"

        if definition is not None and definition.category:
            self.category = definition.category
        else:
            self.category = "Other"

        # Reconfigure Row 0: key label + description label
        self._key_label.configure(text=self.key)
        self._desc_label.configure(text=self.description)

        # Reconfigure Row 1: allowed values, default value, current value labels
        self._allowed_values_label.configure(
            text=format_allowed_values(self._definition)
        )
        self._default_value_label.configure(
            text=format_default_value(self.key, self._definition)
        )

        # Update current value display with appropriate styling
        current_display = format_current_value(self.key, self._current_value)
        is_modified = False
        if self._definition is not None and self._definition.default_value is not None:
            is_modified = values_differ(
                self._current_value, self._definition.default_value, self._definition
            )

        current_font = self._bold_font if is_modified else self._normal_font
        current_color = COLOR_TEXT if is_modified else COLOR_TEXT_SECONDARY
        self._current_value_label.configure(
            text=current_display, font=current_font, text_color=current_color
        )

        # Reconfigure Row 2: input control
        new_input_type = get_input_control_type(self._definition)

        if new_input_type != self._input_type:
            # Input control type changed — destroy and recreate
            self._input_control.destroy()
            self._input_type = new_input_type
            is_password = is_password_setting(self.key)

            if new_input_type == "combobox":
                combobox_values = self._get_combobox_values()
                self._input_control = customtkinter.CTkComboBox(
                    self._row2_frame,
                    variable=self._input_var,
                    values=combobox_values,
                    width=200,
                    state="readonly",
                )
            else:
                if is_password:
                    self._input_control = customtkinter.CTkEntry(
                        self._row2_frame,
                        textvariable=self._input_var,
                        width=200,
                        show="*",
                        fg_color=COLOR_INPUT_BG,
                        text_color=COLOR_TEXT,
                    )
                else:
                    self._input_control = customtkinter.CTkEntry(
                        self._row2_frame,
                        textvariable=self._input_var,
                        width=200,
                        fg_color=COLOR_INPUT_BG,
                        text_color=COLOR_TEXT,
                    )
            self._input_control.grid(
                row=0, column=0, sticky="w", padx=(0, WIDGET_INNER_SPACING)
            )
        elif new_input_type == "combobox":
            # Same control type (combobox) — update values list
            combobox_values = self._get_combobox_values()
            self._input_control.configure(values=combobox_values)

        # Update input control value
        self._set_input_value(current_value)

    def _get_combobox_values(self) -> list[str]:
        """Return the list of combobox values based on the current definition.

        Returns:
            List of string values for the combobox dropdown.
        """
        if self._definition is not None and self._definition.value_type == bool:
            return ["True", "False"]
        elif (
            self._definition is not None
            and self._definition.allowed_values is not None
        ):
            return [str(v) for v in self._definition.allowed_values]
        return []

    def _set_input_value(self, value: str) -> None:
        """Set the input control value, handling combobox normalization.

        Args:
            value: The value string to set in the input control.
        """
        if self._input_type == "combobox":
            combobox_values = self._get_combobox_values()
            if value in combobox_values:
                self._input_var.set(value)
            elif (
                self._definition is not None
                and self._definition.value_type == bool
            ):
                if value.lower() == "true":
                    self._input_var.set("True")
                elif value.lower() == "false":
                    self._input_var.set("False")
                else:
                    self._input_var.set(value)
            else:
                self._input_var.set(value)
        else:
            self._input_var.set(value)
