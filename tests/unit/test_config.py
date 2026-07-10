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
        assert config.idle_timeout_seconds == 300

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

    def test_default_maintenance_interval_seconds(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.maintenance_interval_seconds == 21600

    def test_default_maintenance_broadcast_lead_seconds(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.maintenance_broadcast_lead_seconds == 300

    def test_default_steamcmd_path(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.steamcmd_path == ""

    def test_default_steam_app_install_dir(self):
        config = WrapperConfig(
            server_exe_path=Path("."), settings_file_path=Path(".")
        )
        assert config.steam_app_install_dir == ""


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


class TestMaintenanceIntervalValidation:
    """Test validation of maintenance_interval_seconds."""

    def test_valid_interval_lower_bound(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_interval_seconds=3600,
        )
        config.validate()  # Should not raise

    def test_valid_interval_upper_bound(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_interval_seconds=86400,
        )
        config.validate()  # Should not raise

    def test_valid_interval_mid_range(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_interval_seconds=21600,
        )
        config.validate()  # Should not raise

    def test_invalid_interval_below_range(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_interval_seconds=3599,
        )
        with pytest.raises(ValueError, match="maintenance_interval_seconds must be between 3600 and 86400"):
            config.validate()

    def test_invalid_interval_above_range(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_interval_seconds=86401,
        )
        with pytest.raises(ValueError, match="maintenance_interval_seconds must be between 3600 and 86400"):
            config.validate()

    def test_invalid_interval_not_integer(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
        )
        config.maintenance_interval_seconds = 21600.5  # type: ignore[assignment]
        with pytest.raises(ValueError, match="maintenance_interval_seconds must be an integer"):
            config.validate()


class TestMaintenanceBroadcastLeadValidation:
    """Test validation of maintenance_broadcast_lead_seconds."""

    def test_valid_lead_lower_bound(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_broadcast_lead_seconds=30,
        )
        config.validate()  # Should not raise

    def test_valid_lead_upper_bound(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_broadcast_lead_seconds=1800,
        )
        config.validate()  # Should not raise

    def test_valid_lead_mid_range(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_broadcast_lead_seconds=300,
        )
        config.validate()  # Should not raise

    def test_invalid_lead_below_range(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_broadcast_lead_seconds=29,
        )
        with pytest.raises(ValueError, match="maintenance_broadcast_lead_seconds must be between 30 and 1800"):
            config.validate()

    def test_invalid_lead_above_range(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_broadcast_lead_seconds=1801,
        )
        with pytest.raises(ValueError, match="maintenance_broadcast_lead_seconds must be between 30 and 1800"):
            config.validate()

    def test_invalid_lead_not_integer(self):
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
        )
        config.maintenance_broadcast_lead_seconds = 300.0  # type: ignore[assignment]
        with pytest.raises(ValueError, match="maintenance_broadcast_lead_seconds must be an integer"):
            config.validate()

    def test_valid_lead_at_maximum_with_minimum_interval(self):
        """Boundary: max broadcast lead (1800) with min interval (3600) is valid."""
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_interval_seconds=3600,
            maintenance_broadcast_lead_seconds=1800,
        )
        config.validate()  # Should not raise (1800 < 3600)

    def test_cross_validation_lead_equal_to_interval(self):
        """Cross-validation: broadcast_lead >= interval raises ValueError.

        With current ranges (lead max 1800, interval min 3600), this guard
        is unreachable via normal construction. We verify that when both are
        out of individual ranges, the first applicable check fires correctly.
        """
        config = WrapperConfig(
            server_exe_path=Path("."),
            settings_file_path=Path("."),
            maintenance_interval_seconds=100,
            maintenance_broadcast_lead_seconds=100,
        )
        # interval=100 fails range check first (< 3600)
        with pytest.raises(ValueError, match="maintenance_interval_seconds must be between 3600 and 86400"):
            config.validate()
