"""Process manager for launching and controlling the Palworld Dedicated Server."""

import asyncio
import logging
import socket
from collections.abc import Callable, Coroutine
from typing import Any

from src.models import StartResult, StopResult

logger = logging.getLogger(__name__)

# Type alias for the on_crash callback
OnCrashCallback = Callable[[], Coroutine[Any, Any, None]]


class ProcessManager:
    """Manages the lifecycle of the Palworld Dedicated Server process.

    Handles starting, stopping, and monitoring the server subprocess.
    Detects unexpected termination and invokes an optional crash callback.
    """

    def __init__(self, on_crash: OnCrashCallback | None = None) -> None:
        """Initialize the process manager.

        Args:
            on_crash: Optional async callback invoked when the server process
                terminates unexpectedly (not via stop_server).
        """
        self._process: asyncio.subprocess.Process | None = None
        self._on_crash = on_crash
        self._monitor_task: asyncio.Task[None] | None = None
        self._stopping = False

    async def start_server(self, exe_path: str, args: list[str] | None = None) -> StartResult:
        """Launch the server process.

        Args:
            exe_path: Path to the PalServer.exe executable.
            args: Optional list of command-line arguments to pass.

        Returns:
            StartResult indicating success or failure with error details.
        """
        if self._process is not None and self._process.returncode is None:
            return StartResult(success=False, error_message="Server process is already running")

        if args is None:
            args = []

        try:
            self._stopping = False
            self._process = await asyncio.create_subprocess_exec(
                exe_path,
                *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            logger.info("Server process started with PID %d", self._process.pid)

            # Start background task to monitor for unexpected termination
            self._monitor_task = asyncio.create_task(self._monitor_process())

            return StartResult(success=True)
        except FileNotFoundError:
            error_msg = f"Server executable not found: {exe_path}"
            logger.error(error_msg)
            return StartResult(success=False, error_message=error_msg)
        except PermissionError:
            error_msg = f"Permission denied when launching: {exe_path}"
            logger.error(error_msg)
            return StartResult(success=False, error_message=error_msg)
        except OSError as e:
            error_msg = f"OS error launching server: {e}"
            logger.error(error_msg)
            return StartResult(success=False, error_message=error_msg)

    async def stop_server(self, timeout: int = 30) -> StopResult:
        """Stop the server process gracefully, with force kill as fallback.

        On Windows, PalServer.exe is a launcher that spawns child processes.
        Simple process.terminate() only kills the launcher, leaving the actual
        game server running. This method uses `taskkill /T /F` to kill the
        entire process tree reliably.

        Args:
            timeout: Seconds to wait for graceful shutdown before force killing.

        Returns:
            StopResult indicating success and whether force was required.
        """
        if self._process is None or self._process.returncode is not None:
            return StopResult(success=False, error_message="Server process is not running")

        self._stopping = True
        pid = self._process.pid

        try:
            # Kill the entire process tree using taskkill on Windows
            # PalServer.exe spawns child processes, so we must use /T (tree kill)
            logger.info(
                "Killing server process tree (PID %d) with taskkill", pid
            )
            kill_proc = await asyncio.create_subprocess_exec(
                "taskkill", "/F", "/T", "/PID", str(pid),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                kill_proc.communicate(), timeout=timeout
            )

            if kill_proc.returncode != 0:
                stderr_text = stderr.decode(errors="replace").strip()
                # taskkill returns non-zero if PID not found (already exited)
                if "not found" in stderr_text.lower():
                    logger.info("Server process tree already terminated")
                else:
                    logger.warning(
                        "taskkill returned code %d: %s",
                        kill_proc.returncode, stderr_text,
                    )

            # Wait for our tracked process handle to reflect termination
            try:
                await asyncio.wait_for(self._process.wait(), timeout=10)
            except asyncio.TimeoutError:
                # Process handle didn't close, but tree kill should have worked
                logger.warning(
                    "Process handle did not close within 10s after taskkill"
                )

            logger.info("Server process tree terminated (PID %d)", pid)
            self._cancel_monitor()
            return StopResult(success=True, was_forced=True)

        except asyncio.TimeoutError:
            logger.error("taskkill timed out after %ds", timeout)
            self._cancel_monitor()
            return StopResult(
                success=False,
                was_forced=True,
                error_message="taskkill timed out",
            )
        except FileNotFoundError:
            # taskkill not available — fall back to process.kill()
            logger.warning("taskkill not found, falling back to process.kill()")
            self._process.kill()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass
            self._cancel_monitor()
            return StopResult(success=True, was_forced=True)
        except ProcessLookupError:
            logger.info("Server process already terminated")
            self._cancel_monitor()
            return StopResult(success=True, was_forced=False)

    async def is_running(self) -> bool:
        """Check if the server process is currently alive.

        Returns:
            True if the process exists and has not exited.
        """
        return self._process is not None and self._process.returncode is None

    async def wait_for_port(self, port: int = 8212, timeout: int = 120) -> bool:
        """Wait for the server to begin listening on the specified TCP port.

        Polls using TCP socket connection attempts with a brief sleep between
        each attempt. Defaults to the REST API port (8212) which is a reliable
        indicator that the server is fully initialized.

        Args:
            port: The TCP port to check (default 8212, the REST API port).
            timeout: Maximum seconds to wait for the port to become available.

        Returns:
            True if the port became available within the timeout, False otherwise.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout

        while loop.time() < deadline:
            # Check if process died while waiting
            if self._process is not None and self._process.returncode is not None:
                logger.error("Server process exited while waiting for port %d", port)
                return False

            if await self._try_connect(port):
                logger.info("Server is now listening on port %d", port)
                return True

            await asyncio.sleep(1.0)

        logger.error("Timed out waiting for server to listen on port %d after %ds", port, timeout)
        return False

    def get_pid(self) -> int | None:
        """Get the process ID of the running server.

        Returns:
            The PID if the server is running, None otherwise.
        """
        if self._process is not None and self._process.returncode is None:
            return self._process.pid
        return None

    async def _try_connect(self, port: int) -> bool:
        """Attempt a TCP connection to localhost on the given port.

        Args:
            port: Port number to try connecting to.

        Returns:
            True if connection succeeded, False otherwise.
        """
        try:
            loop = asyncio.get_event_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            try:
                await asyncio.wait_for(
                    loop.sock_connect(sock, ("127.0.0.1", port)),
                    timeout=2.0,
                )
                return True
            except (OSError, asyncio.TimeoutError):
                return False
            finally:
                sock.close()
        except OSError:
            return False

    async def _monitor_process(self) -> None:
        """Background task that waits for the process to exit.

        If the process terminates unexpectedly (not via stop_server),
        invokes the on_crash callback.
        """
        if self._process is None:
            return

        await self._process.wait()

        # Only invoke crash callback if we weren't intentionally stopping
        if not self._stopping and self._on_crash is not None:
            logger.warning(
                "Server process terminated unexpectedly (exit code: %s)",
                self._process.returncode,
            )
            try:
                await self._on_crash()
            except Exception as e:
                logger.error("Error in on_crash callback: %s", e)

    def _cancel_monitor(self) -> None:
        """Cancel the background process monitor task."""
        if self._monitor_task is not None and not self._monitor_task.done():
            self._monitor_task.cancel()
            self._monitor_task = None
