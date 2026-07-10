"""Unit tests for the settings parser module."""

import pytest
from pathlib import Path
from src.settings_parser import SettingDefinition, SettingsParser, SETTING_DEFINITIONS


# Sample PalWorldSettings.ini content for testing
SAMPLE_INI_CONTENT = """\
[/Script/Pal.PalGameWorldSettings]
OptionSettings=(Difficulty=None,DayTimeSpeedRate=1.000000,NightTimeSpeedRate=1.000000,ExpRate=1.000000,PalCaptureRate=1.000000,PalSpawnNumRate=1.000000,PalDamageRateAttack=1.000000,PalDamageRateDefense=1.000000,PlayerDamageRateAttack=1.000000,PlayerDamageRateDefense=1.000000,PlayerStomachDecreaceRate=1.000000,PlayerStaminaDecreaceRate=1.000000,PlayerAutoHPRegeneRate=1.000000,PlayerAutoHpRegeneRateInSleep=1.000000,PalStomachDecreaceRate=1.000000,PalStaminaDecreaceRate=1.000000,PalAutoHPRegeneRate=1.000000,PalAutoHpRegeneRateInSleep=1.000000,BuildObjectDamageRate=1.000000,BuildObjectDeteriorationDamageRate=1.000000,CollectionDropRate=1.000000,CollectionObjectHpRate=1.000000,CollectionObjectRespawnSpeedRate=1.000000,EnemyDropItemRate=1.000000,DeathPenalty=All,bEnablePlayerToPlayerDamage=False,bEnableFriendlyFire=False,bEnableInvaderEnemy=True,bActiveUNKO=False,bIsPvP=False,bCanPickupOtherGuildDeathPenaltyDrop=False,ServerPlayerMaxNum=32,GuildPlayerMaxNum=20,PalEggDefaultHatchingTime=72.000000,WorkSpeedRate=1.000000,ServerName=Default Palworld Server,ServerDescription=,AdminPassword=,ServerPassword=,PublicPort=8211,RCONPort=25575,bIsUseBackupSaveData=True)
"""


class TestReadSettings:
    """Tests for SettingsParser.read_settings()."""

    def test_read_valid_settings(self, tmp_path: Path):
        """Read settings from a well-formed INI file."""
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text(SAMPLE_INI_CONTENT, encoding="utf-8")

        settings = SettingsParser.read_settings(ini_file)

        assert "__error__" not in settings
        assert settings["Difficulty"] == "None"
        assert settings["DayTimeSpeedRate"] == 1.0
        assert settings["NightTimeSpeedRate"] == 1.0
        assert settings["ExpRate"] == 1.0
        assert settings["ServerPlayerMaxNum"] == 32
        assert settings["bEnableInvaderEnemy"] is True
        assert settings["bIsPvP"] is False
        assert settings["DeathPenalty"] == "All"
        assert settings["ServerName"] == "Default Palworld Server"

    def test_read_file_not_found(self, tmp_path: Path):
        """Return error when file does not exist."""
        ini_file = tmp_path / "nonexistent.ini"

        settings = SettingsParser.read_settings(ini_file)

        assert "__error__" in settings
        assert "not found" in settings["__error__"].lower()

    def test_read_malformed_no_option_settings(self, tmp_path: Path):
        """Return error when file has no OptionSettings line."""
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text("[SomeSection]\nFoo=Bar\n", encoding="utf-8")

        settings = SettingsParser.read_settings(ini_file)

        assert "__error__" in settings
        assert "malformed" in settings["__error__"].lower()

    def test_read_malformed_no_parentheses(self, tmp_path: Path):
        """Return error when OptionSettings is not wrapped in parentheses."""
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text(
            "[/Script/Pal.PalGameWorldSettings]\nOptionSettings=NoParens\n",
            encoding="utf-8",
        )

        settings = SettingsParser.read_settings(ini_file)

        assert "__error__" in settings
        assert "parentheses" in settings["__error__"].lower()

    def test_read_empty_option_settings(self, tmp_path: Path):
        """Return empty dict when OptionSettings has no pairs."""
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text(
            "[/Script/Pal.PalGameWorldSettings]\nOptionSettings=()\n",
            encoding="utf-8",
        )

        settings = SettingsParser.read_settings(ini_file)

        assert "__error__" not in settings
        assert settings == {}


class TestWriteSetting:
    """Tests for SettingsParser.write_setting()."""

    def test_write_float_setting(self, tmp_path: Path):
        """Write a float setting and verify it's changed."""
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text(SAMPLE_INI_CONTENT, encoding="utf-8")

        result = SettingsParser.write_setting(ini_file, "DayTimeSpeedRate", 2.5)

        assert result.valid is True
        # Verify the change
        settings = SettingsParser.read_settings(ini_file)
        assert settings["DayTimeSpeedRate"] == 2.5

    def test_write_preserves_other_settings(self, tmp_path: Path):
        """Writing one setting preserves all others."""
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text(SAMPLE_INI_CONTENT, encoding="utf-8")

        original = SettingsParser.read_settings(ini_file)
        SettingsParser.write_setting(ini_file, "ExpRate", 5.0)
        modified = SettingsParser.read_settings(ini_file)

        # Only ExpRate should change
        for key, val in original.items():
            if key == "ExpRate":
                assert modified[key] == 5.0
            else:
                assert modified[key] == val, f"Setting '{key}' was unexpectedly modified"

    def test_write_int_setting(self, tmp_path: Path):
        """Write an integer setting."""
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text(SAMPLE_INI_CONTENT, encoding="utf-8")

        result = SettingsParser.write_setting(ini_file, "ServerPlayerMaxNum", 16)

        assert result.valid is True
        settings = SettingsParser.read_settings(ini_file)
        assert settings["ServerPlayerMaxNum"] == 16

    def test_write_bool_setting(self, tmp_path: Path):
        """Write a boolean setting."""
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text(SAMPLE_INI_CONTENT, encoding="utf-8")

        result = SettingsParser.write_setting(ini_file, "bIsPvP", True)

        assert result.valid is True
        settings = SettingsParser.read_settings(ini_file)
        assert settings["bIsPvP"] is True

    def test_write_invalid_value_rejected(self, tmp_path: Path):
        """Reject writing an out-of-range value."""
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text(SAMPLE_INI_CONTENT, encoding="utf-8")

        result = SettingsParser.write_setting(ini_file, "DayTimeSpeedRate", 99.0)

        assert result.valid is False
        assert "maximum" in result.error_message.lower()
        # File should be unchanged
        settings = SettingsParser.read_settings(ini_file)
        assert settings["DayTimeSpeedRate"] == 1.0

    def test_write_file_not_found(self, tmp_path: Path):
        """Return error when file does not exist."""
        ini_file = tmp_path / "nonexistent.ini"

        result = SettingsParser.write_setting(ini_file, "ExpRate", 2.0)

        assert result.valid is False
        assert "not found" in result.error_message.lower()

    def test_write_nonexistent_key(self, tmp_path: Path):
        """Return error when key doesn't exist in the file."""
        ini_file = tmp_path / "PalWorldSettings.ini"
        ini_file.write_text(SAMPLE_INI_CONTENT, encoding="utf-8")

        result = SettingsParser.write_setting(ini_file, "NonexistentKey", "value")

        assert result.valid is False
        assert "could not find" in result.error_message.lower()


class TestValidateSetting:
    """Tests for SettingsParser.validate_setting()."""

    def test_valid_float_in_range(self):
        """Accept a float value within range."""
        result = SettingsParser.validate_setting("DayTimeSpeedRate", 2.5)
        assert result.valid is True

    def test_float_below_minimum(self):
        """Reject a float value below minimum."""
        result = SettingsParser.validate_setting("DayTimeSpeedRate", 0.01)
        assert result.valid is False
        assert "below" in result.error_message.lower()

    def test_float_above_maximum(self):
        """Reject a float value above maximum."""
        result = SettingsParser.validate_setting("ExpRate", 25.0)
        assert result.valid is False
        assert "above" in result.error_message.lower()

    def test_valid_int_in_range(self):
        """Accept an integer value within range."""
        result = SettingsParser.validate_setting("ServerPlayerMaxNum", 16)
        assert result.valid is True

    def test_int_below_minimum(self):
        """Reject an integer below minimum."""
        result = SettingsParser.validate_setting("ServerPlayerMaxNum", 0)
        assert result.valid is False

    def test_int_above_maximum(self):
        """Reject an integer above maximum."""
        result = SettingsParser.validate_setting("ServerPlayerMaxNum", 100)
        assert result.valid is False

    def test_valid_bool(self):
        """Accept a boolean value."""
        result = SettingsParser.validate_setting("bIsPvP", True)
        assert result.valid is True

    def test_valid_allowed_value(self):
        """Accept a value in allowed_values list."""
        result = SettingsParser.validate_setting("DeathPenalty", "All")
        assert result.valid is True

    def test_invalid_allowed_value(self):
        """Reject a value not in allowed_values list."""
        result = SettingsParser.validate_setting("DeathPenalty", "InvalidOption")
        assert result.valid is False
        assert "allowed values" in result.error_message.lower()

    def test_unknown_setting_accepted(self):
        """Unknown settings are accepted without validation."""
        result = SettingsParser.validate_setting("CustomSetting", "anything")
        assert result.valid is True

    def test_invalid_type_for_float(self):
        """Reject a non-numeric value for a float setting."""
        result = SettingsParser.validate_setting("DayTimeSpeedRate", "not_a_number")
        assert result.valid is False
        assert "float" in result.error_message.lower()

    def test_invalid_type_for_int(self):
        """Reject a non-integer value for an int setting."""
        result = SettingsParser.validate_setting("ServerPlayerMaxNum", "abc")
        assert result.valid is False
        assert "integer" in result.error_message.lower()


class TestGetSettingDefinitions:
    """Tests for SettingsParser.get_setting_definitions()."""

    def test_returns_definitions(self):
        """Returns non-empty dict of definitions."""
        defs = SettingsParser.get_setting_definitions()
        assert len(defs) > 0
        assert "DayTimeSpeedRate" in defs
        assert "ExpRate" in defs

    def test_definitions_have_correct_types(self):
        """Each definition has appropriate type info."""
        defs = SettingsParser.get_setting_definitions()
        assert defs["DayTimeSpeedRate"].value_type == float
        assert defs["ServerPlayerMaxNum"].value_type == int
        assert defs["bIsPvP"].value_type == bool
        assert defs["DeathPenalty"].value_type == str

    def test_returns_copy(self):
        """Returns a copy, not the original dict."""
        defs1 = SettingsParser.get_setting_definitions()
        defs2 = SettingsParser.get_setting_definitions()
        defs1["test"] = None
        assert "test" not in defs2
