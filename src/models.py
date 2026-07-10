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
class RconQueryResult:
    """Result of an RCON player count query."""

    success: bool
    player_count: int = 0
    error_message: str | None = None


@dataclass
class ValidationResult:
    """Result of a setting value validation check."""

    valid: bool
    error_message: str | None = None


@dataclass
class StateTransitionEvent:
    """Records a state transition for logging and auditing."""

    timestamp: datetime
    from_state: ServerState
    to_state: ServerState
    reason: str
