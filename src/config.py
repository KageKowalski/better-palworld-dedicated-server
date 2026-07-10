"""Configuration data model for the Palworld Server Wrapper."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WrapperConfig:
    """Configuration for the Palworld Server Wrapper.

    Holds all configurable parameters for server paths, network ports,
    timing thresholds, and logging settings.
    """

    # Server paths
    server_exe_path: Path  # Path to PalServer.exe
    settings_file_path: Path  # Path to PalWorldSettings.ini

    # Network
    game_port: int = 8211  # UDP port for game connections
    rcon_port: int = 25575  # TCP port for RCON
    rcon_password: str = ""  # RCON admin password

    # Timing
    idle_timeout_seconds: int = 300  # Seconds before idle shutdown
    start_timeout_seconds: int = 120  # Max wait for server startup
    stop_timeout_seconds: int = 30  # Max wait for graceful shutdown
    rcon_poll_interval_seconds: int = 10  # Seconds between RCON queries

    # Logging
    log_file_path: Path = field(default_factory=lambda: Path("wrapper.log"))
    log_max_size_mb: int = 10
    log_backup_count: int = 3

    # Maintenance
    maintenance_interval_seconds: int = 21600  # 6 hours (range: 3600–86400)
    maintenance_broadcast_lead_seconds: int = 300  # 5 minutes (range: 30–1800)
    steamcmd_path: str = ""  # Path to steamcmd.exe
    steam_app_install_dir: str = ""  # Palworld Dedicated Server install dir

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If any configuration value is outside its valid range
                or has an incorrect type.
        """
        if self.rcon_poll_interval_seconds < 1 or self.rcon_poll_interval_seconds > 30:
            raise ValueError(
                f"rcon_poll_interval_seconds must be between 1 and 30, "
                f"got {self.rcon_poll_interval_seconds}"
            )

        if not isinstance(self.maintenance_interval_seconds, int):
            raise ValueError(
                f"maintenance_interval_seconds must be an integer, "
                f"got {type(self.maintenance_interval_seconds).__name__}"
            )

        if self.maintenance_interval_seconds < 3600 or self.maintenance_interval_seconds > 86400:
            raise ValueError(
                f"maintenance_interval_seconds must be between 3600 and 86400, "
                f"got {self.maintenance_interval_seconds}"
            )

        if not isinstance(self.maintenance_broadcast_lead_seconds, int):
            raise ValueError(
                f"maintenance_broadcast_lead_seconds must be an integer, "
                f"got {type(self.maintenance_broadcast_lead_seconds).__name__}"
            )

        if (
            self.maintenance_broadcast_lead_seconds < 30
            or self.maintenance_broadcast_lead_seconds > 1800
        ):
            raise ValueError(
                f"maintenance_broadcast_lead_seconds must be between 30 and 1800, "
                f"got {self.maintenance_broadcast_lead_seconds}"
            )

        if self.maintenance_broadcast_lead_seconds >= self.maintenance_interval_seconds:
            raise ValueError(
                f"maintenance_broadcast_lead_seconds ({self.maintenance_broadcast_lead_seconds}) "
                f"must be less than maintenance_interval_seconds "
                f"({self.maintenance_interval_seconds})"
            )
