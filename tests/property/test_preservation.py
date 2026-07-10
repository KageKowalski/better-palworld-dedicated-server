# Property 2: Preservation - Existing Wrapper Behavior
"""Preservation property tests verifying existing wrapper behavior is maintained.

These tests MUST PASS on the current unfixed code. They confirm baseline behavior
that the bugfix must not regress:
  2a. Crash detection triggers on_crash callback (Req 3.1)
  2b. UDP packet detection invokes on_packet_received callback (Req 3.2)
  2c. Idle timer expiry triggers on_expired callback (Req 3.3)
  2d. Graceful stop terminates process and transitions to MONITORING (Req 3.4)
  2e. Invalid state commands are rejected without state change (Req 3.5)
"""

import asyncio
import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, strategies as st

from src.connection_listener import ConnectionListener
from src.idle_timer import IdleTimer
from src.models import ServerState, StartResult, StopResult
from src.process_manager import ProcessManager
from src.wrapper_core import WrapperCore
from src.config import WrapperConfig


def _make_config() -> WrapperConfig:
    """Create a minimal WrapperConfig for testing."""
    return WrapperConfig(
        server_exe_path=Path("PalServer.exe"),
        settings_file_path=Path("PalWorldSettings.ini"),
        game_port=8211,
        rcon_port=25575,
        rcon_password="test",
        idle_timeout_seconds=600,
        start_timeout_seconds=120,
        stop_timeout_seconds=30,
        rcon_poll_interval_seconds=10,
    )


class TestPreservationProperties:
    """Property-based tests that verify preservation of existing wrapper behavior.

    All tests in this class are expected to PASS on the current unfixed code.
    They serve as regression guards for the bugfix implementation.
    """

    # -------------------------------------------------------------------------
    # Test 2a: Crash detection preservation (Req 3.1)
    # -------------------------------------------------------------------------

    @given(exit_code=st.integers(min_value=-128, max_value=128))
    @settings(max_examples=100)
    async def test_crash_detection_invokes_callback(self, exit_code: int) -> None:
        """When a process terminates unexpectedly, on_crash callback is invoked.

        Verifies that _monitor_process detects process exit and calls the
        on_crash callback when _stopping is False.

        **Validates: Requirements 3.1**
        """
        callback = AsyncMock()
        pm = ProcessManager(on_crash=callback)

        # Create a mock process that has already "exited"
        mock_process = MagicMock()
        mock_process.returncode = exit_code

        # Make wait() return immediately (process already exited)
        async def mock_wait():
            return exit_code

        mock_process.wait = mock_wait
        pm._process = mock_process
        pm._stopping = False

        # Run the monitor
        await pm._monitor_process()

        # Crash callback should have been invoked
        callback.assert_called_once()

    @given(exit_code=st.integers(min_value=-128, max_value=128))
    @settings(max_examples=100)
    async def test_no_crash_callback_when_stopping(self, exit_code: int) -> None:
        """When _stopping is True, on_crash callback is NOT invoked.

        Verifies that intentional stops don't trigger the crash handler.

        **Validates: Requirements 3.1**
        """
        callback = AsyncMock()
        pm = ProcessManager(on_crash=callback)

        mock_process = MagicMock()
        mock_process.returncode = exit_code

        async def mock_wait():
            return exit_code

        mock_process.wait = mock_wait
        pm._process = mock_process
        pm._stopping = True

        await pm._monitor_process()

        callback.assert_not_called()

    # -------------------------------------------------------------------------
    # Test 2b: UDP packet detection preservation (Req 3.2)
    # -------------------------------------------------------------------------

    @given(packet_data=st.binary(min_size=1, max_size=512))
    @settings(max_examples=100)
    async def test_udp_packet_invokes_callback(self, packet_data: bytes) -> None:
        """When a UDP packet arrives, on_packet_received callback is invoked.

        Uses the _UdpProtocol directly via create_datagram_endpoint on a
        random OS-assigned port, sends a packet, and verifies callback fires.

        **Validates: Requirements 3.2**
        """
        from src.connection_listener import _UdpProtocol

        callback_fired = asyncio.Event()
        callback = MagicMock(side_effect=lambda: callback_fired.set())

        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _UdpProtocol(callback),
            local_addr=("127.0.0.1", 0),
        )

        actual_port = transport.get_extra_info("sockname")[1]

        try:
            # Send a UDP packet to the listener
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(packet_data, ("127.0.0.1", actual_port))
            sock.close()

            # Wait for the callback to fire
            await asyncio.wait_for(callback_fired.wait(), timeout=1.0)
            callback.assert_called()
        finally:
            transport.close()

    # -------------------------------------------------------------------------
    # Test 2c: Idle timer expiry triggers shutdown (Req 3.3)
    # -------------------------------------------------------------------------

    @given(dummy=st.integers(min_value=0, max_value=100))
    @settings(max_examples=100)
    async def test_idle_timer_fires_callback_on_expiry(
        self, dummy: int
    ) -> None:
        """When idle timer expires, the on_expired callback is invoked.

        Uses a very short fixed timeout to keep tests fast. The hypothesis
        parameter generates variety in test execution ordering.

        **Validates: Requirements 3.3**
        """
        fired = asyncio.Event()

        def on_expired():
            fired.set()

        # Use a fixed short timeout for speed (0.01s)
        timer = IdleTimer(timeout_seconds=0.01, on_expired=on_expired)
        await timer.start()

        # Wait for the timer to fire
        try:
            await asyncio.wait_for(fired.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("IdleTimer did not fire on_expired callback")

        assert fired.is_set()

    @given(dummy=st.integers(min_value=0, max_value=100))
    @settings(max_examples=100)
    async def test_idle_timer_async_callback_on_expiry(
        self, dummy: int
    ) -> None:
        """When idle timer expires with async callback, the callback is awaited.

        **Validates: Requirements 3.3**
        """
        fired = asyncio.Event()

        async def on_expired():
            fired.set()

        timer = IdleTimer(timeout_seconds=0.01, on_expired=on_expired)
        await timer.start()

        try:
            await asyncio.wait_for(fired.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pytest.fail("IdleTimer did not fire async on_expired callback")

        assert fired.is_set()

    # -------------------------------------------------------------------------
    # Test 2d: Graceful stop terminates process (Req 3.4)
    # -------------------------------------------------------------------------

    @given(dummy=st.integers(min_value=0, max_value=100))
    @settings(max_examples=100)
    async def test_stop_server_transitions_to_monitoring(
        self, dummy: int
    ) -> None:
        """stop_server() in RUNNING state calls process_manager.stop_server()
        and transitions state to MONITORING.

        **Validates: Requirements 3.4**
        """
        config = _make_config()
        core = WrapperCore(config)

        # Put the core in RUNNING state
        core._state = ServerState.RUNNING

        # Mock all the dependencies
        core._process_manager = MagicMock()
        core._process_manager.stop_server = AsyncMock(
            return_value=StopResult(success=True, was_forced=False)
        )

        core._rcon_client = MagicMock()
        core._rcon_client.disconnect = AsyncMock()

        core._idle_timer = MagicMock()
        core._idle_timer.cancel = MagicMock()
        core._idle_timer.is_active = MagicMock(return_value=False)

        core._connection_listener = MagicMock()
        core._connection_listener.start_listening = AsyncMock()

        core._rcon_poll_task = None

        # Call stop_server
        result = await core.stop_server()

        # Verify
        assert result.success is True
        assert core._state == ServerState.MONITORING
        core._process_manager.stop_server.assert_called_once()
        core._connection_listener.start_listening.assert_called_once()

    # -------------------------------------------------------------------------
    # Test 2e: Invalid state command rejection (Req 3.5)
    # -------------------------------------------------------------------------

    @given(
        state=st.sampled_from(
            [ServerState.STARTING, ServerState.RUNNING, ServerState.STOPPING]
        )
    )
    @settings(max_examples=100)
    async def test_start_server_rejected_in_non_monitoring_state(
        self, state: ServerState
    ) -> None:
        """start_server() returns error when not in MONITORING state.

        **Validates: Requirements 3.5**
        """
        config = _make_config()
        core = WrapperCore(config)
        core._state = state

        result = await core.start_server()

        assert result.success is False
        assert result.error_message is not None
        # State should not have changed
        assert core._state == state

    @given(
        state=st.sampled_from(
            [ServerState.MONITORING, ServerState.STARTING, ServerState.STOPPING]
        )
    )
    @settings(max_examples=100)
    async def test_stop_server_rejected_in_non_running_state(
        self, state: ServerState
    ) -> None:
        """stop_server() returns error when not in RUNNING state.

        **Validates: Requirements 3.5**
        """
        config = _make_config()
        core = WrapperCore(config)
        core._state = state

        result = await core.stop_server()

        assert result.success is False
        assert result.error_message is not None
        # State should not have changed
        assert core._state == state

    @given(
        state=st.sampled_from([ServerState.STARTING, ServerState.STOPPING])
    )
    @settings(max_examples=100)
    async def test_restart_rejected_in_invalid_state(
        self, state: ServerState
    ) -> None:
        """restart_server() returns error in STARTING or STOPPING states.

        **Validates: Requirements 3.5**
        """
        config = _make_config()
        core = WrapperCore(config)
        core._state = state

        result = await core.restart_server()

        assert result.success is False
        assert result.error_message is not None
        # State should not have changed
        assert core._state == state



