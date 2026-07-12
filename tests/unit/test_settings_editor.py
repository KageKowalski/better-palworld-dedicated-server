"""Unit tests for SettingsEditor widget class (mock-based, no display required).

Tests the _on_submit() logic and input length limiting using mocked tkinter
internals so they can run in headless CI environments.

Covers:
- Key input limited to 128 chars (Req 6.1)
- Value input limited to 1024 chars (Req 6.1)
- Validates using validate_and_correct() (Req 6.2)
- Displays auto-correction feedback (Req 6.3)
- Displays validation error messages without writing (Req 6.4)
- On success: shows confirmation and refreshes SettingsView (Req 6.5, 6.7)
- Warns if server is RUNNING (Req 6.6)
- Unknown keys written as raw string (Req 6.9)
- File system errors handled gracefully (Req 6.8)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import WrapperConfig
from src.models import ServerState, ValidationResult, WrapperStatus
from src.validation import CorrectionResult


@pytest.fixture
def tmp_config(tmp_path):
    """Create a WrapperConfig with temporary paths."""
    return WrapperConfig(
        server_exe_path=tmp_path / "PalServer.exe",
        settings_file_path=tmp_path / "PalWorldSettings.ini",
    )


@pytest.fixture
def mock_wrapper_core():
    """Create a mock WrapperCore with get_status returning MONITORING."""
    core = MagicMock()
    core.get_status = MagicMock(return_value=WrapperStatus(
        server_state=ServerState.MONITORING,
        player_count=0,
        idle_timer_active=False,
        idle_seconds=0,
        server_pid=None,
        uptime_seconds=None,
    ))
    return core


@pytest.fixture
def settings_editor(tmp_config, mock_wrapper_core):
    """Create a SettingsEditor with mocked tkinter internals (no display needed)."""
    from src.gui_interface import SettingsEditor

    with patch.object(SettingsEditor, "__init__", lambda self, *a, **kw: None):
        editor = SettingsEditor.__new__(SettingsEditor)
        # Set up the internal state that __init__ would create
        editor._config = tmp_config
        editor._wrapper_core = mock_wrapper_core
        editor._on_setting_changed = MagicMock()
        editor._settings_write_handler = None
        editor._key_var = MagicMock()
        editor._value_var = MagicMock()
        editor._feedback_label = MagicMock()
        editor._apply_button = MagicMock()
        return editor


class TestSettingsEditorSubmit:
    """Tests for SettingsEditor._on_submit() method logic."""

    def test_empty_key_shows_error(self, settings_editor):
        """Submitting with empty key should show error feedback."""
        settings_editor._key_var.get.return_value = ""
        settings_editor._value_var.get.return_value = "some_value"

        settings_editor._on_submit()

        settings_editor._feedback_label.configure.assert_called()
        call_kwargs = settings_editor._feedback_label.configure.call_args[1]
        assert "cannot be empty" in call_kwargs["text"]
        assert call_kwargs["foreground"] == "red"

    def test_whitespace_only_key_shows_error(self, settings_editor):
        """Submitting with whitespace-only key should show error."""
        settings_editor._key_var.get.return_value = "   "
        settings_editor._value_var.get.return_value = "value"

        settings_editor._on_submit()

        call_kwargs = settings_editor._feedback_label.configure.call_args[1]
        assert "cannot be empty" in call_kwargs["text"]
        assert call_kwargs["foreground"] == "red"

    @patch("src.gui_interface.validate_and_correct")
    def test_validation_error_displays_red_message(
        self, mock_validate, settings_editor
    ):
        """When validation returns error string, display it in red."""
        mock_validate.return_value = "Error: Setting 'Foo' must be an integer, got: 'abc'"
        settings_editor._key_var.get.return_value = "Foo"
        settings_editor._value_var.get.return_value = "abc"

        settings_editor._on_submit()

        call_kwargs = settings_editor._feedback_label.configure.call_args[1]
        assert "Error" in call_kwargs["text"]
        assert call_kwargs["foreground"] == "red"

    @patch("src.gui_interface.validate_and_correct")
    def test_validation_error_does_not_write_file(
        self, mock_validate, settings_editor
    ):
        """When validation fails, SettingsParser.write_setting should not be called."""
        mock_validate.return_value = "Error: invalid"
        settings_editor._key_var.get.return_value = "SomeKey"
        settings_editor._value_var.get.return_value = "bad"

        with patch("src.gui_interface.SettingsParser.write_setting") as mock_write:
            settings_editor._on_submit()
            mock_write.assert_not_called()

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_auto_correction_feedback_shown(
        self, mock_validate, mock_write, settings_editor
    ):
        """When auto-correction is applied, show original -> corrected message."""
        mock_validate.return_value = CorrectionResult(
            value="True", was_corrected=True, original_input="true"
        )
        mock_write.return_value = ValidationResult(valid=True)
        settings_editor._key_var.get.return_value = "bEnablePvP"
        settings_editor._value_var.get.return_value = "true"

        settings_editor._on_submit()

        # Check the last configure call has auto-correction info
        call_kwargs = settings_editor._feedback_label.configure.call_args[1]
        assert "Auto-corrected" in call_kwargs["text"]
        assert "'true'" in call_kwargs["text"]
        assert "'True'" in call_kwargs["text"]
        assert call_kwargs["foreground"] == "blue"

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_successful_write_shows_confirmation(
        self, mock_validate, mock_write, settings_editor
    ):
        """On successful write, show confirmation message in green."""
        mock_validate.return_value = CorrectionResult(
            value="2.0", was_corrected=False, original_input="2.0"
        )
        mock_write.return_value = ValidationResult(valid=True)
        settings_editor._key_var.get.return_value = "ExpRate"
        settings_editor._value_var.get.return_value = "2.0"

        settings_editor._on_submit()

        call_kwargs = settings_editor._feedback_label.configure.call_args[1]
        assert "successfully" in call_kwargs["text"]
        assert "ExpRate" in call_kwargs["text"]
        assert call_kwargs["foreground"] == "green"

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_successful_write_calls_on_setting_changed(
        self, mock_validate, mock_write, settings_editor
    ):
        """On successful write, the on_setting_changed callback should be called."""
        mock_validate.return_value = CorrectionResult(
            value="TestValue", was_corrected=False, original_input="TestValue"
        )
        mock_write.return_value = ValidationResult(valid=True)
        settings_editor._key_var.get.return_value = "UnknownKey"
        settings_editor._value_var.get.return_value = "TestValue"

        settings_editor._on_submit()

        settings_editor._on_setting_changed.assert_called_once_with()

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_running_server_shows_restart_warning(
        self, mock_validate, mock_write, settings_editor, mock_wrapper_core
    ):
        """When server is RUNNING, show restart warning after successful write."""
        mock_validate.return_value = CorrectionResult(
            value="1.5", was_corrected=False, original_input="1.5"
        )
        mock_write.return_value = ValidationResult(valid=True)
        mock_wrapper_core.get_status.return_value = WrapperStatus(
            server_state=ServerState.RUNNING,
            player_count=2,
            idle_timer_active=False,
            idle_seconds=0,
            server_pid=1234,
            uptime_seconds=100,
        )
        settings_editor._key_var.get.return_value = "ExpRate"
        settings_editor._value_var.get.return_value = "1.5"

        settings_editor._on_submit()

        call_kwargs = settings_editor._feedback_label.configure.call_args[1]
        assert "restart" in call_kwargs["text"].lower()
        assert "Warning" in call_kwargs["text"]

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_monitoring_server_no_restart_warning(
        self, mock_validate, mock_write, settings_editor
    ):
        """When server is MONITORING, no restart warning should appear."""
        mock_validate.return_value = CorrectionResult(
            value="1.5", was_corrected=False, original_input="1.5"
        )
        mock_write.return_value = ValidationResult(valid=True)
        settings_editor._key_var.get.return_value = "ExpRate"
        settings_editor._value_var.get.return_value = "1.5"

        settings_editor._on_submit()

        call_kwargs = settings_editor._feedback_label.configure.call_args[1]
        assert "restart" not in call_kwargs["text"].lower()

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_write_failure_shows_error(
        self, mock_validate, mock_write, settings_editor
    ):
        """When SettingsParser.write_setting returns invalid, show error."""
        mock_validate.return_value = CorrectionResult(
            value="test", was_corrected=False, original_input="test"
        )
        mock_write.return_value = ValidationResult(
            valid=False, error_message="File not found: /path/to/file"
        )
        settings_editor._key_var.get.return_value = "SomeKey"
        settings_editor._value_var.get.return_value = "test"

        settings_editor._on_submit()

        call_kwargs = settings_editor._feedback_label.configure.call_args[1]
        assert "Error" in call_kwargs["text"]
        assert "File not found" in call_kwargs["text"]
        assert call_kwargs["foreground"] == "red"

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_write_failure_does_not_call_callback(
        self, mock_validate, mock_write, settings_editor
    ):
        """When write fails, on_setting_changed callback should NOT be called."""
        mock_validate.return_value = CorrectionResult(
            value="test", was_corrected=False, original_input="test"
        )
        mock_write.return_value = ValidationResult(
            valid=False, error_message="Write error"
        )
        settings_editor._key_var.get.return_value = "SomeKey"
        settings_editor._value_var.get.return_value = "test"

        settings_editor._on_submit()

        settings_editor._on_setting_changed.assert_not_called()

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_filesystem_exception_handled_gracefully(
        self, mock_validate, mock_write, settings_editor
    ):
        """File system exceptions should be caught and shown as error."""
        mock_validate.return_value = CorrectionResult(
            value="test", was_corrected=False, original_input="test"
        )
        mock_write.side_effect = OSError("Permission denied")
        settings_editor._key_var.get.return_value = "SomeKey"
        settings_editor._value_var.get.return_value = "test"

        settings_editor._on_submit()

        call_kwargs = settings_editor._feedback_label.configure.call_args[1]
        assert "Error" in call_kwargs["text"]
        assert "Permission denied" in call_kwargs["text"]
        assert call_kwargs["foreground"] == "red"

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_unknown_key_writes_raw_string(
        self, mock_validate, mock_write, settings_editor
    ):
        """Unknown keys should be written as raw strings."""
        mock_validate.return_value = CorrectionResult(
            value="raw_string_value", was_corrected=False, original_input="raw_string_value"
        )
        mock_write.return_value = ValidationResult(valid=True)
        settings_editor._key_var.get.return_value = "UnknownCustomSetting"
        settings_editor._value_var.get.return_value = "raw_string_value"

        settings_editor._on_submit()

        mock_write.assert_called_once()
        call_args = mock_write.call_args[0]
        assert call_args[1] == "UnknownCustomSetting"
        assert call_args[2] == "raw_string_value"

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_write_setting_receives_config_path(
        self, mock_validate, mock_write, settings_editor, tmp_config
    ):
        """write_setting should be called with the configured settings_file_path."""
        mock_validate.return_value = CorrectionResult(
            value="val", was_corrected=False, original_input="val"
        )
        mock_write.return_value = ValidationResult(valid=True)
        settings_editor._key_var.get.return_value = "MyKey"
        settings_editor._value_var.get.return_value = "val"

        settings_editor._on_submit()

        call_args = mock_write.call_args[0]
        assert call_args[0] == tmp_config.settings_file_path

    @patch("src.gui_interface.SettingsParser.write_setting")
    @patch("src.gui_interface.validate_and_correct")
    def test_get_status_exception_skips_warning(
        self, mock_validate, mock_write, settings_editor, mock_wrapper_core
    ):
        """If get_status() raises, skip the restart warning gracefully."""
        mock_validate.return_value = CorrectionResult(
            value="val", was_corrected=False, original_input="val"
        )
        mock_write.return_value = ValidationResult(valid=True)
        mock_wrapper_core.get_status.side_effect = RuntimeError("no connection")
        settings_editor._key_var.get.return_value = "Key"
        settings_editor._value_var.get.return_value = "val"

        # Should not raise
        settings_editor._on_submit()

        # Callback should still be called (write was successful)
        settings_editor._on_setting_changed.assert_called_once_with()
        # Confirmation should still be shown (without warning)
        call_kwargs = settings_editor._feedback_label.configure.call_args[1]
        assert "successfully" in call_kwargs["text"]
        assert "restart" not in call_kwargs["text"].lower()


class TestSettingsEditorLengthLimits:
    """Tests for SettingsEditor input length limiting logic."""

    def test_limit_key_length_truncates_long_input(self, settings_editor):
        """_limit_key_length should truncate to MAX_KEY_LENGTH chars."""
        from src.gui_interface import SettingsEditor

        # Simulate a StringVar that returns a long value
        long_key = "A" * 200
        settings_editor._key_var.get.return_value = long_key

        settings_editor._limit_key_length()

        settings_editor._key_var.set.assert_called_once_with("A" * 128)

    def test_limit_key_length_no_truncation_for_short_input(self, settings_editor):
        """_limit_key_length should not modify input within limits."""
        short_key = "A" * 50
        settings_editor._key_var.get.return_value = short_key

        settings_editor._limit_key_length()

        settings_editor._key_var.set.assert_not_called()

    def test_limit_key_length_exact_boundary(self, settings_editor):
        """_limit_key_length should not truncate input at exactly MAX_KEY_LENGTH."""
        exact_key = "A" * 128
        settings_editor._key_var.get.return_value = exact_key

        settings_editor._limit_key_length()

        settings_editor._key_var.set.assert_not_called()

    def test_limit_value_length_truncates_long_input(self, settings_editor):
        """_limit_value_length should truncate to MAX_VALUE_LENGTH chars."""
        long_value = "B" * 2000
        settings_editor._value_var.get.return_value = long_value

        settings_editor._limit_value_length()

        settings_editor._value_var.set.assert_called_once_with("B" * 1024)

    def test_limit_value_length_no_truncation_for_short_input(self, settings_editor):
        """_limit_value_length should not modify input within limits."""
        short_value = "B" * 500
        settings_editor._value_var.get.return_value = short_value

        settings_editor._limit_value_length()

        settings_editor._value_var.set.assert_not_called()

    def test_limit_value_length_exact_boundary(self, settings_editor):
        """_limit_value_length should not truncate input at exactly MAX_VALUE_LENGTH."""
        exact_value = "B" * 1024
        settings_editor._value_var.get.return_value = exact_value

        settings_editor._limit_value_length()

        settings_editor._value_var.set.assert_not_called()
