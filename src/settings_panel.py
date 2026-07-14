"""Unified settings display and modification panel.

Consolidates the former SettingsView (read-only display) and SettingsEditor
(modification form) into a single searchable, scrollable panel where each
setting is displayed with full metadata and an inline edit control.
"""

import logging
import tkinter as tk
from tkinter import ttk, font as tkfont
from collections.abc import Callable
from typing import Any

from src.config import WrapperConfig
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


class SettingsPanel(ttk.LabelFrame):
    """Unified settings display and modification panel.

    Replaces the former SettingsView and SettingsEditor with a single scrollable,
    searchable interface showing all setting metadata inline with edit controls.
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
            parent: The parent tkinter widget.
            config: The wrapper configuration (provides settings_file_path).
            wrapper_core: The WrapperCore instance for state queries.
            settings_write_handler: Handler for routing setting writes/queues.
            notification_bar: The NotificationBar instance for messages.
        """
        super().__init__(parent, text="Server Settings")

        self._config = config
        self._wrapper_core = wrapper_core
        self._settings_write_handler = settings_write_handler
        self._notification_bar = notification_bar

        self._setting_rows: list["SettingRow"] = []
        self._no_results_label: ttk.Label | None = None

        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        """Construct the internal layout: search, pending indicator, canvas, refresh."""
        # 1. Search input field
        search_frame = ttk.Frame(self)
        search_frame.pack(fill="x", padx=5, pady=(5, 2))

        ttk.Label(search_frame, text="Search:").pack(side="left", padx=(0, 5))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        self._search_entry = ttk.Entry(
            search_frame, textvariable=self._search_var, width=40
        )
        self._search_entry.pack(side="left", fill="x", expand=True)

        # 2. Pending changes indicator (hidden when queue empty)
        self._pending_indicator = ttk.Label(self, text="", foreground="orange")
        self._pending_indicator.pack(fill="x", padx=5, pady=(2, 2))
        self._pending_indicator.pack_forget()

        # 3. Scrollable canvas + frame container
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill="both", expand=True, padx=5, pady=2)

        self._canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        self._scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self._canvas.yview
        )
        self._canvas.configure(yscrollcommand=self._scrollbar.set)

        self._scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        # Inner frame for SettingRow widgets
        self._inner_frame = ttk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._inner_frame, anchor="nw"
        )

        # Update scroll region when inner frame resizes
        self._inner_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Bind mousewheel for scrolling
        self._canvas.bind("<Enter>", self._bind_mousewheel)
        self._canvas.bind("<Leave>", self._unbind_mousewheel)

        # 4. Refresh button
        self._refresh_button = ttk.Button(
            self, text="Refresh", command=self.refresh
        )
        self._refresh_button.pack(anchor="e", padx=5, pady=(2, 5))

    def _on_frame_configure(self, event: "tk.Event") -> None:
        """Update canvas scroll region when inner frame size changes."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event: "tk.Event") -> None:
        """Stretch the inner frame to match canvas width."""
        self._canvas.itemconfig(self._canvas_window, width=event.width)

    def _bind_mousewheel(self, event: "tk.Event") -> None:
        """Bind mousewheel scrolling when mouse enters canvas."""
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, event: "tk.Event") -> None:
        """Unbind mousewheel scrolling when mouse leaves canvas."""
        self._canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: "tk.Event") -> None:
        """Scroll the canvas on mousewheel events."""
        self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_search_changed(self, *args) -> None:
        """Trace callback for the search StringVar — limits length and filters."""
        current = self._search_var.get()
        if len(current) > self.MAX_SEARCH_LENGTH:
            self._search_var.set(current[: self.MAX_SEARCH_LENGTH])
            return
        self.filter_settings(current)

    def refresh(self) -> None:
        """Re-read settings file and rebuild all SettingRows grouped by category."""
        settings = SettingsParser.read_settings(self._config.settings_file_path)

        # Handle read errors
        if "__error__" in settings:
            error_msg = settings["__error__"]
            if self._notification_bar is not None:
                self._notification_bar.show_error(error_msg)
            # Preserve existing rows on error — don't rebuild
            return

        # Compute the union of file keys and definition keys
        all_keys = set(settings.keys()) | set(SETTING_DEFINITIONS.keys())

        # Destroy existing rows and headers
        for row in self._setting_rows:
            row.destroy()
        self._setting_rows.clear()

        for header in getattr(self, "_category_headers", []):
            header.destroy()
        self._category_headers: list[ttk.Label] = []

        # Hide "no results" label if present
        if self._no_results_label is not None:
            self._no_results_label.destroy()
            self._no_results_label = None

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

        # Build rows in category order with headers
        for cat in SETTING_CATEGORIES:
            keys_in_cat = category_buckets[cat]
            if not keys_in_cat:
                continue

            # Add category header
            header = ttk.Label(
                self._inner_frame,
                text=cat,
                font=self._get_header_font(),
                anchor="w",
            )
            header.pack(fill="x", padx=2, pady=(10, 4))
            self._category_headers.append(header)

            # Add setting rows for this category
            for key in keys_in_cat:
                definition = SETTING_DEFINITIONS.get(key)
                current_value = (
                    str(settings.get(key, "")) if key in settings else ""
                )

                row = SettingRow(
                    parent=self._inner_frame,
                    key=key,
                    definition=definition,
                    current_value=current_value,
                    on_apply=self._on_apply_setting,
                )
                row.pack(fill="x", padx=2, pady=2)
                self._setting_rows.append(row)

        # Add uncategorized settings at the end (if any)
        if uncategorized:
            header = ttk.Label(
                self._inner_frame,
                text="Other",
                font=self._get_header_font(),
                anchor="w",
            )
            header.pack(fill="x", padx=2, pady=(10, 4))
            self._category_headers.append(header)

            for key in uncategorized:
                definition = SETTING_DEFINITIONS.get(key)
                current_value = (
                    str(settings.get(key, "")) if key in settings else ""
                )

                row = SettingRow(
                    parent=self._inner_frame,
                    key=key,
                    definition=definition,
                    current_value=current_value,
                    on_apply=self._on_apply_setting,
                )
                row.pack(fill="x", padx=2, pady=2)
                self._setting_rows.append(row)

        # Re-apply current search filter
        search_text = self._search_var.get()
        if search_text:
            self.filter_settings(search_text)

    def _get_header_font(self):
        """Return a bold, slightly larger font for category headers."""
        try:
            from tkinter import font as tkfont
            default_font = tkfont.nametofont("TkDefaultFont")
            header_font = default_font.copy()
            header_font.configure(weight="bold", size=default_font.cget("size") + 2)
            return header_font
        except Exception:
            return None

    def filter_settings(self, search_text: str) -> None:
        """Show only SettingRows matching the search text.

        Matches case-insensitively against the key name, description,
        and category. Category headers are hidden/shown based on whether
        they have visible children.

        Args:
            search_text: The search query string.
        """
        # Remove any existing "no results" label
        if self._no_results_label is not None:
            self._no_results_label.destroy()
            self._no_results_label = None

        if not search_text:
            # Show all rows and headers
            for header in self._category_headers:
                header.pack(fill="x", padx=2, pady=(10, 4))
            for row in self._setting_rows:
                row.pack(fill="x", padx=2, pady=2)
            return

        search_lower = search_text.lower()
        visible_count = 0

        # Track which categories have visible rows
        visible_categories: set[str] = set()

        for row in self._setting_rows:
            key_lower = row.key.lower()
            desc_lower = row.description.lower()
            cat_lower = row.category.lower()
            if (
                search_lower in key_lower
                or search_lower in desc_lower
                or search_lower in cat_lower
            ):
                row.pack(fill="x", padx=2, pady=2)
                visible_count += 1
                visible_categories.add(row.category)
            else:
                row.pack_forget()

        # Show/hide category headers based on whether they have visible rows
        for header in self._category_headers:
            header_text = header.cget("text")
            if header_text in visible_categories:
                header.pack(fill="x", padx=2, pady=(10, 4))
            else:
                header.pack_forget()

        # Show "No matching settings" if nothing matched
        if visible_count == 0:
            self._no_results_label = ttk.Label(
                self._inner_frame, text="No matching settings"
            )
            self._no_results_label.pack(fill="x", padx=5, pady=10)

    def update_pending_indicator(self) -> None:
        """Update the pending changes badge count."""
        try:
            pending_queue = self._settings_write_handler._pending_queue
            count = pending_queue.count()

            if count > 0:
                text = f"{count} change(s) pending"
                self._pending_indicator.configure(text=text)
                self._pending_indicator.pack(fill="x", padx=5, pady=(2, 2))
            else:
                self._pending_indicator.pack_forget()
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

        # Find the row and update it on success
        target_row = None
        for row in self._setting_rows:
            if row.key == key:
                target_row = row
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


class SettingRow(ttk.Frame):
    """Single setting row with metadata display and edit control.

    Displays one setting key with its description, allowed values, default,
    current value, and an inline input control with Apply button.
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
            parent: The parent tkinter widget (the inner frame of the canvas).
            key: The setting key name.
            definition: The SettingDefinition for this key, or None if unknown.
            current_value: The current value read from file (empty string if absent).
            on_apply: Callback invoked with (key, new_value) when Apply is clicked.
        """
        super().__init__(parent, relief="groove", borderwidth=1, padding=4)

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
        """Build the three-row layout for this setting."""
        # Attempt to create a bold font variant
        try:
            default_font = tkfont.nametofont("TkDefaultFont")
            self._bold_font = default_font.copy()
            self._bold_font.configure(weight="bold")
        except Exception:
            self._bold_font = None

        # Row 1: Key name (bold) + Description
        row1 = ttk.Frame(self)
        row1.pack(fill="x", pady=(0, 2))

        key_label = ttk.Label(row1, text=self.key, font=self._bold_font)
        key_label.pack(side="left", padx=(0, 10))

        desc_label = ttk.Label(row1, text=self.description, foreground="gray")
        desc_label.pack(side="left", fill="x", expand=True)

        # Row 2: Allowed | Default | Current
        row2 = ttk.Frame(self)
        row2.pack(fill="x", pady=(0, 2))

        allowed_text = format_allowed_values(self._definition)
        ttk.Label(row2, text="Allowed:").pack(side="left", padx=(0, 2))
        ttk.Label(row2, text=allowed_text).pack(side="left", padx=(0, 15))

        default_text = format_default_value(self.key, self._definition)
        ttk.Label(row2, text="Default:").pack(side="left", padx=(0, 2))
        ttk.Label(row2, text=default_text).pack(side="left", padx=(0, 15))

        current_display = format_current_value(self.key, self._current_value)
        ttk.Label(row2, text="Current:").pack(side="left", padx=(0, 2))

        # Bold the current value if it differs from default
        is_modified = False
        if self._definition is not None and self._definition.default_value is not None:
            is_modified = values_differ(
                self._current_value, self._definition.default_value, self._definition
            )

        current_font = self._bold_font if is_modified else None
        self._current_value_label = ttk.Label(
            row2, text=current_display, font=current_font
        )
        self._current_value_label.pack(side="left")

        # Row 3: Input control + Apply button
        row3 = ttk.Frame(self)
        row3.pack(fill="x")

        input_type = get_input_control_type(self._definition)
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

            self._input_control = ttk.Combobox(
                row3,
                textvariable=self._input_var,
                values=combobox_values,
                width=30,
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
                self._input_control = ttk.Entry(
                    row3, textvariable=self._input_var, width=30, show="*"
                )
            else:
                self._input_control = ttk.Entry(
                    row3, textvariable=self._input_var, width=30
                )
            # Pre-populate with current value (not masked — user edits raw)
            self._input_var.set(self._current_value)

        self._input_control.pack(side="left", padx=(0, 5))

        self._apply_button = ttk.Button(
            row3, text="Apply", command=self._on_apply_click
        )
        self._apply_button.pack(side="left")

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
            self._current_value_label.configure(font=self._bold_font)
        else:
            self._current_value_label.configure(font="")

        # Update the input control
        self._input_var.set(value)
