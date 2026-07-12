"""Wrapper Core - central state machine coordinator for the Palworld Server Wrapper.

Manages state transitions between MONITORING, STARTING, RUNNING, and STOPPING.
Orchestrates all components: ConnectionListener, ProcessManager, RconClient,
IdleTimer, WrapperLogger, and SettingsParser.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

from src.config import WrapperConfig
from src.connection_listener import ConnectionListener
from src.idle_timer import IdleTimer
from src.logger import WrapperLogger
from src.maintenance_timer import MaintenanceTimer
from src.models import (
    RestartResult,
    ServerState,
    StartResult,
    StateTransitionEvent,
    StopResult,
    WrapperStatus,
)
from src.pending_settings import ApplyResult, PendingSettingsQueue
from src.process_manager import ProcessManager
from src.rcon_client import RconClient
from src.settings_parser import SettingsParser
from src.steam_updater import SteamUpdater

logger = logging.getLogger(__name__)


class WrapperCore:
    """Central state machine coordinator for managing the Palworld Dedicated Server.

    Implements the state machine: MONITORING → STARTING → RUNNING → STOPPING → MONITORING.
    Coordinates all components and ensures safe transitions between states.
    """

    def __init__(self, config: WrapperConfig) -> None:
        """Initialize the wrapper core with all components.

        Args:
            config: The wrapper configuration containing paths, ports, and timing settings.
        """
        self._config = config
        self._state = ServerState.MONITORING
        self._player_count = 0
        self._running_since: float | None = None
        self._quit_event = asyncio.Event()
        self._rcon_poll_task: asyncio.Task | None = None
        self._consecutive_rcon_failures = 0

        # Initialize components
        self._logger = WrapperLogger()
        self._settings_parser = SettingsParser()
        self._process_manager = ProcessManager(on_crash=self.handle_server_crashed)
        self._rcon_client = RconClient(
            host="127.0.0.1",
            port=config.rcon_port,
            password=config.rcon_password,
        )
        self._idle_timer = IdleTimer(
            timeout_seconds=config.idle_timeout_seconds,
            on_expired=self.handle_idle_expired,
        )
        self._connection_listener = ConnectionListener(
            on_packet_received=self._on_udp_packet_received,
            port=config.game_port,
        )
        self._maintenance_timer = MaintenanceTimer(
            interval_seconds=config.maintenance_interval_seconds,
            broadcast_lead_seconds=config.maintenance_broadcast_lead_seconds,
            on_broadcast_due=self._handle_broadcast_due,
            on_maintenance_due=self._handle_maintenance_due,
        )
        self._steam_updater = SteamUpdater(
            steamcmd_path=config.steamcmd_path,
            install_dir=config.steam_app_install_dir,
        )
        self._maintenance_in_progress: bool = False

        # Pending settings queue and notification callbacks
        self._pending_queue = PendingSettingsQueue()
        self._apply_callbacks: list[Callable[[ApplyResult], None]] = []

    @property
    def state(self) -> ServerState:
        """Current state of the wrapper state machine."""
        return self._state

    @property
    def player_count(self) -> int:
        """Current connected player count."""
        return self._player_count

    @property
    def pending_queue(self) -> PendingSettingsQueue:
        """The pending settings queue instance."""
        return self._pending_queue

    def register_apply_callback(self, callback: Callable[[ApplyResult], None]) -> None:
        """Register a callback to be invoked when pending settings are applied.

        Args:
            callback: A callable that receives an ApplyResult instance.
        """
        self._apply_callbacks.append(callback)

    def _notify_apply_result(self, result: ApplyResult) -> None:
        """Fire all registered apply result callbacks.

        Args:
            result: The ApplyResult to pass to each callback.
        """
        for callback in self._apply_callbacks:
            try:
                callback(result)
            except Exception as e:
                logger.warning("Apply result callback failed: %s", e)

    async def run(self) -> None:
        """Main entry point - sets up logger, starts monitoring, and runs until quit.

        This is the asyncio event loop entry point. It sets up the logger,
        starts the connection listener in MONITORING state, and runs indefinitely
        until quit() is called.
        """
        # Set up the logger
        self._logger.setup(
            log_path=self._config.log_file_path,
            max_size_mb=self._config.log_max_size_mb,
            backup_count=self._config.log_backup_count,
        )

        logger.info("Wrapper starting in MONITORING state")

        # Start in MONITORING state with the connection listener active
        await self._connection_listener.start_listening()

        # Run until quit is signaled
        await self._quit_event.wait()

        # Cleanup on exit
        await self._cleanup()

    async def quit(self) -> None:
        """Signal the wrapper to stop running and perform cleanup."""
        logger.info("Quit signal received, shutting down wrapper")
        self._quit_event.set()

    async def handle_connection_detected(self) -> None:
        """Handle a detected UDP connection attempt.

        Only acts if in MONITORING state - this ensures Property 4 (single start
        attempt on multiple UDP packets). If already starting/running/stopping,
        packets are discarded.

        Transitions: MONITORING → STARTING → RUNNING (on success)
                     MONITORING → STARTING → MONITORING (on failure)
        """
        if self._state != ServerState.MONITORING:
            logger.debug(
                "Ignoring connection detected in state %s (not MONITORING)",
                self._state.value,
            )
            return

        # Transition to STARTING
        self._transition_to(ServerState.STARTING, "UDP connection attempt detected")

        # Stop the listener to release the port for the server
        await self._connection_listener.stop_listening()

        # Start the server
        result = await self._process_manager.start_server(
            str(self._config.server_exe_path)
        )

        if not result.success:
            logger.error("Server start failed: %s", result.error_message)
            self._logger.log_error(
                "Server start failed",
                Exception(result.error_message or "Unknown error"),
            )
            # Transition back to MONITORING and restart listener
            self._transition_to(ServerState.MONITORING, "Server start failed")
            await self._connection_listener.start_listening()
            return

        # Wait for the server RCON port to be ready (reliable TCP indicator)
        port_ready = await self._process_manager.wait_for_port(
            port=self._config.rcon_port,
            timeout=self._config.start_timeout_seconds,
        )

        if not port_ready:
            logger.error(
                "Server RCON not ready on port %d within %ds",
                self._config.rcon_port,
                self._config.start_timeout_seconds,
            )
            self._logger.log_error(
                "Server startup timeout",
                Exception(
                    f"Server RCON not ready on port {self._config.rcon_port} "
                    f"within {self._config.start_timeout_seconds}s"
                ),
            )
            # Stop the process since it didn't become ready
            await self._process_manager.stop_server(
                timeout=self._config.stop_timeout_seconds
            )
            # Transition back to MONITORING
            self._transition_to(ServerState.MONITORING, "Server startup timeout")
            await self._connection_listener.start_listening()
            return

        # Success - transition to RUNNING
        await self._enter_running_state()

    async def handle_idle_expired(self) -> None:
        """Handle the idle timer reaching its threshold.

        Only acts if in RUNNING state. Schedules the graceful shutdown in a
        separate task to avoid self-cancellation — stop_server() cancels the
        idle timer task, so running stop_server from within that task would
        abort the shutdown before the terminate signal is sent.
        """
        if self._state != ServerState.RUNNING:
            logger.debug(
                "Ignoring idle expiry in state %s (not RUNNING)", self._state.value
            )
            return

        logger.info("Idle timer expired, initiating graceful shutdown")
        self._logger.log_state_transition("running", "stopping (idle timeout)")
        asyncio.create_task(self.stop_server())

    async def handle_server_crashed(self) -> None:
        """Handle unexpected server process termination.

        Only acts if in RUNNING or STARTING state. Logs the crash event,
        cancels RCON polling and idle timer, transitions to MONITORING,
        and restarts the connection listener.
        """
        if self._state not in (ServerState.RUNNING, ServerState.STARTING):
            logger.debug(
                "Ignoring crash notification in state %s", self._state.value
            )
            return

        logger.warning("Server process crashed unexpectedly")
        self._logger.log_state_transition(self._state.value, "monitoring (crash)")

        # Cancel ongoing tasks
        self._cancel_rcon_polling()
        self._idle_timer.cancel()

        # Reset state
        self._player_count = 0
        self._running_since = None
        self._consecutive_rcon_failures = 0

        # Disconnect RCON
        await self._rcon_client.disconnect()

        # Transition to MONITORING
        self._transition_to(ServerState.MONITORING, "Server process crashed")

        # Apply any pending settings changes
        apply_result = self._pending_queue.apply(self._config.settings_file_path)
        if apply_result.applied_count > 0 or apply_result.failed_key is not None:
            self._notify_apply_result(apply_result)

        # Restart the connection listener
        await self._connection_listener.start_listening()

    async def start_server(self) -> StartResult:
        """Manually start the server (from management interface).

        Only works from MONITORING state. Returns an error result if
        the server is already running or starting.

        Returns:
            StartResult indicating success or failure.
        """
        if self._state != ServerState.MONITORING:
            return StartResult(
                success=False, error_message="Server is already running"
            )

        # Use the same flow as handle_connection_detected
        self._transition_to(ServerState.STARTING, "Manual start command")

        # Stop the listener to release the port
        await self._connection_listener.stop_listening()

        # Start the server process
        result = await self._process_manager.start_server(
            str(self._config.server_exe_path)
        )

        if not result.success:
            logger.error("Server start failed: %s", result.error_message)
            self._transition_to(ServerState.MONITORING, "Server start failed")
            await self._connection_listener.start_listening()
            return result

        # Wait for RCON port readiness (reliable TCP indicator)
        port_ready = await self._process_manager.wait_for_port(
            port=self._config.rcon_port,
            timeout=self._config.start_timeout_seconds,
        )

        if not port_ready:
            error_msg = (
                f"Server RCON not ready on port {self._config.rcon_port} "
                f"within {self._config.start_timeout_seconds}s"
            )
            logger.error(error_msg)
            await self._process_manager.stop_server(
                timeout=self._config.stop_timeout_seconds
            )
            self._transition_to(ServerState.MONITORING, "Server startup timeout")
            await self._connection_listener.start_listening()
            return StartResult(success=False, error_message=error_msg)

        # Success - transition to RUNNING
        await self._enter_running_state()
        return StartResult(success=True)

    async def stop_server(self) -> StopResult:
        """Stop the server gracefully with force-kill fallback.

        Only works from RUNNING state. Transitions through STOPPING to MONITORING.
        Sends the RCON Shutdown command first for a graceful save-and-exit,
        then kills the process tree as a fallback to ensure all child processes
        are cleaned up.

        Returns:
            StopResult indicating success and whether force was required.
        """
        if self._state != ServerState.RUNNING:
            return StopResult(
                success=False, error_message="Server is not running"
            )

        # Transition to STOPPING
        self._transition_to(ServerState.STOPPING, "Stop command issued")

        # Cancel RCON polling and idle timer
        self._cancel_rcon_polling()
        self._idle_timer.cancel()

        # Send RCON Shutdown command for graceful save-and-exit before
        # disconnecting. This tells PalServer to save world data and exit.
        try:
            await self._rcon_client.send_command("Shutdown")
        except Exception as e:
            logger.warning("RCON Shutdown command failed: %s", e)

        # Disconnect RCON
        await self._rcon_client.disconnect()

        # Kill the process tree — PalServer.exe spawns child processes that
        # must all be terminated to release UDP port 8211
        result = await self._process_manager.stop_server(
            timeout=self._config.stop_timeout_seconds
        )

        # Reset state
        self._player_count = 0
        self._running_since = None
        self._consecutive_rcon_failures = 0

        # Transition to MONITORING
        self._transition_to(ServerState.MONITORING, "Server stopped")

        # Apply any pending settings changes
        apply_result = self._pending_queue.apply(self._config.settings_file_path)
        if apply_result.applied_count > 0 or apply_result.failed_key is not None:
            self._notify_apply_result(apply_result)

        # Restart the connection listener
        await self._connection_listener.start_listening()

        return result

    async def restart_server(self) -> RestartResult:
        """Restart the server (stop then start).

        Behavior depends on current state:
        - RUNNING: stop then start
        - MONITORING: treat as start (per Req 3.8)
        - Otherwise: reject

        Returns:
            RestartResult indicating success or failure.
        """
        if self._state == ServerState.RUNNING:
            # Stop first
            stop_result = await self.stop_server()
            if not stop_result.success:
                return RestartResult(
                    success=False,
                    error_message=f"Failed to stop server: {stop_result.error_message}",
                )
            # Then start
            start_result = await self.start_server()
            if not start_result.success:
                return RestartResult(
                    success=False,
                    error_message=f"Failed to start server: {start_result.error_message}",
                )
            return RestartResult(success=True)

        elif self._state == ServerState.MONITORING:
            # Treat as a start per Req 3.8
            start_result = await self.start_server()
            if not start_result.success:
                return RestartResult(
                    success=False,
                    error_message=f"Failed to start server: {start_result.error_message}",
                )
            return RestartResult(success=True)

        else:
            return RestartResult(
                success=False,
                error_message=f"Cannot restart in state: {self._state.value}",
            )

    def get_status(self) -> WrapperStatus:
        """Return the current wrapper status snapshot.

        Returns:
            WrapperStatus with current state, player count, timer info, and uptime.
        """
        uptime: int | None = None
        if self._running_since is not None:
            loop = asyncio.get_event_loop()
            uptime = int(loop.time() - self._running_since)

        return WrapperStatus(
            server_state=self._state,
            player_count=self._player_count,
            idle_timer_active=self._idle_timer.is_active(),
            idle_seconds=self._idle_timer.elapsed_seconds(),
            server_pid=self._process_manager.get_pid(),
            uptime_seconds=uptime,
        )

    # -------------------------------------------------------------------------
    # Maintenance callbacks
    # -------------------------------------------------------------------------

    async def _handle_broadcast_due(self) -> None:
        """Handle the maintenance broadcast timer firing.

        Sends a warning message to connected players that maintenance is
        approaching. If no players are connected, the broadcast is skipped.
        If the RCON command fails, a warning is logged and the maintenance
        cycle continues regardless.
        """
        if self._maintenance_in_progress:
            logger.debug("Broadcast skipped: maintenance already in progress")
            return

        remaining_seconds = self._config.maintenance_broadcast_lead_seconds

        if self._player_count <= 0:
            logger.debug(
                "Broadcast skipped: no players connected"
            )
            return

        broadcast_message = (
            f"Broadcast Server_maintenance_in_{remaining_seconds}_seconds"
        )

        try:
            await self._rcon_client.send_command(broadcast_message)
            logger.info(
                "Maintenance broadcast sent: %s", broadcast_message
            )
        except Exception as e:
            logger.warning(
                "Failed to send maintenance broadcast '%s': %s",
                broadcast_message,
                e,
            )

    async def _handle_maintenance_due(self) -> None:
        """Handle the maintenance timer firing.

        Orchestrates the full maintenance cycle: stop, update, restart.
        Sets the maintenance-in-progress flag, cancels timers and RCON polling,
        then delegates to _run_maintenance_cycle().
        """
        if self._maintenance_in_progress:
            logger.debug(
                "Maintenance timer fired but cycle already in progress, ignoring"
            )
            return

        self._maintenance_in_progress = True
        self._idle_timer.cancel()
        self._maintenance_timer.cancel()
        self._cancel_rcon_polling()

        await self._run_maintenance_cycle()

    async def _run_maintenance_cycle(self) -> None:
        """Execute the full maintenance cycle: stop → update → start.

        Transitions through RUNNING → STOPPING → MONITORING → STARTING → RUNNING.
        Proceeds even if individual steps fail (stop, update) to ensure the
        server is always restarted.
        """
        loop = asyncio.get_event_loop()
        cycle_start = loop.time()

        logger.info("Maintenance cycle starting")

        # --- STOPPING phase ---
        self._transition_to(ServerState.STOPPING, "Maintenance cycle initiated")

        # Send RCON Shutdown for graceful save-and-exit
        try:
            await self._rcon_client.send_command("Shutdown")
        except Exception as e:
            logger.warning("RCON Shutdown command failed during maintenance: %s", e)

        # Disconnect RCON
        await self._rcon_client.disconnect()

        # Stop the server process (proceed even if it fails)
        stop_result = await self._process_manager.stop_server(
            timeout=self._config.stop_timeout_seconds
        )
        if not stop_result.success:
            logger.warning(
                "Server stop failed during maintenance: %s",
                stop_result.error_message,
            )
        elif stop_result.was_forced:
            logger.warning(
                "Server graceful stop failed during maintenance, force-stop performed"
            )

        # --- MONITORING phase (no connection listener during maintenance!) ---
        self._transition_to(ServerState.MONITORING, "Server stopped for maintenance")

        # Run SteamCMD update
        update_result = await self._steam_updater.update()
        if update_result.success:
            logger.info("SteamCMD update completed successfully")
        elif update_result.skipped:
            logger.info("SteamCMD update skipped (paths not configured or not found)")
        elif update_result.timed_out:
            logger.warning(
                "SteamCMD update timed out: %s", update_result.error_message
            )
        else:
            logger.warning(
                "SteamCMD update failed: %s", update_result.error_message
            )

        # --- STARTING phase ---
        self._transition_to(ServerState.STARTING, "Starting server after maintenance")

        start_result = await self._process_manager.start_server(
            str(self._config.server_exe_path)
        )

        if not start_result.success:
            logger.error(
                "Server start failed after maintenance: %s",
                start_result.error_message,
            )
            # Fall back to MONITORING with connection listener active
            self._transition_to(
                ServerState.MONITORING, "Server start failed after maintenance"
            )
            self._maintenance_in_progress = False
            await self._connection_listener.start_listening()
            return

        # Wait for RCON port readiness
        port_ready = await self._process_manager.wait_for_port(
            port=self._config.rcon_port,
            timeout=self._config.start_timeout_seconds,
        )

        if not port_ready:
            logger.error(
                "Server RCON not ready on port %d within %ds after maintenance",
                self._config.rcon_port,
                self._config.start_timeout_seconds,
            )
            await self._process_manager.stop_server(
                timeout=self._config.stop_timeout_seconds
            )
            self._transition_to(
                ServerState.MONITORING, "Server startup timeout after maintenance"
            )
            self._maintenance_in_progress = False
            await self._connection_listener.start_listening()
            return

        # --- RUNNING phase ---
        self._transition_to(ServerState.RUNNING, "Server ready after maintenance")

        # Reset player count (fresh start)
        self._player_count = 0

        # Record new running_since time
        self._running_since = loop.time()

        # Clear maintenance flag
        self._maintenance_in_progress = False

        # Restart RCON polling
        self._start_rcon_polling()

        # Restart idle timer (no players after fresh start)
        await self._idle_timer.start()

        # Start a new maintenance timer cycle
        await self._maintenance_timer.start()

        # Log total maintenance duration
        cycle_duration = loop.time() - cycle_start
        logger.info(
            "Maintenance cycle completed in %.1f seconds", cycle_duration
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _on_udp_packet_received(self) -> None:
        """Callback invoked by ConnectionListener when a UDP packet arrives.

        Schedules handle_connection_detected as an asyncio task. This is
        a synchronous callback that bridges into async code.
        """
        asyncio.ensure_future(self.handle_connection_detected())

    async def _enter_running_state(self) -> None:
        """Transition to RUNNING state and start RCON polling + idle timer."""
        self._transition_to(ServerState.RUNNING, "Server is ready")

        # Record start time for uptime tracking
        loop = asyncio.get_event_loop()
        self._running_since = loop.time()

        # Initialize player count to zero (Req 5.5)
        self._player_count = 0

        # Start RCON polling
        self._start_rcon_polling()

        # Start idle timer (Req 1.5: starts counting when server starts with 0 players)
        await self._idle_timer.start()

    def _transition_to(self, new_state: ServerState, reason: str) -> None:
        """Perform a state transition with logging.

        Args:
            new_state: The state to transition to.
            reason: Human-readable reason for the transition.
        """
        old_state = self._state
        self._state = new_state

        # Log the transition
        self._logger.log_state_transition(old_state.value, new_state.value)
        logger.info(
            "State transition: %s -> %s (%s)",
            old_state.value,
            new_state.value,
            reason,
        )

        # Record the event
        StateTransitionEvent(
            timestamp=datetime.now(tz=timezone.utc),
            from_state=old_state,
            to_state=new_state,
            reason=reason,
        )

    def _start_rcon_polling(self) -> None:
        """Start the RCON polling background task."""
        if self._rcon_poll_task is not None and not self._rcon_poll_task.done():
            return
        self._rcon_poll_task = asyncio.create_task(self._rcon_poll_loop())

    def _cancel_rcon_polling(self) -> None:
        """Cancel the RCON polling background task."""
        if self._rcon_poll_task is not None and not self._rcon_poll_task.done():
            self._rcon_poll_task.cancel()
        self._rcon_poll_task = None

    async def _rcon_poll_loop(self) -> None:
        """Background task that periodically queries player count via RCON.

        Runs while the server is in RUNNING state. Handles player count
        updates, idle timer management, and RCON failure tracking.
        """
        # Give the server a moment to initialize RCON
        await asyncio.sleep(2)

        # Attempt initial RCON connection with retry and backoff
        max_attempts = 5
        delays = [2, 4, 8, 16, 30]  # seconds between retries
        connected = False

        for attempt in range(1, max_attempts + 1):
            if self._state != ServerState.RUNNING:
                logger.debug("State changed during RCON connect retry, aborting")
                return

            connected = await self._rcon_client.connect()
            if connected:
                break

            if attempt < max_attempts:
                delay = delays[attempt - 1]
                logger.warning(
                    "RCON connection attempt %d/%d failed, retrying in %ds...",
                    attempt, max_attempts, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "RCON connection failed after %d attempts. "
                    "Will continue polling with reconnect-on-failure fallback.",
                    max_attempts,
                )

        try:
            while self._state == ServerState.RUNNING:
                result = await self._rcon_client.query_players()

                if result.success:
                    self._consecutive_rcon_failures = 0
                    new_count = max(0, result.player_count)  # Never allow < 0
                    old_count = self._player_count

                    self._player_count = new_count

                    # Log player events
                    if new_count > old_count:
                        self._logger.log_player_event("connected", new_count)
                        logger.info(
                            "Player connected (count: %d -> %d)", old_count, new_count
                        )
                        # Player joined - cancel idle timer if active (Req 1.3)
                        if self._idle_timer.is_active():
                            self._idle_timer.cancel()

                    elif new_count < old_count:
                        self._logger.log_player_event("disconnected", new_count)
                        logger.info(
                            "Player disconnected (count: %d -> %d)",
                            old_count,
                            new_count,
                        )

                    # Manage idle timer based on player count
                    if new_count == 0 and not self._idle_timer.is_active():
                        # No players - start idle timer (Req 1.1)
                        await self._idle_timer.start()
                    elif new_count > 0 and self._idle_timer.is_active():
                        # Players present - cancel idle timer (Req 1.3)
                        self._idle_timer.cancel()

                else:
                    # RCON query failed - retain last count (Req 5.6)
                    self._consecutive_rcon_failures += 1
                    logger.warning(
                        "RCON query failed (attempt %d): %s",
                        self._consecutive_rcon_failures,
                        result.error_message,
                    )

                    if self._consecutive_rcon_failures >= 5:
                        # Log warning on 5 consecutive failures (Req 5.7)
                        logger.warning(
                            "RCON has failed %d consecutive times",
                            self._consecutive_rcon_failures,
                        )

                    # Try reconnecting on next poll
                    await self._rcon_client.disconnect()
                    await self._rcon_client.connect()

                # Wait for next poll interval
                await asyncio.sleep(self._config.rcon_poll_interval_seconds)

        except asyncio.CancelledError:
            logger.debug("RCON polling task cancelled")
        except Exception as e:
            logger.error("Unexpected error in RCON polling loop: %s", e)
            self._logger.log_error("RCON polling loop", e)

    async def _cleanup(self) -> None:
        """Perform cleanup when the wrapper is shutting down."""
        self._cancel_rcon_polling()
        self._idle_timer.cancel()
        await self._connection_listener.stop_listening()
        await self._rcon_client.disconnect()

        if await self._process_manager.is_running():
            logger.info("Stopping server process during wrapper shutdown")
            await self._process_manager.stop_server(
                timeout=self._config.stop_timeout_seconds
            )
