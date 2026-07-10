"""Unit tests for the ConnectionListener class."""

import asyncio

import pytest

from src.connection_listener import ConnectionListener


@pytest.fixture
def callback_tracker():
    """Fixture that tracks callback invocations."""
    calls = []

    def callback():
        calls.append(True)

    return callback, calls


class TestConnectionListenerLifecycle:
    """Tests for listener start/stop lifecycle."""

    async def test_is_listening_false_initially(self, callback_tracker):
        """Listener should not be active before start_listening is called."""
        callback, _ = callback_tracker
        listener = ConnectionListener(on_packet_received=callback, port=19876)
        assert listener.is_listening() is False

    async def test_start_listening_binds_port(self, callback_tracker):
        """After start_listening, is_listening should return True."""
        callback, _ = callback_tracker
        listener = ConnectionListener(on_packet_received=callback, port=19876)
        try:
            await listener.start_listening()
            assert listener.is_listening() is True
        finally:
            await listener.stop_listening()

    async def test_stop_listening_releases_port(self, callback_tracker):
        """After stop_listening, is_listening should return False."""
        callback, _ = callback_tracker
        listener = ConnectionListener(on_packet_received=callback, port=19877)
        await listener.start_listening()
        await listener.stop_listening()
        assert listener.is_listening() is False

    async def test_stop_listening_when_not_started(self, callback_tracker):
        """stop_listening should be a no-op when not currently listening."""
        callback, _ = callback_tracker
        listener = ConnectionListener(on_packet_received=callback, port=19878)
        # Should not raise
        await listener.stop_listening()
        assert listener.is_listening() is False

    async def test_start_listening_twice_is_safe(self, callback_tracker):
        """Calling start_listening when already listening should be idempotent."""
        callback, _ = callback_tracker
        listener = ConnectionListener(on_packet_received=callback, port=19879)
        try:
            await listener.start_listening()
            await listener.start_listening()  # Should not raise
            assert listener.is_listening() is True
        finally:
            await listener.stop_listening()

    async def test_port_released_within_1_second(self, callback_tracker):
        """Port should be reusable within 1 second after stop_listening."""
        callback, _ = callback_tracker
        listener1 = ConnectionListener(on_packet_received=callback, port=19880)
        listener2 = ConnectionListener(on_packet_received=callback, port=19880)

        await listener1.start_listening()
        assert listener1.is_listening() is True

        await listener1.stop_listening()

        # Windows may need a brief moment for OS-level socket cleanup
        await asyncio.sleep(0.1)

        # Should be able to bind within 1 second after release
        await listener2.start_listening()
        assert listener2.is_listening() is True
        await listener2.stop_listening()


class TestConnectionListenerCallback:
    """Tests for packet receipt callback behavior."""

    async def test_callback_invoked_on_packet(self, callback_tracker):
        """Callback should be invoked when a UDP packet is received."""
        callback, calls = callback_tracker
        listener = ConnectionListener(on_packet_received=callback, port=19881)
        try:
            await listener.start_listening()

            # Send a UDP packet to the listener
            loop = asyncio.get_running_loop()
            transport, _ = await loop.create_datagram_endpoint(
                asyncio.DatagramProtocol,
                remote_addr=("127.0.0.1", 19881),
            )
            transport.sendto(b"hello")
            # Give the event loop time to process
            await asyncio.sleep(0.1)
            transport.close()

            assert len(calls) == 1
        finally:
            await listener.stop_listening()

    async def test_callback_invoked_multiple_times(self, callback_tracker):
        """Callback should be invoked for each packet received."""
        callback, calls = callback_tracker
        listener = ConnectionListener(on_packet_received=callback, port=19882)
        try:
            await listener.start_listening()

            loop = asyncio.get_running_loop()
            transport, _ = await loop.create_datagram_endpoint(
                asyncio.DatagramProtocol,
                remote_addr=("127.0.0.1", 19882),
            )
            transport.sendto(b"packet1")
            transport.sendto(b"packet2")
            transport.sendto(b"packet3")
            await asyncio.sleep(0.1)
            transport.close()

            assert len(calls) == 3
        finally:
            await listener.stop_listening()


class TestConnectionListenerErrorHandling:
    """Tests for graceful error handling."""

    async def test_port_in_use_handled_gracefully(self, callback_tracker):
        """Should not raise when port is already in use."""
        callback, _ = callback_tracker
        listener1 = ConnectionListener(on_packet_received=callback, port=19883)
        listener2 = ConnectionListener(on_packet_received=callback, port=19883)
        try:
            await listener1.start_listening()
            assert listener1.is_listening() is True

            # Second listener should fail gracefully
            await listener2.start_listening()
            assert listener2.is_listening() is False
        finally:
            await listener1.stop_listening()
            await listener2.stop_listening()

    async def test_custom_port(self, callback_tracker):
        """Listener should bind to the specified custom port."""
        callback, calls = callback_tracker
        listener = ConnectionListener(on_packet_received=callback, port=19884)
        try:
            await listener.start_listening()
            assert listener.is_listening() is True

            loop = asyncio.get_running_loop()
            transport, _ = await loop.create_datagram_endpoint(
                asyncio.DatagramProtocol,
                remote_addr=("127.0.0.1", 19884),
            )
            transport.sendto(b"test")
            await asyncio.sleep(0.1)
            transport.close()

            assert len(calls) == 1
        finally:
            await listener.stop_listening()
