"""State and status data models for the Palworld Server Wrapper."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class ServerState(Enum):
    """Represents the current state of the server wrapper state machine."""

    MONITORING = "monitoring"  # Server stopped, listening for connections
    STARTING = "starting"  # Server process launched, waiting for ready
    RUNNING = "running"  # Server active, monitoring players
    STOPPING = "stopping"  # Graceful shutdown in progress


@dataclass
class WrapperStatus:
    """Snapshot of the wrapper's current operational status."""

    server_state: ServerState
    player_count: int
    idle_timer_active: bool
    idle_seconds: int
    server_pid: int | None
    uptime_seconds: int | None


@dataclass
class StartResult:
    """Result of a server start attempt."""

    success: bool
    error_message: str | None = None


@dataclass
class StopResult:
    """Result of a server stop attempt."""

    success: bool
    was_forced: bool = False
    error_message: str | None = None


@dataclass
class RestartResult:
    """Result of a server restart attempt."""

    success: bool
    error_message: str | None = None


@dataclass
class ValidationResult:
    """Result of a setting value validation check."""

    valid: bool
    error_message: str | None = None


@dataclass
class UpdateResult:
    """Result of a SteamCMD update attempt."""

    success: bool
    skipped: bool = False
    error_message: str | None = None
    timed_out: bool = False


@dataclass
class MaintenanceCycleResult:
    """Result of a complete maintenance cycle."""

    success: bool
    update_result: UpdateResult | None = None
    duration_seconds: float = 0.0
    error_message: str | None = None


@dataclass
class StateTransitionEvent:
    """Records a state transition for logging and auditing."""

    timestamp: datetime
    from_state: ServerState
    to_state: ServerState
    reason: str


@dataclass
class MetricsResult:
    """Result of a REST API metrics query."""

    success: bool
    player_count: int = 0
    error_message: str | None = None


@dataclass
class InfoResult:
    """Result of a REST API info query (connectivity check)."""

    success: bool
    version: str = ""
    server_name: str = ""
    description: str = ""
    error_message: str | None = None


@dataclass
class PlayerInfo:
    """A single player's information from the REST API."""

    name: str = ""
    playerid: str = ""
    userid: str = ""
    ip: str = ""
    ping: float = 0.0
    location_x: float = 0.0
    location_y: float = 0.0
    level: int = 0


@dataclass
class PlayersResult:
    """Result of a REST API players query."""

    success: bool
    players: list[PlayerInfo] = field(default_factory=list)
    error_message: str | None = None


@dataclass
class AnnounceResult:
    """Result of a REST API announce (broadcast) request."""

    success: bool
    error_message: str | None = None


@dataclass
class ShutdownResult:
    """Result of a REST API shutdown request."""

    success: bool
    error_message: str | None = None
