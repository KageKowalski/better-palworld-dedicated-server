# Property 1: Bug Condition - GUI Operations Exceed Acceptable Latency
# These tests validate the expected (correct) behavior after the performance fix.
"""Bug condition exploration tests for GUI performance freezes.

Tests exercise:
1. refresh() with ~119 settings — asserts completes within 100ms
2. filter_settings() with ~119 pre-built rows — asserts completes within 100ms
3. _regrid_all() — asserts grid operations are O(visible) not O(total)
4. Concurrent refresh() — asserts second call is rejected
5. Search debounce — asserts filter_settings() is called only once after rapid keystrokes

EXPECTED BEHAVIOR: These tests encode the correct performance requirements.
On UNFIXED code they FAIL (confirming the bug exists).
After the fix is implemented, they PASS (confirming the fix works).
"""

import tempfile
import time
import tkinter as tk
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st

from src.config import WrapperConfig
from src.settings_parser import SETTING_DEFINITIONS, SETTING_CATEGORIES, SettingDefinition


# --- Constants matching design spec ---
VIEWPORT_CAPACITY = 30
TOTAL_SETTINGS_COUNT = 119
MAX_OPERATION_TIME_MS = 100


# --- Helper: generate mock settings data ---

def _build_mock_settings() -> dict[str, str]:
    """Build a settings dict with all 119 known setting keys and string values."""
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


def _create_panel_with_rows(settings_file: Path):
    """Create a SettingsPanel with fully mocked tkinter and run refresh().

    Uses patching at the customtkinter.CTkFrame level to prevent real
    tkinter widget creation while still exercising the panel logic.

    Returns the panel with rows built.
    """
    import customtkinter

    from src.settings_panel import SettingsPanel, SettingRow

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

    # Build the panel without calling __init__ (skip CTkFrame init)
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


class TestBugConditionGUIPerformance:
    """Exploration tests that surface GUI performance bugs in SettingsPanel.

    These tests encode the EXPECTED (correct) behavior. They will FAIL on
    unfixed code, confirming the performance bugs exist. After fixes, they PASS.

    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5**
    """

    # -------------------------------------------------------------------------
    # Test 1: refresh() with 119 settings must complete within 100ms
    # Bug: creates ~1,500 widgets from scratch every time
    # -------------------------------------------------------------------------

    @given(widget_count=st.integers(min_value=VIEWPORT_CAPACITY + 1, max_value=TOTAL_SETTINGS_COUNT))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_refresh_completes_within_100ms(self, widget_count: int) -> None:
        """refresh() with >VIEWPORT_CAPACITY settings must complete within 100ms.

        Bug (unfixed): refresh() destroys ALL existing SettingRow widgets and
        recreates them from scratch (~119 rows × ~13 widgets each = ~1,500 widgets),
        taking >500ms. The fix should reuse widgets via recycling pool.

        **Validates: Requirements 2.4**
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

                panel = _create_panel_with_rows(settings_file)

                # Time the refresh operation
                start = time.perf_counter()
                panel.refresh()
                elapsed_ms = (time.perf_counter() - start) * 1000

            # EXPECTED BEHAVIOR: refresh completes within 100ms
            assert elapsed_ms < MAX_OPERATION_TIME_MS, (
                f"refresh() with {len(panel._setting_rows)} settings took {elapsed_ms:.1f}ms "
                f"(limit: {MAX_OPERATION_TIME_MS}ms). Bug: destroys and recreates all widgets "
                f"instead of recycling."
            )

    # -------------------------------------------------------------------------
    # Test 2: filter_settings() must only grid_remove() rows that change state
    # Bug: calls grid_remove() on ALL 119 rows, then re-grids matching ones
    # -------------------------------------------------------------------------

    @given(search_term=st.sampled_from(["server", "rate", "pal", "time", "damage"]))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_filter_settings_only_updates_changed_rows(self, search_term: str) -> None:
        """filter_settings() must only grid_remove rows that change visibility state.

        Bug (unfixed): filter_settings() calls grid_remove() on ALL ~119 rows
        then re-grids only matching ones, triggering massive layout recalculation.
        The fix should update only rows that change visibility state (differential).

        **Validates: Requirements 2.3**
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

                panel = _create_panel_with_rows(settings_file)

                # Build all rows first
                panel.refresh()
                total_rows = len(panel._setting_rows)

                # Count how many rows actually match the search term
                search_lower = search_term.lower()
                matching_rows = sum(
                    1 for row in panel._setting_rows
                    if search_lower in row.key.lower()
                    or search_lower in row.description.lower()
                    or search_lower in row.category.lower()
                )
                non_matching_rows = total_rows - matching_rows

                # Reset grid_remove call tracking on all rows
                for row in panel._setting_rows:
                    row.grid_remove = MagicMock()

                # Call filter_settings
                panel.filter_settings(search_term)

                # Count how many rows had grid_remove called
                grid_remove_count = sum(
                    1 for row in panel._setting_rows if row.grid_remove.called
                )

            # EXPECTED BEHAVIOR: only non-matching rows get grid_remove(),
            # not ALL rows. The fix should only remove rows that need hiding.
            # On unfixed code, ALL 119 rows are grid_removed then matching ones re-gridded.
            assert grid_remove_count <= non_matching_rows, (
                f"filter_settings('{search_term}') called grid_remove() on {grid_remove_count} rows, "
                f"but only {non_matching_rows} rows needed hiding (total: {total_rows}, matching: {matching_rows}). "
                f"Bug: grid_remove() called on ALL {total_rows} rows including matching ones, "
                f"instead of only removing rows that change from visible to hidden."
            )

    # -------------------------------------------------------------------------
    # Test 3: _regrid_all() — grid operations must be O(visible) not O(total)
    # Bug: performs 119×2 grid operations (remove + add) per invocation
    # -------------------------------------------------------------------------

    @given(visible_count=st.integers(min_value=1, max_value=VIEWPORT_CAPACITY))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_regrid_all_operations_are_bounded(self, visible_count: int) -> None:
        """_regrid_all() must perform at most O(visible) grid operations, not O(total).

        Bug (unfixed): _regrid_all() calls grid_remove() on ALL 119 rows then
        grid() on ALL rows, performing 119×2 grid operations regardless of how
        many rows are actually visible. The fix should only grid visible rows.

        **Validates: Requirements 2.2, 2.3**
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

                panel = _create_panel_with_rows(settings_file)

                # Build all rows
                panel.refresh()
                total_rows = len(panel._setting_rows)

                # Reset call counts on grid_remove and grid for each row
                for row in panel._setting_rows:
                    row.grid_remove = MagicMock()
                    row.grid = MagicMock()
                for header in panel._category_headers:
                    header.grid_remove = MagicMock()
                    header.grid = MagicMock()

                # Call _regrid_all — this should NOT touch all rows
                panel._regrid_all()

                # Count total grid operations on rows
                grid_remove_count = sum(
                    1 for row in panel._setting_rows if row.grid_remove.called
                )
                grid_add_count = sum(
                    1 for row in panel._setting_rows if row.grid.called
                )
                total_grid_ops = grid_remove_count + grid_add_count

            # EXPECTED BEHAVIOR: grid operations bounded by VIEWPORT_CAPACITY, not total
            max_acceptable_ops = (VIEWPORT_CAPACITY + 5) * 2  # viewport + buffer, remove + add
            assert total_grid_ops <= max_acceptable_ops, (
                f"_regrid_all() performed {total_grid_ops} grid operations "
                f"(grid_remove: {grid_remove_count}, grid: {grid_add_count}) on {total_rows} total rows. "
                f"Bug: performs O(total={total_rows}) ops instead of O(visible<={VIEWPORT_CAPACITY}) ops. "
                f"Max acceptable: {max_acceptable_ops}."
            )

    # -------------------------------------------------------------------------
    # Test 4: Concurrent refresh() — second call must be rejected
    # Bug: both calls execute fully, doubling widget creation cost
    # -------------------------------------------------------------------------

    @given(call_count=st.integers(min_value=2, max_value=5))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_concurrent_refresh_is_rejected(self, call_count: int) -> None:
        """Second concurrent refresh() call must be rejected without executing.

        Bug (unfixed): There is no refresh guard. Multiple concurrent refresh()
        calls all execute fully, each destroying and recreating all ~1,500 widgets.
        The fix should add a _refresh_in_progress flag.

        **Validates: Requirements 2.5**
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

                panel = _create_panel_with_rows(settings_file)

                # Initial refresh to build rows
                panel.refresh()

                # Track how many times SettingsParser.read_settings is called
                with patch("src.settings_panel.SettingsParser.read_settings") as mock_read:
                    mock_read.return_value = _build_mock_settings()

                    # Simulate rapid consecutive refresh calls
                    for _ in range(call_count):
                        panel.refresh()

                    actual_read_calls = mock_read.call_count

            # EXPECTED BEHAVIOR: Only ONE refresh executes, subsequent calls are rejected
            assert actual_read_calls == 1, (
                f"Called refresh() {call_count} times, but read_settings was invoked "
                f"{actual_read_calls} times. Bug: no refresh guard — all {call_count} calls "
                f"execute fully instead of rejecting concurrent calls."
            )

    # -------------------------------------------------------------------------
    # Test 5: Search debounce — filter_settings() called only once after
    # rapid keystrokes
    # Bug: called on every keystroke with no debounce
    # -------------------------------------------------------------------------

    @given(search_text=st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=3,
        max_size=10,
    ))
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_search_debounce_calls_filter_once(self, search_text: str) -> None:
        """filter_settings() must be called only once after rapid keystrokes (debounced).

        Bug (unfixed): _on_search_changed() calls filter_settings() synchronously
        on every keystroke via a StringVar trace. Typing "server" triggers 6 full
        filter passes. The fix should debounce by 150ms.

        **Validates: Requirements 2.3**
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
                mock_var.trace_add = MagicMock()
                mock_var.set = MagicMock()
                mock_sv.return_value = mock_var

                panel = _create_panel_with_rows(settings_file)

                # Build rows first
                panel.refresh()

                # Simulate rapid keystrokes
                with patch.object(panel, "filter_settings") as mock_filter:
                    for i in range(1, len(search_text) + 1):
                        mock_var.get.return_value = search_text[:i]
                        panel._on_search_changed()

                    filter_call_count = mock_filter.call_count

            # EXPECTED BEHAVIOR: filter_settings called only once (after debounce)
            assert filter_call_count <= 1, (
                f"Typed {len(search_text)} characters ('{search_text}'), "
                f"filter_settings() was called {filter_call_count} times. "
                f"Bug: no search debounce — filter is called on every keystroke "
                f"instead of once after 150ms of keyboard silence."
            )
