# Property 2: Preservation - Non-Performance Behavior Unchanged
"""Preservation property tests for GUI settings panel behavior.

These tests MUST PASS on the current unfixed code. They capture baseline
behavior that the bugfix must not regress:
  - Search filtering matches case-insensitively against key, description, category
  - Apply button validates and auto-corrects via validate_and_correct()
  - Category headers group settings in canonical order with alphabetical sorting
  - Settings file errors during refresh preserve existing rows and show notification
  - Pending changes indicator displays correct count
  - "No matching settings" label displays when search returns zero matches

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

from src.settings_parser import SETTING_DEFINITIONS, SETTING_CATEGORIES, SettingDefinition
from src.validation import validate_and_correct, CorrectionResult


# --- Helpers ---


def _build_mock_settings() -> dict[str, str]:
    """Build a settings dict with all known setting keys and string values."""
    settings_data = {}
    for key, defn in SETTING_DEFINITIONS.items():
        if defn.default_value is not None:
            settings_data[key] = str(defn.default_value)
        else:
            settings_data[key] = "test_value"
    return settings_data


def _write_settings_file(directory: Path) -> Path:
    """Write a valid PalWorldSettings.ini file and return its path."""
    settings_data = _build_mock_settings()
    ini_content = "[/Script/Pal.PalGameWorldSettings]\n"
    ini_content += "OptionSettings=("
    ini_content += ",".join(f"{k}={v}" for k, v in settings_data.items())
    ini_content += ")\n"

    settings_file = directory / "PalWorldSettings.ini"
    settings_file.write_text(ini_content, encoding="utf-8")
    return settings_file


def _make_mock_label(*args, **kwargs):
    """Create a mock CTkLabel that remembers its 'text' kwarg for cget()."""
    mock = MagicMock()
    stored_config = dict(kwargs)

    def cget(attr):
        return stored_config.get(attr, "")

    def configure(**kw):
        stored_config.update(kw)

    mock.cget = cget
    mock.configure = configure
    return mock


def _create_panel(settings_file: Path):
    """Create a SettingsPanel with mocked tkinter, refresh it, and return it."""
    from src.config import WrapperConfig
    from src.settings_panel import SettingsPanel

    config = WrapperConfig(
        server_exe_path=settings_file.parent / "PalServer.exe",
        settings_file_path=settings_file,
    )

    mock_core = MagicMock()
    mock_write_handler = MagicMock()
    mock_write_handler._pending_queue = MagicMock()
    mock_write_handler._pending_queue.count = MagicMock(return_value=0)
    mock_notification_bar = MagicMock()

    mock_var = MagicMock()
    mock_var.get.return_value = ""
    mock_var.trace_add = MagicMock()
    mock_var.set = MagicMock()

    mock_scrollable = MagicMock()
    mock_scrollable.columnconfigure = MagicMock()

    panel = SettingsPanel.__new__(SettingsPanel)
    panel._config = config
    panel._wrapper_core = mock_core
    panel._settings_write_handler = mock_write_handler
    panel._notification_bar = mock_notification_bar
    panel._setting_rows = []
    panel._no_results_label = None
    panel._category_headers = []
    panel._search_var = mock_var
    panel._scrollable_frame = mock_scrollable
    panel._pending_indicator = MagicMock()

    return panel


# --- Strategies ---

# Generate search text that could match against setting keys, descriptions, or categories
_search_text_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs")),
    min_size=1,
    max_size=30,
)

# Generate valid setting keys from the known definitions
_setting_key_strategy = st.sampled_from(list(SETTING_DEFINITIONS.keys()))

# Generate valid float values within a setting's range
_float_value_strategy = st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False)

# Generate valid int values
_int_value_strategy = st.integers(min_value=0, max_value=100)


class TestPreservationSearchFiltering:
    """Property tests for search/filter behavior preservation.

    **Validates: Requirements 3.2, 3.3**
    """

    @given(search_text=_search_text_strategy)
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_search_matches_case_insensitively_against_key_description_category(
        self, search_text: str
    ) -> None:
        """For any search text, visible setting keys match case-insensitive
        matching against key name, description, and category.

        Computes expected matches independently and verifies filter_settings()
        produces the same visible set.

        **Validates: Requirements 3.2**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            settings_file = _write_settings_file(tmp_path)

            with patch("src.settings_panel.customtkinter.CTkFrame.__init__", return_value=None), \
                 patch("src.settings_panel.customtkinter.CTkScrollableFrame") as mock_scroll, \
                 patch("src.settings_panel.customtkinter.CTkEntry") as mock_entry, \
                 patch("src.settings_panel.customtkinter.CTkLabel", side_effect=_make_mock_label), \
                 patch("src.settings_panel.customtkinter.CTkButton") as mock_btn, \
                 patch("src.settings_panel.customtkinter.CTkComboBox") as mock_combo, \
                 patch("src.settings_panel.tk.StringVar") as mock_sv:

                mock_scroll.return_value = MagicMock()
                mock_entry.return_value = MagicMock()
                mock_btn.return_value = MagicMock()
                mock_combo.return_value = MagicMock()

                mock_var = MagicMock()
                mock_var.get.return_value = ""
                mock_var.trace_add = MagicMock()
                mock_var.set = MagicMock()
                mock_sv.return_value = mock_var

                panel = _create_panel(settings_file)
                panel.refresh()

                # Compute expected matches independently
                search_lower = search_text.lower()
                expected_visible_keys = set()
                for row in panel._setting_rows:
                    if (
                        search_lower in row.key.lower()
                        or search_lower in row.description.lower()
                        or search_lower in row.category.lower()
                    ):
                        expected_visible_keys.add(row.key)

                # Reset grid tracking on rows
                for row in panel._setting_rows:
                    row.grid = MagicMock()
                    row.grid_remove = MagicMock()

                # Apply filter
                panel.filter_settings(search_text)

                # Determine which rows are visible after filtering.
                # Current behavior: filter_settings() calls grid_remove() on ALL rows,
                # then calls grid() on matching rows. So a visible row has grid() called
                # (even if grid_remove was also called before it).
                actual_visible_keys = set()
                for row in panel._setting_rows:
                    if row.grid.called:
                        actual_visible_keys.add(row.key)

            assert actual_visible_keys == expected_visible_keys, (
                f"Search '{search_text}' produced wrong visible set.\n"
                f"Expected {len(expected_visible_keys)} rows, got {len(actual_visible_keys)}.\n"
                f"Missing: {expected_visible_keys - actual_visible_keys}\n"
                f"Extra: {actual_visible_keys - expected_visible_keys}"
            )

    @given(search_text=st.text(
        alphabet=st.characters(
            whitelist_categories=("L",),
            whitelist_characters="!@#$%^&*()_+{}[]|\\:;<>?/~`"
        ),
        min_size=20,
        max_size=50,
    ))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_no_results_label_displays_when_search_returns_zero_matches(
        self, search_text: str
    ) -> None:
        """'No matching settings' label displays when search returns zero matches.

        Uses long random strings unlikely to match any setting to verify the
        no-results behavior.

        **Validates: Requirements 3.3**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            settings_file = _write_settings_file(tmp_path)

            with patch("src.settings_panel.customtkinter.CTkFrame.__init__", return_value=None), \
                 patch("src.settings_panel.customtkinter.CTkScrollableFrame") as mock_scroll, \
                 patch("src.settings_panel.customtkinter.CTkEntry") as mock_entry, \
                 patch("src.settings_panel.customtkinter.CTkLabel", side_effect=_make_mock_label), \
                 patch("src.settings_panel.customtkinter.CTkButton") as mock_btn, \
                 patch("src.settings_panel.customtkinter.CTkComboBox") as mock_combo, \
                 patch("src.settings_panel.tk.StringVar") as mock_sv:

                mock_scroll.return_value = MagicMock()
                mock_entry.return_value = MagicMock()
                mock_btn.return_value = MagicMock()
                mock_combo.return_value = MagicMock()

                mock_var = MagicMock()
                mock_var.get.return_value = ""
                mock_var.trace_add = MagicMock()
                mock_var.set = MagicMock()
                mock_sv.return_value = mock_var

                panel = _create_panel(settings_file)
                panel.refresh()

                # Verify no matches exist for this search text
                search_lower = search_text.lower()
                has_matches = any(
                    search_lower in row.key.lower()
                    or search_lower in row.description.lower()
                    or search_lower in row.category.lower()
                    for row in panel._setting_rows
                )

                if not has_matches:
                    # Apply filter — should show "No matching settings"
                    panel.filter_settings(search_text)

                    # The no_results_label should be set (not None)
                    assert panel._no_results_label is not None, (
                        f"Search '{search_text[:20]}...' returned zero matches but "
                        f"_no_results_label was not created."
                    )


class TestPreservationApplyValidation:
    """Property tests for apply/validation behavior preservation.

    **Validates: Requirements 3.1, 3.6**
    """

    @given(key=_setting_key_strategy)
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_apply_produces_identical_validation_result(self, key: str) -> None:
        """For any valid setting key with its default value, apply produces
        identical validation/auto-correction result via validate_and_correct().

        Tests that the validation path works correctly for default values
        of each setting definition.

        **Validates: Requirements 3.1**
        """
        defn = SETTING_DEFINITIONS[key]

        # Use the default value as input string
        if defn.default_value is not None:
            raw_value = str(defn.default_value)
        else:
            raw_value = ""

        # Call validate_and_correct directly (this is what _on_apply_setting uses)
        result = validate_and_correct(key, raw_value)

        # For default values, validation should succeed (return CorrectionResult, not str)
        assert not isinstance(result, str), (
            f"validate_and_correct('{key}', '{raw_value}') returned error: {result}"
        )
        assert isinstance(result, CorrectionResult), (
            f"Expected CorrectionResult for key '{key}', got {type(result)}"
        )
        # The result should have a value
        assert result.value is not None, (
            f"CorrectionResult for key '{key}' has None value"
        )

    @given(
        data=st.data(),
    )
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_apply_validation_for_typed_values(self, data: st.DataObject) -> None:
        """For any setting with typed values, validate_and_correct produces
        consistent results for values within the valid range.

        **Validates: Requirements 3.1**
        """
        # Pick a setting key that has numeric type with ranges
        numeric_keys = [
            k for k, d in SETTING_DEFINITIONS.items()
            if d.value_type in (int, float)
            and d.min_value is not None
            and d.max_value is not None
        ]
        key = data.draw(st.sampled_from(numeric_keys))
        defn = SETTING_DEFINITIONS[key]

        # Generate a value within the valid range
        if defn.value_type == int:
            value = data.draw(st.integers(
                min_value=int(defn.min_value),
                max_value=int(defn.max_value),
            ))
            raw_value = str(value)
        else:
            value = data.draw(st.floats(
                min_value=float(defn.min_value),
                max_value=float(defn.max_value),
                allow_nan=False,
                allow_infinity=False,
            ))
            raw_value = str(value)

        result = validate_and_correct(key, raw_value)

        # Should succeed for in-range values
        assert not isinstance(result, str), (
            f"validate_and_correct('{key}', '{raw_value}') returned error: {result}"
        )
        assert isinstance(result, CorrectionResult)
        # The corrected value should be the same type
        if defn.value_type == int:
            assert isinstance(result.value, int), (
                f"Expected int result for '{key}', got {type(result.value)}"
            )
            assert result.value == int(raw_value)
        else:
            assert isinstance(result.value, float), (
                f"Expected float result for '{key}', got {type(result.value)}"
            )


class TestPreservationCategoryGrouping:
    """Property tests for category ordering and alphabetical sorting preservation.

    **Validates: Requirements 3.8**
    """

    @given(data=st.data())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_settings_grouped_in_canonical_category_order(self, data: st.DataObject) -> None:
        """Settings are grouped by category in canonical order:
        Performances, Server management, Features, Game balances.

        For any subset of settings, the category headers appear in canonical order
        and settings within each category are sorted alphabetically (case-insensitive).

        **Validates: Requirements 3.8**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            settings_file = _write_settings_file(tmp_path)

            with patch("src.settings_panel.customtkinter.CTkFrame.__init__", return_value=None), \
                 patch("src.settings_panel.customtkinter.CTkScrollableFrame") as mock_scroll, \
                 patch("src.settings_panel.customtkinter.CTkEntry") as mock_entry, \
                 patch("src.settings_panel.customtkinter.CTkLabel", side_effect=_make_mock_label), \
                 patch("src.settings_panel.customtkinter.CTkButton") as mock_btn, \
                 patch("src.settings_panel.customtkinter.CTkComboBox") as mock_combo, \
                 patch("src.settings_panel.tk.StringVar") as mock_sv:

                mock_scroll.return_value = MagicMock()
                mock_entry.return_value = MagicMock()
                mock_btn.return_value = MagicMock()
                mock_combo.return_value = MagicMock()

                mock_var = MagicMock()
                mock_var.get.return_value = ""
                mock_var.trace_add = MagicMock()
                mock_var.set = MagicMock()
                mock_sv.return_value = mock_var

                panel = _create_panel(settings_file)
                panel.refresh()

                # Verify category headers are in canonical order
                header_texts = [
                    h.cget("text") for h in panel._category_headers
                    if h.cget("text") in SETTING_CATEGORIES
                ]

                # Filter to only canonical categories (ignore "Other" if present)
                expected_order = [
                    cat for cat in SETTING_CATEGORIES
                    if cat in header_texts
                ]

                assert header_texts == expected_order, (
                    f"Category headers not in canonical order.\n"
                    f"Expected: {expected_order}\n"
                    f"Got: {header_texts}"
                )

                # Verify alphabetical sorting within each category
                for cat in SETTING_CATEGORIES:
                    keys_in_cat = [
                        row.key for row in panel._setting_rows
                        if row.category == cat
                    ]
                    sorted_keys = sorted(keys_in_cat, key=lambda k: k.lower())
                    assert keys_in_cat == sorted_keys, (
                        f"Settings in '{cat}' not sorted alphabetically.\n"
                        f"Expected: {sorted_keys[:5]}...\n"
                        f"Got: {keys_in_cat[:5]}..."
                    )


class TestPreservationErrorHandling:
    """Property tests for error handling preservation during refresh.

    **Validates: Requirements 3.4**
    """

    @given(error_msg=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "Zs", "P")),
        min_size=1,
        max_size=100,
    ))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_settings_file_error_preserves_existing_rows_and_shows_notification(
        self, error_msg: str
    ) -> None:
        """For any settings file error during refresh, existing rows are preserved
        and error notification is shown.

        Simulates SettingsParser.read_settings returning {"__error__": msg} and
        verifies existing rows remain intact and notification_bar.show_error is called.

        **Validates: Requirements 3.4**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            settings_file = _write_settings_file(tmp_path)

            with patch("src.settings_panel.customtkinter.CTkFrame.__init__", return_value=None), \
                 patch("src.settings_panel.customtkinter.CTkScrollableFrame") as mock_scroll, \
                 patch("src.settings_panel.customtkinter.CTkEntry") as mock_entry, \
                 patch("src.settings_panel.customtkinter.CTkLabel") as mock_label, \
                 patch("src.settings_panel.customtkinter.CTkButton") as mock_btn, \
                 patch("src.settings_panel.customtkinter.CTkComboBox") as mock_combo, \
                 patch("src.settings_panel.tk.StringVar") as mock_sv:

                mock_scroll.return_value = MagicMock()
                mock_entry.return_value = MagicMock()
                mock_label.return_value = MagicMock()
                mock_btn.return_value = MagicMock()
                mock_combo.return_value = MagicMock()

                mock_var = MagicMock()
                mock_var.get.return_value = ""
                mock_var.trace_add = MagicMock()
                mock_var.set = MagicMock()
                mock_sv.return_value = mock_var

                panel = _create_panel(settings_file)

                # Do initial refresh to populate rows
                panel.refresh()
                initial_row_count = len(panel._setting_rows)
                initial_row_keys = [row.key for row in panel._setting_rows]

                assert initial_row_count > 0, "Initial refresh should create rows"

                # Now simulate a read error on next refresh
                with patch("src.settings_panel.SettingsParser.read_settings") as mock_read:
                    mock_read.return_value = {"__error__": error_msg}

                    panel.refresh()

                # Rows should be preserved (not destroyed)
                assert len(panel._setting_rows) == initial_row_count, (
                    f"Rows changed after error refresh: "
                    f"had {initial_row_count}, now {len(panel._setting_rows)}"
                )
                current_keys = [row.key for row in panel._setting_rows]
                assert current_keys == initial_row_keys, (
                    "Row keys changed after error refresh"
                )

                # Error notification should have been shown
                panel._notification_bar.show_error.assert_called_with(error_msg)


class TestPreservationPendingIndicator:
    """Property tests for pending changes indicator preservation.

    **Validates: Requirements 3.7**
    """

    @given(pending_count=st.integers(min_value=0, max_value=100))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_pending_indicator_displays_correct_count(
        self, pending_count: int
    ) -> None:
        """Pending changes indicator displays the correct count from the queue.

        **Validates: Requirements 3.7**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            settings_file = _write_settings_file(tmp_path)

            with patch("src.settings_panel.customtkinter.CTkFrame.__init__", return_value=None), \
                 patch("src.settings_panel.customtkinter.CTkScrollableFrame") as mock_scroll, \
                 patch("src.settings_panel.customtkinter.CTkEntry") as mock_entry, \
                 patch("src.settings_panel.customtkinter.CTkLabel") as mock_label, \
                 patch("src.settings_panel.customtkinter.CTkButton") as mock_btn, \
                 patch("src.settings_panel.customtkinter.CTkComboBox") as mock_combo, \
                 patch("src.settings_panel.tk.StringVar") as mock_sv:

                mock_scroll.return_value = MagicMock()
                mock_entry.return_value = MagicMock()
                mock_label.return_value = MagicMock()
                mock_btn.return_value = MagicMock()
                mock_combo.return_value = MagicMock()

                mock_var = MagicMock()
                mock_var.get.return_value = ""
                mock_var.trace_add = MagicMock()
                mock_var.set = MagicMock()
                mock_sv.return_value = mock_var

                panel = _create_panel(settings_file)
                panel.refresh()

                # Set up mock pending queue count
                panel._settings_write_handler._pending_queue.count.return_value = pending_count

                # Call update_pending_indicator
                panel.update_pending_indicator()

                if pending_count > 0:
                    expected_text = f"{pending_count} change(s) pending"
                    panel._pending_indicator.configure.assert_called()
                    # Verify the text was set correctly
                    configure_calls = panel._pending_indicator.configure.call_args_list
                    text_found = any(
                        call_args[1].get("text") == expected_text
                        for call_args in configure_calls
                        if call_args[1]
                    )
                    assert text_found, (
                        f"Expected indicator text '{expected_text}', "
                        f"configure calls: {configure_calls}"
                    )
                    # Should be gridded (visible)
                    panel._pending_indicator.grid.assert_called()
                else:
                    # Should be hidden
                    panel._pending_indicator.grid_remove.assert_called()
