"""RCON client for querying the Palworld Dedicated Server."""

import asyncio
import logging
from rcon.source import Client as RconSourceClient

from src.models import RconQueryResult


logger = logging.getLogger(__name__)


class RconClient:
    """Queries the Palworld Dedicated Server for player information via RCON.

    Uses the Source RCON protocol to connect to the server and issue
    the ShowPlayers command, parsing the CSV-like response to determine
    the current player count.
    """

    def __init__(
        self, host: str = "127.0.0.1", port: int = 25575, password: str = ""
    ) -> None:
        self._host = host
        self._port = port
        self._password = password
        self._client: RconSourceClient | None = None
        self._connected = False

    async def connect(self) -> bool:
        """Establish a connection to the RCON server.

        Returns True on success, False on failure.
        """
        try:
            self._client = RconSourceClient(
                self._host, self._port, passwd=self._password
            )
            # The rcon library's Client uses synchronous sockets, so we
            # run connect+login in a thread to avoid blocking the event loop.
            await asyncio.to_thread(self._client.connect, True)
            self._connected = True
            logger.info("RCON connected to %s:%d", self._host, self._port)
            return True
        except Exception as e:
            logger.error("RCON connection failed: %s", e)
            self._connected = False
            self._client = None
            return False

    async def query_players(self) -> RconQueryResult:
        """Query the server for connected players.

        Sends the ShowPlayers command and parses the CSV-like response.
        Returns an RconQueryResult with the player count on success,
        or error information on failure.
        """
        if not self._connected or self._client is None:
            return RconQueryResult(
                success=False, error_message="RCON not connected"
            )

        try:
            response = await asyncio.to_thread(
                self._client.run, "ShowPlayers", enforce_id=False
            )
            player_count = self._parse_player_response(response)
            return RconQueryResult(success=True, player_count=player_count)
        except Exception as e:
            logger.error("RCON query failed: %s", e)
            self._connected = False
            return RconQueryResult(
                success=False, error_message=f"RCON query failed: {e}"
            )

    async def send_command(self, command: str) -> str | None:
        """Send an arbitrary RCON command to the server.

        Args:
            command: The RCON command string to send.

        Returns:
            The server's response string on success, None on failure.
        """
        if not self._connected or self._client is None:
            logger.warning("Cannot send RCON command: not connected")
            return None

        try:
            response = await asyncio.to_thread(
                self._client.run, command, enforce_id=False
            )
            return response
        except Exception as e:
            logger.error("RCON command '%s' failed: %s", command, e)
            self._connected = False
            return None

    async def disconnect(self) -> None:
        """Close the RCON connection."""
        if self._client is not None:
            try:
                await asyncio.to_thread(self._client.close)
            except Exception as e:
                logger.warning("Error closing RCON connection: %s", e)
            finally:
                self._client = None
                self._connected = False
                logger.info("RCON disconnected")

    @staticmethod
    def _parse_player_response(response: str) -> int:
        """Parse the ShowPlayers CSV-like response and return the player count.

        The response format is:
            name,playeruid,steamid
            PlayerName,12345,67890
            ...

        Player count is the number of non-empty lines after the header line.
        An empty response or a response with only a header returns 0.
        """
        if not response or not response.strip():
            return 0

        lines = response.strip().splitlines()

        # Filter out empty lines
        non_empty_lines = [line for line in lines if line.strip()]

        if len(non_empty_lines) <= 1:
            # Only header or empty
            return 0

        # Subtract the header line
        return len(non_empty_lines) - 1
