"""Management Interface for the Palworld Server Wrapper.

Provides a local CLI-based interface for user interaction with the wrapper.
Runs on the asyncio event loop using asyncio.to_thread for non-blocking stdin
reading, allowing the interface to remain responsive (<2s) even during
long-running server operations.

Commands:
    start    - Start the Dedicated Server
    stop     - Stop the Dedicated Server
    restart  - Restart the Dedicated Server
    status   - Display current server status
    settings - Display all server settings
    set      - Modify a server setting (set <key> <value>)
    help     - Show available commands
    quit     - Shut down the wrapper
"""

import asyncio
import logging
from pathlib import Path

from src.config import WrapperConfig
from src.models import ServerState, WrapperStatus
from src.settings_parser import SettingsParser
from src.wrapper_core import WrapperCore

logger = logging.getLogger(__name__)


class ManagementInterface:
    """CLI management interface running on the asyncio event loop.

    Provides non-blocking command input and real-time status display.
    Integrates with WrapperCore for command execution and SettingsParser
    for settings management.
    """

    def __init__(self, wrapper_core: WrapperCore, config: WrapperConfig) -> None:
        """Initialize the management interface.

        Args:
            wrapper_core: The WrapperCore instance for command execution.
            config: The wrapper configuration for settings file path and other params.
        """
        self._wrapper_core = wrapper_core
        self._config = config
        self._settings_parser = SettingsParser()
        self._running = False

    async def run(self) -> None:
        """Main entry point - run the interactive command loop.

        Uses asyncio.to_thread(input) for non-blocking stdin reading,
        ensuring the interface remains responsive within 2 seconds
        even during server operations.
        """
        self._running = True
        await self.display_message("Palworld Server Wrapper - Management Interface")
        await self.display_message("Type 'help' for available commands.\n")

        # Show initial status
        status = self._wrapper_core.get_status()
        await self.display_status(status)

        while self._running:
            try:
                command = await self.prompt_command()
                if command is None:
                    # EOF or input error
                    break
                await self._handle_command(command)
            except asyncio.CancelledError:
                break
            except EOFError:
                break
            except Exception as e:
                logger.error("Error in management interface: %s", e)
                await self.display_message(f"Error: {e}")

    async def display_status(self, status: WrapperStatus) -> None:
        """Display the current server status in formatted output.

        Args:
            status: The current wrapper status snapshot.
        """
        state_display = status.server_state.value.upper()
        output_lines = [
            f"Server Status: {state_display}",
            f"Player Count: {status.player_count}",
        ]

        # Idle timer display
        if status.idle_timer_active:
            idle_threshold = self._config.idle_timeout_seconds
            output_lines.append(
                f"Idle Timer: {status.idle_seconds}s elapsed ({idle_threshold}s threshold)"
            )
        else:
            output_lines.append("Idle Timer: Not active")

        # Server PID (only when running/starting/stopping)
        if status.server_pid is not None:
            output_lines.append(f"Server PID: {status.server_pid}")

        # Uptime (only when server has been running)
        if status.uptime_seconds is not None:
            output_lines.append(f"Uptime: {status.uptime_seconds}s")

        output = "\n".join(output_lines)
        print(output)

    async def prompt_command(self) -> str | None:
        """Prompt the user for a command using non-blocking input.

        Uses asyncio.to_thread to read from stdin without blocking
        the event loop, ensuring responsiveness within 2 seconds.

        Returns:
            The user's input string, or None on EOF/error.
        """
        try:
            user_input = await asyncio.to_thread(input, "> ")
            return user_input.strip()
        except EOFError:
            return None
        except OSError:
            return None

    async def display_message(self, message: str) -> None:
        """Display a message to the user.

        Args:
            message: The message string to display.
        """
        print(message)

    async def _handle_command(self, command: str) -> None:
        """Parse and execute a user command.

        Args:
            command: The raw command string from the user.
        """
        if not command:
            return

        parts = command.split(maxsplit=2)
        cmd = parts[0].lower()

        if cmd == "start":
            await self._cmd_start()
        elif cmd == "stop":
            await self._cmd_stop()
        elif cmd == "restart":
            await self._cmd_restart()
        elif cmd == "status":
            await self._cmd_status()
        elif cmd == "settings":
            await self._cmd_settings()
        elif cmd == "set":
            await self._cmd_set(parts)
        elif cmd == "help":
            await self._cmd_help()
        elif cmd == "quit":
            await self._cmd_quit()
        else:
            await self.display_message(
                "Unknown command. Type 'help' for available commands."
            )

    async def _cmd_start(self) -> None:
        """Handle the 'start' command."""
        status = self._wrapper_core.get_status()
        if status.server_state != ServerState.MONITORING:
            await self.display_message("Server is already running.")
            return

        await self.display_message("Starting server...")
        result = await self._wrapper_core.start_server()

        if result.success:
            await self.display_message("Server started successfully.")
        else:
            await self.display_message(
                f"Failed to start server: {result.error_message}"
            )

    async def _cmd_stop(self) -> None:
        """Handle the 'stop' command."""
        status = self._wrapper_core.get_status()
        if status.server_state != ServerState.RUNNING:
            await self.display_message("Server is not running.")
            return

        await self.display_message("Stopping server...")
        result = await self._wrapper_core.stop_server()

        if result.success:
            if result.was_forced:
                await self.display_message(
                    "Server stopped (force kill was required)."
                )
            else:
                await self.display_message("Server stopped successfully.")
        else:
            await self.display_message(
                f"Failed to stop server: {result.error_message}"
            )

    async def _cmd_restart(self) -> None:
        """Handle the 'restart' command."""
        await self.display_message("Restarting server...")
        result = await self._wrapper_core.restart_server()

        if result.success:
            await self.display_message("Server restarted successfully.")
        else:
            await self.display_message(
                f"Failed to restart server: {result.error_message}"
            )

    async def _cmd_status(self) -> None:
        """Handle the 'status' command."""
        status = self._wrapper_core.get_status()
        await self.display_status(status)

    async def _cmd_settings(self) -> None:
        """Handle the 'settings' command."""
        settings = self._settings_parser.read_settings(self._config.settings_file_path)

        if "__error__" in settings:
            await self.display_message(f"Error reading settings: {settings['__error__']}")
            return

        if not settings:
            await self.display_message("No settings found in configuration file.")
            return

        await self.display_message("Current Server Settings:")
        await self.display_message("-" * 40)
        for key, value in sorted(settings.items()):
            await self.display_message(f"  {key} = {value}")

    async def _cmd_set(self, parts: list[str]) -> None:
        """Handle the 'set <key> <value>' command.

        Args:
            parts: The split command parts (["set", "<key>", "<value>"]).
        """
        if len(parts) < 3:
            await self.display_message("Usage: set <key> <value>")
            return

        key = parts[1]
        value = parts[2]

        # Validate and write the setting
        result = self._settings_parser.write_setting(
            self._config.settings_file_path, key, value
        )

        if result.valid:
            await self.display_message(f"Setting '{key}' updated to '{value}'.")

            # Warn if server is running that restart is required
            status = self._wrapper_core.get_status()
            if status.server_state == ServerState.RUNNING:
                await self.display_message(
                    "Warning: Setting modified while server is running. "
                    "A restart is required for changes to take effect."
                )
        else:
            await self.display_message(
                f"Failed to update setting: {result.error_message}"
            )

    async def _cmd_help(self) -> None:
        """Handle the 'help' command."""
        help_text = (
            "Available commands:\n"
            "  start            - Start the Dedicated Server\n"
            "  stop             - Stop the Dedicated Server\n"
            "  restart          - Restart the Dedicated Server\n"
            "  status           - Display current server status\n"
            "  settings         - Display all server settings\n"
            "  set <key> <value> - Modify a server setting\n"
            "  help             - Show this help message\n"
            "  quit             - Shut down the wrapper"
        )
        await self.display_message(help_text)

    async def _cmd_quit(self) -> None:
        """Handle the 'quit' command."""
        await self.display_message("Shutting down wrapper...")
        self._running = False
        await self._wrapper_core.quit()
