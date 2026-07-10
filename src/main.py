"""Application entry point for the Palworld Server Wrapper.

Parses command-line arguments, builds a WrapperConfig, instantiates all
components, and runs the asyncio event loop with top-level exception handling.

Usage:
    python -m src.main --server-exe <path> --settings-file <path> [options]

Requirements: 7.1, 7.2, 7.4, 8.5
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.config import WrapperConfig
from src.management_interface import ManagementInterface
from src.wrapper_core import WrapperCore

logger = logging.getLogger(__name__)


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
        default=600,
        help="Idle timeout in seconds before shutdown (default: 600)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="RCON poll interval in seconds (default: 10)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("wrapper.log"),
        help="Log file path (default: wrapper.log)",
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
        log_file_path=args.log_file,
    )
    config.validate()
    return config


async def run_wrapper(config: WrapperConfig) -> None:
    """Run the wrapper core and management interface concurrently.

    Sets up a global exception handler on the asyncio event loop so that
    unhandled exceptions are logged but do not crash the wrapper (Req 8.5).

    Args:
        config: Validated wrapper configuration.
    """
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
    management_interface = ManagementInterface(wrapper_core, config)

    # Run both concurrently; if either finishes, cancel the other
    core_task = asyncio.create_task(wrapper_core.run(), name="wrapper_core")
    interface_task = asyncio.create_task(
        management_interface.run(), name="management_interface"
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

    try:
        asyncio.run(run_wrapper(config))
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
