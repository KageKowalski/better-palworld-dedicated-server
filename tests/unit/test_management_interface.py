"""Unit tests for ManagementInterface error messages and auto-correction feedback.

Covers:
- Type validation failure messages (Req 3.4)
- Out-of-range numeric error messages (Req 3.6, 3.8)
- Invalid enum error messages (Req 3.9)
- Non-boolean error messages (Req 3.4 for booleans)
- Auto-correction success feedback (Req 3.12)
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config import WrapperConfig
from src.management_interface import CorrectionResult, ManagementInterface
from src.models import ServerState, ValidationResult, WrapperStatus
from src.settings_parser import SETTING_DEFINITIONS, SettingDefinition


@pytest.fixture
def mock_wrapper_core():
    """Create a mock WrapperCore."""
    core = MagicMock()
    core.get_status.return_value = WrapperStatus(
        server_state=ServerState.MONITORING,
        player_count=0,
        idle_timer_active=False,
        idle_seconds=0,
        server_pid=None,
        uptime_seconds=None,
    )
    return core


@pytest.fixture
def config(tmp_path):
    """Create a WrapperConfig with a temporary settings file path."""
    return WrapperConfig(
        server_exe_path=tmp_path / "PalServer.exe",
        settings_file_path=tmp_path / "PalWorldSettings.ini",
        idle_timeout_seconds=300,
    )


@pytest.fixture
def interface(mock_wrapper_core, config):
    """Create a ManagementInterface instance."""
    return ManagementInterface(mock_wrapper_core, config)


class TestTypeValidationErrors:
    """Tests for error messages on type validation failures (Req 3.4)."""

    def test_integer_type_error_names_expected_type(self, interface):
        """Error message for non-integer input should say 'must be an integer'."""
        result = interface._validate_and_correct(
            "ServerPlayerMaxNum", "abc", SETTING_DEFINITIONS["ServerPlayerMaxNum"]
        )
        assert isinstance(result, str)
        assert "must be an integer" in result
        assert "abc" in result

    def test_float_type_error_names_expected_type(self, interface):
        """Error message for non-float input should say 'must be a float'."""
        result = interface._validate_and_correct(
            "DayTimeSpeedRate", "not_a_number", SETTING_DEFINITIONS["DayTimeSpeedRate"]
        )
        assert isinstance(result, str)
        assert "must be a float" in result
        assert "not_a_number" in result

    def test_boolean_type_error_indicates_true_false(self, interface):
        """Error message for non-boolean should indicate True/False is expected."""
        result = interface._validate_and_correct(
            "bEnablePlayerToPlayerDamage",
            "yes",
            SETTING_DEFINITIONS["bEnablePlayerToPlayerDamage"],
        )
        assert isinstance(result, str)
        assert "must be a boolean" in result
        assert "True/False" in result
        assert "yes" in result


class TestOutOfRangeErrors:
    """Tests for out-of-range numeric error messages (Req 3.6, 3.8)."""

    def test_integer_below_min_shows_range(self, interface):
        """Error for below-minimum integer should display min and max."""
        result = interface._validate_and_correct(
            "ServerPlayerMaxNum", "0", SETTING_DEFINITIONS["ServerPlayerMaxNum"]
        )
        assert isinstance(result, str)
        assert "out of range" in result
        assert "1" in result  # min_value
        assert "32" in result  # max_value

    def test_integer_above_max_shows_range(self, interface):
        """Error for above-maximum integer should display min and max."""
        result = interface._validate_and_correct(
            "ServerPlayerMaxNum", "100", SETTING_DEFINITIONS["ServerPlayerMaxNum"]
        )
        assert isinstance(result, str)
        assert "out of range" in result
        assert "1" in result  # min_value
        assert "32" in result  # max_value

    def test_float_below_min_shows_range(self, interface):
        """Error for below-minimum float should display min and max."""
        result = interface._validate_and_correct(
            "DayTimeSpeedRate", "0.01", SETTING_DEFINITIONS["DayTimeSpeedRate"]
        )
        assert isinstance(result, str)
        assert "out of range" in result
        assert "0.1" in result  # min_value
        assert "5.0" in result  # max_value

    def test_float_above_max_shows_range(self, interface):
        """Error for above-maximum float should display min and max."""
        result = interface._validate_and_correct(
            "DayTimeSpeedRate", "10.0", SETTING_DEFINITIONS["DayTimeSpeedRate"]
        )
        assert isinstance(result, str)
        assert "out of range" in result
        assert "0.1" in result  # min_value
        assert "5.0" in result  # max_value


class TestInvalidEnumErrors:
    """Tests for invalid enum error messages (Req 3.9)."""

    def test_invalid_enum_lists_all_allowed_values(self, interface):
        """Error for invalid enum should display the complete list of allowed values."""
        result = interface._validate_and_correct(
            "DeathPenalty", "Invalid", SETTING_DEFINITIONS["DeathPenalty"]
        )
        assert isinstance(result, str)
        assert "not valid" in result
        # Verify all allowed values are present
        for val in SETTING_DEFINITIONS["DeathPenalty"].allowed_values:
            assert val in result

    def test_invalid_difficulty_lists_all_values(self, interface):
        """Error for invalid Difficulty should show all allowed values."""
        result = interface._validate_and_correct(
            "Difficulty", "Easy", SETTING_DEFINITIONS["Difficulty"]
        )
        assert isinstance(result, str)
        for val in SETTING_DEFINITIONS["Difficulty"].allowed_values:
            assert val in result


class TestAutoCorrectionFeedback:
    """Tests for auto-correction success message containing both original and corrected (Req 3.12)."""

    @pytest.fixture
    def settings_file(self, tmp_path):
        """Create a valid PalWorldSettings.ini file for testing."""
        content = (
            "[/Script/Pal.PalGameWorldSettings]\n"
            'OptionSettings=(ServerName="TestServer",bEnablePlayerToPlayerDamage=False,'
            'DayTimeSpeedRate=1.000000,ServerPlayerMaxNum=16)\n'
        )
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text(content, encoding="utf-8")
        return ini_file

    async def test_boolean_correction_shows_original_and_corrected(
        self, interface, config, settings_file, capsys
    ):
        """Auto-correction message should contain both original input and corrected value."""
        config.settings_file_path = settings_file
        await interface._cmd_set(["set", "bEnablePlayerToPlayerDamage", "true"])
        captured = capsys.readouterr()
        # Should show the corrected value 'True' and original 'true'
        assert "True" in captured.out
        assert "true" in captured.out
        assert "auto-corrected" in captured.out

    async def test_float_correction_shows_original_and_corrected(
        self, interface, config, settings_file, capsys
    ):
        """Float formatting correction should show both original and corrected values."""
        config.settings_file_path = settings_file
        await interface._cmd_set(["set", "DayTimeSpeedRate", "2.5"])
        captured = capsys.readouterr()
        # Should show auto-corrected from '2.5' since the formatted version differs
        assert "auto-corrected" in captured.out
        assert "2.5" in captured.out  # Original

    async def test_string_quote_stripping_shows_original_and_corrected(
        self, interface, config, settings_file, capsys
    ):
        """String quote stripping should show both original (quoted) and corrected (inner) values."""
        config.settings_file_path = settings_file
        await interface._cmd_set(["set", "ServerName", '"MyServer"'])
        captured = capsys.readouterr()
        # Should show auto-corrected from '"MyServer"' to 'MyServer'
        assert "auto-corrected" in captured.out
        assert "MyServer" in captured.out

    async def test_no_correction_no_auto_corrected_message(
        self, interface, config, settings_file, capsys
    ):
        """When no correction is needed, the message should NOT say 'auto-corrected'."""
        config.settings_file_path = settings_file
        await interface._cmd_set(["set", "bEnablePlayerToPlayerDamage", "True"])
        captured = capsys.readouterr()
        assert "auto-corrected" not in captured.out
        assert "updated" in captured.out


class TestCorrectionResultDataclass:
    """Tests for the CorrectionResult helper data structure."""

    def test_boolean_true_normalization_tracks_correction(self, interface):
        """Boolean 'TRUE' should be corrected to 'True' with was_corrected=True."""
        result = interface._correct_boolean("bIsPvP", "TRUE")
        assert isinstance(result, CorrectionResult)
        assert result.value == "True"
        assert result.was_corrected is True
        assert result.original_input == "TRUE"

    def test_boolean_already_canonical_no_correction(self, interface):
        """Boolean 'True' should not be flagged as corrected."""
        result = interface._correct_boolean("bIsPvP", "True")
        assert isinstance(result, CorrectionResult)
        assert result.value == "True"
        assert result.was_corrected is False

    def test_string_unquoted_no_correction(self, interface):
        """Unquoted string should not be flagged as corrected (parser adds quotes on write)."""
        result = interface._correct_string("MyServer")
        assert isinstance(result, CorrectionResult)
        assert result.value == "MyServer"
        assert result.was_corrected is False

    def test_string_quoted_is_correction(self, interface):
        """Quoted string should be stripped and flagged as corrected."""
        result = interface._correct_string('"MyServer"')
        assert isinstance(result, CorrectionResult)
        assert result.value == "MyServer"
        assert result.was_corrected is True
        assert result.original_input == '"MyServer"'
