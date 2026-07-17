"""HTTP client for the Palworld Dedicated Server REST API."""

import logging

import aiohttp

from src.models import (
    AnnounceResult,
    InfoResult,
    MetricsResult,
    PlayerInfo,
    PlayersResult,
    ShutdownResult,
    StopResult,
)

logger = logging.getLogger(__name__)


class RestClient:
    """HTTP client for the Palworld Dedicated Server REST API.

    Uses aiohttp.ClientSession for connection pooling and native async I/O.
    All methods return typed result dataclasses — never raise on expected failures.
    """

    def __init__(
        self, host: str = "127.0.0.1", port: int = 8212, password: str = ""
    ) -> None:
        """Initialize the REST client.

        Args:
            host: Server hostname (always localhost).
            port: REST API port (default 8212).
            password: Admin password for Basic Auth.
        """
        self._host = host
        self._port = port
        self._password = password
        self._base_url = f"http://{host}:{port}/v1/api"
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Create the aiohttp session lazily on first use.

        Returns:
            The active ClientSession configured with Basic Auth and timeout.
        """
        if self._session is None or self._session.closed:
            auth = aiohttp.BasicAuth("admin", self._password)
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(
                auth=auth,
                timeout=timeout,
            )
        return self._session

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
    ) -> tuple[bool, dict | None, str | None]:
        """Send an HTTP request and handle all error cases.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path relative to base URL (e.g., "/info").
            json_body: Optional JSON body for POST requests.

        Returns:
            A tuple of (success, data, error_message):
                - On success: (True, parsed_json_dict, None)
                - On failure: (False, None, error_description)
        """
        url = f"{self._base_url}{path}"

        try:
            session = await self._ensure_session()
            async with session.request(method, url, json=json_body) as response:
                if response.status == 401:
                    logger.warning("REST API authentication failure for %s %s", method, path)
                    return (False, None, "Authentication failure: invalid admin password")

                if response.status == 400:
                    body = await response.text()
                    logger.warning("REST API bad request for %s %s: %s", method, path, body)
                    return (False, None, body)

                if response.status != 200:
                    body = await response.text()
                    logger.warning(
                        "REST API unexpected status %d for %s %s: %s",
                        response.status, method, path, body,
                    )
                    return (False, None, f"HTTP {response.status}: {body}")

                try:
                    data = await response.json()
                except (aiohttp.ContentTypeError, ValueError) as e:
                    logger.warning("REST API JSON parse failure for %s %s: %s", method, path, e)
                    return (False, None, f"JSON parse failure: {e}")

                return (True, data, None)

        except aiohttp.ClientConnectionError as e:
            logger.debug("REST API connection error for %s %s: %s", method, path, e)
            return (False, None, f"Connection error: {e}")

        except TimeoutError:
            logger.debug("REST API timeout for %s %s", method, path)
            return (False, None, "Request timed out")

        except aiohttp.ClientError as e:
            logger.debug("REST API client error for %s %s: %s", method, path, e)
            return (False, None, f"Client error: {e}")

    async def get_info(self) -> InfoResult:
        """GET /v1/api/info — used for connectivity check.

        Returns:
            InfoResult with server version, name, description on success.
        """
        success, data, error = await self._request("GET", "/info")
        if not success:
            return InfoResult(success=False, error_message=error)
        return InfoResult(
            success=True,
            version=data.get("version", ""),
            server_name=data.get("servername", ""),
            description=data.get("description", ""),
        )

    async def get_metrics(self) -> MetricsResult:
        """GET /v1/api/metrics — player count and server metrics.

        Returns:
            MetricsResult with currentplayernum clamped to min 0 on success.
        """
        success, data, error = await self._request("GET", "/metrics")
        if not success:
            return MetricsResult(success=False, error_message=error)
        player_count = max(0, data.get("currentplayernum", 0))
        return MetricsResult(success=True, player_count=player_count)

    async def get_players(self) -> PlayersResult:
        """GET /v1/api/players — detailed player list.

        Returns:
            PlayersResult with list of PlayerInfo objects on success.
        """
        success, data, error = await self._request("GET", "/players")
        if not success:
            return PlayersResult(success=False, error_message=error)
        players = []
        for p in data.get("players", []):
            players.append(
                PlayerInfo(
                    name=p.get("name", ""),
                    playerid=p.get("playerid", ""),
                    userid=p.get("userid", ""),
                    ip=p.get("ip", ""),
                    ping=float(p.get("ping", 0.0)),
                    location_x=float(p.get("location_x", 0.0)),
                    location_y=float(p.get("location_y", 0.0)),
                    level=int(p.get("level", 0)),
                )
            )
        return PlayersResult(success=True, players=players)

    async def announce(self, message: str) -> AnnounceResult:
        """POST /v1/api/announce — broadcast message to players.

        Truncates message to 256 characters before sending.

        Args:
            message: Broadcast text (max 256 chars, truncated if longer).

        Returns:
            AnnounceResult indicating success or failure.
        """
        truncated = message[:256]
        success, data, error = await self._request(
            "POST", "/announce", json_body={"message": truncated}
        )
        if not success:
            return AnnounceResult(success=False, error_message=error)
        return AnnounceResult(success=True)

    async def shutdown(
        self, waittime: int = 1, message: str = "Server shutting down"
    ) -> ShutdownResult:
        """POST /v1/api/shutdown — graceful server shutdown.

        Args:
            waittime: Seconds the server waits before shutting down.
            message: Shutdown message sent to players.

        Returns:
            ShutdownResult indicating success or failure.
        """
        success, data, error = await self._request(
            "POST", "/shutdown", json_body={"waittime": waittime, "message": message}
        )
        if not success:
            return ShutdownResult(success=False, error_message=error)
        return ShutdownResult(success=True)

    async def stop(self) -> StopResult:
        """POST /v1/api/stop — force stop.

        Returns:
            StopResult indicating success or failure.
        """
        success, data, error = await self._request("POST", "/stop")
        if not success:
            return StopResult(success=False, error_message=error)
        return StopResult(success=True)

    async def close(self) -> None:
        """Close the underlying aiohttp session and release resources."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("REST client session closed")
