"""Unit tests for WrapperConfig data model."""

from pathlib import Path

import pytest

from src.config import WrapperConfig


class TestWrapperConfigDefaults:
    """Test that WrapperConfig has correct default values."""

    def test_required_fields(self):
        config = WrapperConfig(
            server_exe_path=Path("C:/PalServer/PalServer.exe"),
            settings_file_path=Path("C:/PalServer/PalWorldSettings.ini"),
        )
        assert config.server_exe_path == Path("C:/PalServer/PalServer.exe")
        assert config.settings_file_path == Path("C:/PalServer/PalWorldSettings.ini")

    def test_default_game_port(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.game_port == 8211

    def test_default_rcon_port(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.rcon_port == 25575

    def test_default_rcon_password(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.rcon_password == ""

    def test_default_idle_timeout(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.idle_timeout_seconds == 600

    def test_default_start_timeout(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.start_timeout_seconds == 120

    def test_default_stop_timeout(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.stop_timeout_seconds == 30

    def test_default_rcon_poll_interval(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.rcon_poll_interval_seconds == 10

    def test_default_log_file_path(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.log_file_path == Path("wrapper.log")

    def test_default_log_max_size(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.log_max_size_mb == 10

    def test_default_log_backup_count(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.log_backup_count == 3


class TestWrapperConfigValidation:
    """Test validation of rcon_poll_interval_seconds."""

    def test_valid_interval_lower_bound(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            rcon_poll_interval_seconds=1,
        )
        config.validate()  # Should not raise

    def test_valid_interval_upper_bound(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            rcon_poll_interval_seconds=30,
        )
        config.validate()  # Should not raise

    def test_valid_interval_mid_range(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            rcon_poll_interval_seconds=15,
        )
        config.validate()  # Should not raise

    def test_invalid_interval_below_range(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            rcon_poll_interval_seconds=0,
        )
        with pytest.raises(ValueError, match="rcon_poll_interval_seconds must be between 1 and 30"):
            config.validate()

    def test_invalid_interval_above_range(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            rcon_poll_interval_seconds=31,
        )
        with pytest.raises(ValueError, match="rcon_poll_interval_seconds must be between 1 and 30"):
            config.validate()

    def test_invalid_interval_negative(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            rcon_poll_interval_seconds=-5,
        )
        with pytest.raises(ValueError):
            config.validate()
