"""Connection Listener for detecting incoming UDP packets on the game port.

Binds to UDP port 8211 (configurable) and invokes a callback when any packet
is received, signalling that a player is attempting to connect. The listener
releases the port within 1 second when stop_listening() is called so the
Dedicated Server can bind to it.
"""

import asyncio
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class _UdpProtocol(asyncio.DatagramProtocol):
    """Internal asyncio UDP protocol that forwards received datagrams to a callback."""

    def __init__(self, on_packet: Callable[[], None]) -> None:
        self._on_packet = on_packet

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Called when a UDP packet arrives on the bound port."""
        logger.debug("UDP packet received from %s", addr)
        self._on_packet()

    def error_received(self, exc: Exception) -> None:
        """Called when a send/receive operation raises an OS error."""
        logger.warning("UDP protocol error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        """Called when the transport is closed."""
        if exc:
            logger.debug("UDP connection lost: %s", exc)


class ConnectionListener:
    """Listens for incoming UDP packets to detect player connection attempts.

    Uses asyncio's create_datagram_endpoint to bind a UDP socket. When any
    packet arrives, the provided callback is invoked (typically to trigger
    server startup). The socket is released within 1 second when
    stop_listening() is called.
    """

    def __init__(
        self,
        on_packet_received: Callable[[], None],
        port: int = 8211,
        host: str = "0.0.0.0",
        max_bind_attempts: int = 10,
        bind_retry_base_delay: float = 1.0,
        bind_retry_max_delay: float = 8.0,
    ) -> None:
        """Initialize the connection listener.

        Args:
            on_packet_received: Callback invoked when a UDP packet is detected.
            port: UDP port to listen on (default 8211).
            host: Address to bind to (default all interfaces).
            max_bind_attempts: Maximum retry attempts when port bind fails
                (default 10, giving ~55s total wait with capped backoff).
            bind_retry_base_delay: Initial delay in seconds between retries.
            bind_retry_max_delay: Maximum delay cap for exponential backoff.
        """
        self._on_packet_received = on_packet_received
        self._port = port
        self._host = host
        self._max_bind_attempts = max_bind_attempts
        self._bind_retry_base_delay = bind_retry_base_delay
        self._bind_retry_max_delay = bind_retry_max_delay
        self._transport: asyncio.DatagramTransport | None = None
        self._listening = False

    async def start_listening(self) -> None:
        """Bind to the UDP port and begin listening for incoming packets.

        Retries with exponential backoff (capped at bind_retry_max_delay) if
        the port cannot be bound due to an OSError (e.g. port still held by
        the OS after a recent release). The default 10 attempts with 8s cap
        gives ~55s total wait, accommodating Windows taking up to 30-45s to
        fully release a UDP port after a server process exits.
        Raises no exception; logs errors gracefully.
        """
        if self._listening:
            logger.warning("Connection listener is already active")
            return

        loop = asyncio.get_running_loop()

        for attempt in range(1, self._max_bind_attempts + 1):
            try:
                transport, _ = await loop.create_datagram_endpoint(
                    lambda: _UdpProtocol(self._on_packet_received),
                    local_addr=(self._host, self._port),
                    allow_broadcast=False,
                )
                self._transport = transport
                self._listening = True
                logger.info("Connection listener started on %s:%d", self._host, self._port)
                return
            except OSError as e:
                if attempt < self._max_bind_attempts:
                    delay = min(
                        self._bind_retry_base_delay * (2 ** (attempt - 1)),
                        self._bind_retry_max_delay,
                    )
                    logger.warning(
                        "Failed to bind UDP port %d (attempt %d/%d): %s. "
                        "Retrying in %.1fs...",
                        self._port, attempt, self._max_bind_attempts, e, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Failed to bind UDP port %d after %d attempts: %s. "
                        "Port may already be in use.",
                        self._port, self._max_bind_attempts, e,
                    )

    async def stop_listening(self) -> None:
        """Stop listening and release the UDP port within 1 second."""
        if not self._listening or self._transport is None:
            return

        self._transport.close()
        self._transport = None
        self._listening = False
        logger.info("Connection listener stopped, UDP port %d released", self._port)

    def is_listening(self) -> bool:
        """Return whether the listener is currently active."""
        return self._listening
