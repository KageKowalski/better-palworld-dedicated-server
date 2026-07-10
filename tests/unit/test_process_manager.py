"""Unit tests for the ProcessManager class."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import StartResult, StopResult
from src.process_manager import ProcessManager


@pytest.fixture
def process_manager():
    """Create a ProcessManager instance with no crash callback."""
    return ProcessManager()


@pytest.fixture
def process_manager_with_callback():
    """Create a ProcessManager with an on_crash callback."""
    callback = AsyncMock()
    pm = ProcessManager(on_crash=callback)
    return pm, callback


class TestStartServer:
    """Tests for ProcessManager.start_server()."""

    @pytest.mark.asyncio
    async def test_start_server_file_not_found(self, process_manager):
        """Starting with a non-existent exe path returns a failure result."""
        result = await process_manager.start_server("nonexistent_path.exe")
        assert result.success is False
        assert "not found" in result.error_message

    @pytest.mark.asyncio
    async def test_start_server_already_running(self, process_manager):
        """Starting when a process is already running returns failure."""
        # Mock an existing running process
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.pid = 1234
        process_manager._process = mock_proc

        result = await process_manager.start_server("PalServer.exe")
        assert result.success is False
        assert "already running" in result.error_message

    @pytest.mark.asyncio
    async def test_start_server_success(self, process_manager):
        """Starting with a valid executable succeeds and records the process."""
        # Use a simple command that runs briefly - Python itself
        result = await process_manager.start_server(
            sys.executable, ["-c", "import time; time.sleep(5)"]
        )
        assert result.success is True
        assert result.error_message is None
        assert process_manager._process is not None
        assert process_manager._process.pid is not None

        # Clean up
        process_manager._stopping = True
        process_manager._process.kill()
        await process_manager._process.wait()
        process_manager._cancel_monitor()


class TestStopServer:
    """Tests for ProcessManager.stop_server()."""

    @pytest.mark.asyncio
    async def test_stop_server_not_running(self, process_manager):
        """Stopping when no process is running returns failure."""
        result = await process_manager.stop_server()
        assert result.success is False
        assert "not running" in result.error_message

    @pytest.mark.asyncio
    async def test_stop_server_already_exited(self, process_manager):
        """Stopping when the process has already exited returns failure."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0  # Already exited
        process_manager._process = mock_proc

        result = await process_manager.stop_server()
        assert result.success is False
        assert "not running" in result.error_message

    @pytest.mark.asyncio
    async def test_stop_server_graceful(self, process_manager):
        """Stopping a running process with taskkill succeeds."""
        # Start a real process that we can terminate
        process_manager._process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(60)",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        process_manager._monitor_task = asyncio.create_task(
            process_manager._monitor_process()
        )

        result = await process_manager.stop_server(timeout=10)
        assert result.success is True
        # taskkill /F always reports was_forced=True since it's a tree kill
        assert result.was_forced is True

    @pytest.mark.asyncio
    async def test_stop_server_already_terminated_process(self, process_manager):
        """Stopping when taskkill reports process not found still succeeds."""
        # Use a PID that doesn't exist — taskkill will fail with "not found"
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.pid = 99999999  # Non-existent PID

        async def mock_wait():
            mock_proc.returncode = -1
            return -1

        mock_proc.wait = mock_wait
        process_manager._process = mock_proc
        process_manager._monitor_task = None

        result = await process_manager.stop_server(timeout=10)
        # Should still succeed — "not found" means it's already gone
        assert result.success is True


class TestIsRunning:
    """Tests for ProcessManager.is_running()."""

    @pytest.mark.asyncio
    async def test_is_running_no_process(self, process_manager):
        """Returns False when no process has been started."""
        assert await process_manager.is_running() is False

    @pytest.mark.asyncio
    async def test_is_running_process_alive(self, process_manager):
        """Returns True when process is active."""
        mock_proc = MagicMock()
        mock_proc.returncode = None
        process_manager._process = mock_proc
        assert await process_manager.is_running() is True

    @pytest.mark.asyncio
    async def test_is_running_process_exited(self, process_manager):
        """Returns False when process has exited."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        process_manager._process = mock_proc
        assert await process_manager.is_running() is False


class TestGetPid:
    """Tests for ProcessManager.get_pid()."""

    def test_get_pid_no_process(self, process_manager):
        """Returns None when no process exists."""
        assert process_manager.get_pid() is None

    def test_get_pid_running_process(self, process_manager):
        """Returns the PID when a process is running."""
        mock_proc = MagicMock()
        mock_proc.returncode = None
        mock_proc.pid = 42
        process_manager._process = mock_proc
        assert process_manager.get_pid() == 42

    def test_get_pid_exited_process(self, process_manager):
        """Returns None when the process has exited."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.pid = 42
        process_manager._process = mock_proc
        assert process_manager.get_pid() is None


class TestWaitForPort:
    """Tests for ProcessManager.wait_for_port()."""

    @pytest.mark.asyncio
    async def test_wait_for_port_process_died(self, process_manager):
        """Returns False if the process dies while waiting for port."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1  # Already exited
        process_manager._process = mock_proc

        result = await process_manager.wait_for_port(port=8211, timeout=2)
        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_port_success(self, process_manager):
        """Returns True when port becomes available."""
        # Start a real TCP server on a random port
        server = await asyncio.start_server(
            lambda r, w: w.close(), "127.0.0.1", 0
        )
        port = server.sockets[0].getsockname()[1]

        # Set up a mock process that appears running
        mock_proc = MagicMock()
        mock_proc.returncode = None
        process_manager._process = mock_proc

        result = await process_manager.wait_for_port(port=port, timeout=5)
        assert result is True

        server.close()
        await server.wait_closed()

    @pytest.mark.asyncio
    async def test_wait_for_port_timeout(self, process_manager):
        """Returns False when port never becomes available within timeout."""
        mock_proc = MagicMock()
        mock_proc.returncode = None
        process_manager._process = mock_proc

        # Use a port that nothing is listening on
        result = await process_manager.wait_for_port(port=59999, timeout=2)
        assert result is False


class TestCrashDetection:
    """Tests for unexpected process termination detection."""

    @pytest.mark.asyncio
    async def test_crash_callback_invoked(self):
        """on_crash callback is invoked when process terminates unexpectedly."""
        callback = AsyncMock()
        pm = ProcessManager(on_crash=callback)

        # Start a process that exits immediately
        pm._process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "pass",  # Exits immediately
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        pm._stopping = False
        pm._monitor_task = asyncio.create_task(pm._monitor_process())

        # Wait for the monitor to detect termination
        await asyncio.sleep(0.5)
        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_crash_callback_on_intentional_stop(self):
        """on_crash callback is NOT invoked when stop_server is used."""
        callback = AsyncMock()
        pm = ProcessManager(on_crash=callback)

        pm._process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "import time; time.sleep(60)",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        pm._monitor_task = asyncio.create_task(pm._monitor_process())

        await pm.stop_server(timeout=5)
        await asyncio.sleep(0.5)

        callback.assert_not_called()
