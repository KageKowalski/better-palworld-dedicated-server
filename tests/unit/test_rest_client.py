"""Unit tests for the RestClient HTTP client module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from src.rest_client import RestClient


class TestRestClientInit:
    """Tests for RestClient initialization."""

    def test_default_parameters(self) -> None:
        client = RestClient()
        assert client._host == "127.0.0.1"
        assert client._port == 8212
        assert client._password == ""
        assert client._base_url == "http://127.0.0.1:8212/v1/api"
        assert client._session is None

    def test_custom_parameters(self) -> None:
        client = RestClient(host="192.168.1.10", port=9000, password="secret")
        assert client._host == "192.168.1.10"
        assert client._port == 9000
        assert client._password == "secret"
        assert client._base_url == "http://192.168.1.10:9000/v1/api"

    def test_session_not_created_on_init(self) -> None:
        client = RestClient(password="test")
        assert client._session is None


class TestEnsureSession:
    """Tests for lazy session creation."""

    async def test_creates_session_on_first_call(self) -> None:
        client = RestClient(password="mypass")
        session = await client._ensure_session()
        assert session is not None
        assert isinstance(session, aiohttp.ClientSession)
        await client.close()

    async def test_reuses_existing_session(self) -> None:
        client = RestClient(password="mypass")
        session1 = await client._ensure_session()
        session2 = await client._ensure_session()
        assert session1 is session2
        await client.close()

    async def test_recreates_closed_session(self) -> None:
        client = RestClient(password="mypass")
        session1 = await client._ensure_session()
        await session1.close()
        session2 = await client._ensure_session()
        assert session2 is not session1
        assert not session2.closed
        await client.close()


class TestRequest:
    """Tests for the _request() helper method."""

    async def test_connection_error_returns_error_tuple(self) -> None:
        client = RestClient(password="test")
        # No server running, so connection will be refused
        success, data, error = await client._request("GET", "/info")
        assert success is False
        assert data is None
        assert error is not None
        assert "Connection error" in error or "Client error" in error
        await client.close()

    async def test_timeout_returns_error_tuple(self) -> None:
        client = RestClient(password="test")
        # Mock the session to raise a timeout
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.closed = False

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(side_effect=TimeoutError())
        mock_session.request.return_value = mock_context

        client._session = mock_session

        success, data, error = await client._request("GET", "/info")
        assert success is False
        assert data is None
        assert "timed out" in error

    async def test_http_401_returns_auth_failure(self) -> None:
        client = RestClient(password="wrongpass")

        mock_response = AsyncMock()
        mock_response.status = 401

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.closed = False
        mock_session.request.return_value = mock_context

        client._session = mock_session

        success, data, error = await client._request("GET", "/info")
        assert success is False
        assert data is None
        assert "Authentication failure" in error or "authentication failure" in error.lower()

    async def test_http_400_returns_response_body(self) -> None:
        client = RestClient(password="test")

        mock_response = AsyncMock()
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Bad request: missing field")

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.closed = False
        mock_session.request.return_value = mock_context

        client._session = mock_session

        success, data, error = await client._request("POST", "/shutdown")
        assert success is False
        assert data is None
        assert "Bad request: missing field" in error

    async def test_http_500_returns_status_and_body(self) -> None:
        client = RestClient(password="test")

        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal server error")

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.closed = False
        mock_session.request.return_value = mock_context

        client._session = mock_session

        success, data, error = await client._request("GET", "/metrics")
        assert success is False
        assert data is None
        assert "500" in error
        assert "Internal server error" in error

    async def test_json_parse_failure_returns_error(self) -> None:
        client = RestClient(password="test")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            side_effect=aiohttp.ContentTypeError(
                MagicMock(), MagicMock(), message="not json"
            )
        )

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.closed = False
        mock_session.request.return_value = mock_context

        client._session = mock_session

        success, data, error = await client._request("GET", "/info")
        assert success is False
        assert data is None
        assert "parse failure" in error.lower() or "JSON" in error

    async def test_successful_request_returns_data(self) -> None:
        client = RestClient(password="test")

        expected_data = {"currentplayernum": 5, "serverfps": 30}
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=expected_data)

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.closed = False
        mock_session.request.return_value = mock_context

        client._session = mock_session

        success, data, error = await client._request("GET", "/metrics")
        assert success is True
        assert data == expected_data
        assert error is None

    async def test_request_uses_correct_url(self) -> None:
        client = RestClient(host="localhost", port=9999, password="pw")

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)

        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        mock_session.closed = False
        mock_session.request.return_value = mock_context

        client._session = mock_session

        await client._request("POST", "/shutdown", json_body={"waittime": 1})
        mock_session.request.assert_called_once_with(
            "POST",
            "http://localhost:9999/v1/api/shutdown",
            json={"waittime": 1},
        )


class TestClose:
    """Tests for session cleanup."""

    async def test_close_releases_session(self) -> None:
        client = RestClient(password="test")
        await client._ensure_session()
        assert client._session is not None
        await client.close()
        assert client._session is None

    async def test_close_when_no_session(self) -> None:
        client = RestClient(password="test")
        # Should not raise
        await client.close()
        assert client._session is None

    async def test_close_when_already_closed(self) -> None:
        client = RestClient(password="test")
        session = await client._ensure_session()
        await session.close()
        # Should not raise even if session was already closed
        await client.close()
