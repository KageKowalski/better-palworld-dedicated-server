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

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If rcon_poll_interval_seconds is outside the 1-30 range.
        """
        if self.rcon_poll_interval_seconds < 1 or self.rcon_poll_interval_seconds > 30:
            raise ValueError(
                f"rcon_poll_interval_seconds must be between 1 and 30, "
                f"got {self.rcon_poll_interval_seconds}"
            )
