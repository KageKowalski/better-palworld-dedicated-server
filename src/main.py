"""Application entry point for the Palworld Server Wrapper.

Parses command-line arguments, builds a WrapperConfig, instantiates all
components, and runs the asyncio event loop with top-level exception handling.

Usage:
    python -m src.main --server-exe <path> --settings-file <path> [options]

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 7.1, 7.2, 7.4, 8.5
"""

import argparse
import asyncio
import logging
import sys
import tkinter as tk
from pathlib import Path

from src import launcher
from src.config import WrapperConfig
from src.logger import WrapperLogger
from src.management_interface import ManagementInterface
from src.wrapper_core import WrapperCore

logger = logging.getLogger(__name__)


def interface_type(value: str) -> str:
    """Case-insensitive type function for the --interface argument.

    Converts the input to lowercase so that "GUI", "Console", "gui", "CONSOLE",
    etc. are all accepted. argparse's choices validation then checks against
    the lowercase choices list ["gui", "console"].

    Args:
        value: The raw string value provided by the user.

    Returns:
        The lowercased string value.
    """
    return value.lower()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for wrapper configuration.

    Args:
        argv: Optional argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace with all configuration values.
    """
    parser = argparse.ArgumentParser(
        prog="palworld-server-wrapper",
        description="Lightweight wrapper for managing a Palworld Dedicated Server.",
    )

    parser.add_argument(
        "--server-exe",
        type=Path,
        required=True,
        help="Path to PalServer.exe",
    )
    parser.add_argument(
        "--settings-file",
        type=Path,
        required=True,
        help="Path to PalWorldSettings.ini",
    )
    parser.add_argument(
        "--rcon-port",
        type=int,
        default=25575,
        help="RCON TCP port (default: 25575)",
    )
    parser.add_argument(
        "--rcon-password",
        type=str,
        default="",
        help="RCON admin password (default: empty)",
    )
    parser.add_argument(
        "--game-port",
        type=int,
        default=8211,
        help="Game UDP port (default: 8211)",
    )
    parser.add_argument(
        "--idle-timeout",
        type=int,
        default=300,
        help="Idle timeout in seconds before shutdown (default: 300)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="RCON poll interval in seconds (default: 10)",
    )
    parser.add_argument(
        "--maintenance-interval",
        type=int,
        default=21600,
        help="Seconds between maintenance restarts (default: 21600, range: 3600-86400)",
    )
    parser.add_argument(
        "--maintenance-broadcast-lead",
        type=int,
        default=300,
        help="Seconds before restart to warn players (default: 300, range: 30-1800)",
    )
    parser.add_argument(
        "--steamcmd-path",
        type=str,
        default="",
        help="Path to steamcmd.exe for automatic updates (default: empty, skips updates)",
    )
    parser.add_argument(
        "--steam-app-install-dir",
        type=str,
        default="",
        help="Palworld server install directory for SteamCMD (default: empty)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("wrapper.log"),
        help="Log file path (default: wrapper.log)",
    )
    parser.add_argument(
        "--interface",
        type=interface_type,
        default="gui",
        choices=["gui", "console"],
        help="Interface mode: gui (default) or console",
    )
    parser.add_argument(
        "--detached",
        action="store_true",
        default=False,
        help=argparse.SUPPRESS,
    )

    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> WrapperConfig:
    """Build a WrapperConfig from parsed command-line arguments.

    Args:
        args: The parsed argparse namespace.

    Returns:
        A validated WrapperConfig instance.

    Raises:
        ValueError: If configuration validation fails.
    """
    config = WrapperConfig(
        server_exe_path=args.server_exe,
        settings_file_path=args.settings_file,
        game_port=args.game_port,
        rcon_port=args.rcon_port,
        rcon_password=args.rcon_password,
        idle_timeout_seconds=args.idle_timeout,
        rcon_poll_interval_seconds=args.poll_interval,
        maintenance_interval_seconds=args.maintenance_interval,
        maintenance_broadcast_lead_seconds=args.maintenance_broadcast_lead,
        steamcmd_path=args.steamcmd_path,
        steam_app_install_dir=args.steam_app_install_dir,
        log_file_path=args.log_file,
    )
    config.validate()
    return config


async def run_wrapper(
    config: WrapperConfig, interface_mode: str = "gui", is_detached: bool = False
) -> None:
    """Run the wrapper core and management interface concurrently.

    Sets up a global exception handler on the asyncio event loop so that
    unhandled exceptions are logged but do not crash the wrapper (Req 8.5).

    Selects the interface based on interface_mode:
    - "gui": imports and instantiates GuiInterface (exits with code 1 on TclError)
    - "console": uses existing ManagementInterface

    When is_detached is True, installs a CTRL_CLOSE_EVENT handler to prevent
    the OS from killing the process if any residual console association exists.

    Args:
        config: Validated wrapper configuration.
        interface_mode: Interface to use, either "gui" or "console".
        is_detached: Whether the process is running in detached mode.
    """
    # If running as a detached GUI process, ignore CTRL_CLOSE_EVENT (Req 5.4)
    if is_detached:
        launcher.install_ctrl_close_handler()

    loop = asyncio.get_running_loop()

    # Install a global exception handler for unhandled async exceptions (Req 8.5)
    def handle_exception(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exception = context.get("exception")
        message = context.get("message", "Unhandled exception in asyncio")
        if exception:
            logger.error(
                "Unhandled exception caught (wrapper continues): %s - %s",
                message,
                exception,
                exc_info=exception,
            )
        else:
            logger.error("Unhandled error (wrapper continues): %s", message)

    loop.set_exception_handler(handle_exception)

    # Instantiate components
    wrapper_core = WrapperCore(config)

    # Select interface based on mode
    if interface_mode == "gui":
        try:
            from src.gui_interface import GuiInterface
            interface = GuiInterface(wrapper_core, config)
        except tk.TclError as e:
            logger.error("Failed to initialize GUI: %s", e)
            print(f"Error: GUI cannot be initialized: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        interface = ManagementInterface(wrapper_core, config)

    # Configure logging based on interface mode (Req 4.1-4.6)
    wrapper_logger = WrapperLogger()
    if interface_mode == "gui":
        gui_callback = interface.get_log_callback()
        try:
            wrapper_logger.setup(
                config.log_file_path,
                max_size_mb=config.log_max_size_mb,
                backup_count=config.log_backup_count,
                mode="gui",
                gui_callback=gui_callback,
            )
        except Exception as e:
            # Report log file error via GUI notification bar (Req 4.5)
            if hasattr(interface, "_notification_bar") and interface._notification_bar is not None:
                interface._notification_bar.show_error(
                    f"Warning: Could not set up log file: {e}"
                )
    else:
        try:
            wrapper_logger.setup(
                config.log_file_path,
                max_size_mb=config.log_max_size_mb,
                backup_count=config.log_backup_count,
                mode="console",
            )
        except Exception as e:
            # Report log file error via stderr for console mode (Req 4.5)
            print(
                f"Warning: Could not set up log file: {e}",
                file=sys.stderr,
            )

    # Run both concurrently; if either finishes, cancel the other
    core_task = asyncio.create_task(wrapper_core.run(), name="wrapper_core")
    interface_task = asyncio.create_task(
        interface.run(), name="interface"
    )

    done, pending = await asyncio.wait(
        [core_task, interface_task],
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cancel any remaining tasks
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Propagate any exception from the completed tasks (for logging)
    for task in done:
        if task.exception():
            logger.error(
                "Task %s raised an exception: %s",
                task.get_name(),
                task.exception(),
            )


def main(argv: list[str] | None = None) -> None:
    """Main entry point: parse args, validate config, and run the event loop.

    Handles KeyboardInterrupt (Ctrl+C) gracefully and catches any top-level
    exceptions to keep the wrapper from crashing without logging (Req 8.5).

    Args:
        argv: Optional argument list for testing (defaults to sys.argv[1:]).
    """
    # Configure basic logging before anything else (stderr fallback)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    try:
        args = parse_args(argv)
        config = build_config(args)
    except SystemExit:
        raise
    except ValueError as e:
        logger.error("Configuration error: %s", e)
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error("Unexpected error during startup: %s", e, exc_info=True)
        print(f"Startup error: {e}", file=sys.stderr)
        sys.exit(1)

    # Check if we need to detach and respawn as a GUI process (Req 1.1, 6.1-6.3)
    if launcher.should_detach(args.interface, args.detached):
        exit_code = launcher.detach_and_respawn(sys.argv)
        sys.exit(exit_code)

    try:
        asyncio.run(run_wrapper(config, args.interface, is_detached=args.detached))
    except KeyboardInterrupt:
        logger.info("Received Ctrl+C, shutting down gracefully")
        print("\nShutting down...")
    except Exception as e:
        # Top-level unhandled exception: log and continue (Req 8.5)
        logger.critical("Fatal unhandled exception: %s", e, exc_info=True)
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
