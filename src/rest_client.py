"""HTTP client for the Palworld Dedicated Server REST API."""

import logging

import aiohttp

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

    async def close(self) -> None:
        """Close the underlying aiohttp session and release resources."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None
            logger.debug("REST client session closed")
