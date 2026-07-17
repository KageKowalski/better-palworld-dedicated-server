"""Unified settings display and modification panel.

Consolidates the former SettingsView (read-only display) and SettingsEditor
(modification form) into a single searchable, scrollable panel where each
setting is displayed with full metadata and an inline edit control.
"""

import logging
import tkinter as tk
from tkinter import font as tkfont
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

        self._setting_rows: list["SettingRow"] = []
        self._no_results_label: customtkinter.CTkLabel | None = None
        self._category_headers: list[customtkinter.CTkLabel] = []

        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        """Construct the internal grid layout: search, pending indicator, scrollable frame, buttons."""
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

        for header in self._category_headers:
            header.destroy()
        self._category_headers = []

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

        # Track the current grid row in the scrollable frame
        grid_row = 0

        # Build rows in category order with headers
        for cat in SETTING_CATEGORIES:
            keys_in_cat = category_buckets[cat]
            if not keys_in_cat:
                continue

            # Add category header
            header = customtkinter.CTkLabel(
                self._scrollable_frame,
                text=cat,
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

            # Add setting rows for this category
            for key in keys_in_cat:
                definition = SETTING_DEFINITIONS.get(key)
                current_value = (
                    str(settings.get(key, "")) if key in settings else ""
                )

                row = SettingRow(
                    parent=self._scrollable_frame,
                    key=key,
                    definition=definition,
                    current_value=current_value,
                    on_apply=self._on_apply_setting,
                )
                row.grid(
                    row=grid_row, column=0, sticky="ew",
                    padx=2, pady=2,
                )
                self._setting_rows.append(row)
                grid_row += 1

        # Add uncategorized settings at the end (if any)
        if uncategorized:
            header = customtkinter.CTkLabel(
                self._scrollable_frame,
                text="Other",
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

            for key in uncategorized:
                definition = SETTING_DEFINITIONS.get(key)
                current_value = (
                    str(settings.get(key, "")) if key in settings else ""
                )

                row = SettingRow(
                    parent=self._scrollable_frame,
                    key=key,
                    definition=definition,
                    current_value=current_value,
                    on_apply=self._on_apply_setting,
                )
                row.grid(
                    row=grid_row, column=0, sticky="ew",
                    padx=2, pady=2,
                )
                self._setting_rows.append(row)
                grid_row += 1

        # Re-apply current search filter
        search_text = self._search_var.get()
        if search_text:
            self.filter_settings(search_text)

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
            # Show everything — re-grid all headers and rows
            self._regrid_all()
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
                visible_count += 1
                visible_categories.add(row.category)

        # Hide everything first
        for header in self._category_headers:
            header.grid_remove()
        for row in self._setting_rows:
            row.grid_remove()

        # Re-grid headers and matching rows in correct order
        grid_row = 0
        for header in self._category_headers:
            header_text = header.cget("text")
            if header_text in visible_categories:
                header.grid(
                    row=grid_row, column=0, sticky="ew",
                    padx=2, pady=(10, 4),
                )
                grid_row += 1
                # Grid only matching rows that belong to this category
                for row in self._setting_rows:
                    if row.category != header_text:
                        continue
                    key_lower = row.key.lower()
                    desc_lower = row.description.lower()
                    cat_lower = row.category.lower()
                    if (
                        search_lower in key_lower
                        or search_lower in desc_lower
                        or search_lower in cat_lower
                    ):
                        row.grid(
                            row=grid_row, column=0, sticky="ew",
                            padx=2, pady=2,
                        )
                        grid_row += 1

        # Show "No matching settings" if nothing matched
        if visible_count == 0:
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

    def _regrid_all(self) -> None:
        """Re-grid all category headers and setting rows in correct order.

        Iterates through headers and grids each header followed by its
        associated rows, preserving the category-grouped display order.
        """
        # Remove everything first
        for header in self._category_headers:
            header.grid_remove()
        for row in self._setting_rows:
            row.grid_remove()

        grid_row = 0
        for header in self._category_headers:
            header_text = header.cget("text")
            header.grid(
                row=grid_row, column=0, sticky="ew",
                padx=2, pady=(10, 4),
            )
            grid_row += 1
            for row in self._setting_rows:
                if row.category == header_text:
                    row.grid(
                        row=grid_row, column=0, sticky="ew",
                        padx=2, pady=2,
                    )
                    grid_row += 1

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

        key_label = customtkinter.CTkLabel(
            row0_frame,
            text=self.key,
            font=self._bold_font,
            text_color=COLOR_TEXT,
            anchor="w",
        )
        key_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

        desc_label = customtkinter.CTkLabel(
            row0_frame,
            text=self.description,
            font=FONT_BODY,
            text_color=COLOR_TEXT_SECONDARY,
            anchor="w",
        )
        desc_label.grid(row=0, column=1, sticky="ew")

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
        customtkinter.CTkLabel(
            row1_frame, text=allowed_text, font=FONT_BODY,
            text_color=COLOR_TEXT_SECONDARY, anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(0, 15))

        default_text = format_default_value(self.key, self._definition)
        customtkinter.CTkLabel(
            row1_frame, text="Default:", font=FONT_BODY,
            text_color=COLOR_TEXT, anchor="w",
        ).grid(row=0, column=2, sticky="w", padx=(0, 2))
        customtkinter.CTkLabel(
            row1_frame, text=default_text, font=FONT_BODY,
            text_color=COLOR_TEXT_SECONDARY, anchor="w",
        ).grid(row=0, column=3, sticky="w", padx=(0, 15))

        current_display = format_current_value(self.key, self._current_value)

        # Bold the current value if it differs from default
        is_modified = False
        if self._definition is not None and self._definition.default_value is not None:
            is_modified = values_differ(
                self._current_value, self._definition.default_value, self._definition
            )

        current_font = self._bold_font if is_modified else self._normal_font

        customtkinter.CTkLabel(
            row1_frame, text="Current:", font=FONT_BODY,
            text_color=COLOR_TEXT, anchor="w",
        ).grid(row=0, column=4, sticky="w", padx=(0, 2))
        self._current_value_label = customtkinter.CTkLabel(
            row1_frame, text=current_display, font=current_font,
            text_color=COLOR_TEXT, anchor="w",
        )
        self._current_value_label.grid(row=0, column=5, sticky="w")

        # Row 2: Input control + Apply button
        row2_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        row2_frame.grid(
            row=2, column=0, sticky="ew",
            padx=WIDGET_INNER_SPACING, pady=(0, WIDGET_INNER_SPACING),
        )
        row2_frame.columnconfigure(0, weight=0)
        row2_frame.columnconfigure(1, weight=0)

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

            self._input_control = customtkinter.CTkComboBox(
                row2_frame,
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
                    row2_frame,
                    textvariable=self._input_var,
                    width=200,
                    show="*",
                    fg_color=COLOR_INPUT_BG,
                    text_color=COLOR_TEXT,
                )
            else:
                self._input_control = customtkinter.CTkEntry(
                    row2_frame,
                    textvariable=self._input_var,
                    width=200,
                    fg_color=COLOR_INPUT_BG,
                    text_color=COLOR_TEXT,
                )
            # Pre-populate with current value (not masked — user edits raw)
            self._input_var.set(self._current_value)

        self._input_control.grid(row=0, column=0, sticky="w", padx=(0, WIDGET_INNER_SPACING))

        self._apply_button = customtkinter.CTkButton(
            row2_frame,
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
            self._current_value_label.configure(font=self._bold_font)
        else:
            self._current_value_label.configure(font=self._normal_font)

        # Update the input control
        self._input_var.set(value)
