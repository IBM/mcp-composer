"""Test module for dynamic_token_manager.py"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from mcp_composer.core.auth_handler.dynamic_token_manager import DynamicTokenManager
from mcp_composer.core.utils import AuthStrategy, ConfigKey


class TestDynamicTokenManager:
    """Test cases for DynamicTokenManager"""

    @pytest.fixture
    def mock_manager(self):
        """Create a mock DynamicTokenManager without auth strategy"""
        return DynamicTokenManager(base_url="https://api.example.com")

    @pytest.fixture
    def mock_manager_jsessionid(self):
        """Create a mock DynamicTokenManager with JSESSIONID auth strategy"""
        return DynamicTokenManager(
            base_url="https://api.example.com",
            **{
                ConfigKey.AUTH_STRATEGY: AuthStrategy.JSESSIONID,
                ConfigKey.LOGIN_URL: "/login",
                ConfigKey.USERNAME: "testuser",
                ConfigKey.PASSWORD: "testpass",
            },
        )

    def test_dynamic_token_manager_initialization(self, mock_manager):
        """Test DynamicTokenManager initialization without auth strategy"""
        assert mock_manager.auth_strategy is None
        assert not hasattr(mock_manager, "login_url")
        assert not hasattr(mock_manager, "username")
        assert not hasattr(mock_manager, "password")

    def test_dynamic_token_manager_initialization_jsessionid(
        self, mock_manager_jsessionid
    ):
        """Test DynamicTokenManager initialization with JSESSIONID auth strategy"""
        assert mock_manager_jsessionid.auth_strategy == AuthStrategy.JSESSIONID
        assert mock_manager_jsessionid.login_url == "/login"
        assert mock_manager_jsessionid.username == "testuser"
        assert mock_manager_jsessionid.password == "testpass"

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_for_jessonid_success(
        self, mock_manager_jsessionid
    ):
        """Test successful JSESSIONID authentication"""
        mock_response = Mock()
        mock_response.cookies = {"JSESSIONID": "test-session-id"}
        mock_response.raise_for_status.return_value = None

        mock_temp_client = AsyncMock()
        mock_temp_client.post.return_value = mock_response
        mock_temp_client.base_url = "https://api.example.com"

        mock_authenticated_client = Mock(spec=httpx.AsyncClient)

        with patch("httpx.AsyncClient") as mock_client_class:
            # Configure the mock to return different objects for different calls
            mock_client_class.side_effect = [
                mock_temp_client,
                mock_authenticated_client,
            ]

            with patch.object(
                mock_temp_client, "__aenter__", return_value=mock_temp_client
            ):
                with patch.object(mock_temp_client, "__aexit__", return_value=None):
                    result = (
                        await mock_manager_jsessionid.get_authenticated_http_client_for_jessonid()
                    )

                    assert result is not None
                    assert result == mock_authenticated_client

                    # Verify login request was made
                    mock_temp_client.post.assert_called_once_with(
                        "/login",
                        data={
                            ConfigKey.USERNAME: "testuser",
                            ConfigKey.PASSWORD: "testpass",
                        },
                        timeout=10.0,
                    )

                    # Verify client was created with correct parameters
                    assert mock_client_class.call_count == 2
                    # First call for temp client (TLS verify on by default)
                    mock_client_class.assert_any_call(
                        base_url="https://api.example.com",
                        follow_redirects=True,
                        verify=True,
                    )
                    # Second call for authenticated client
                    mock_client_class.assert_any_call(
                        base_url="https://api.example.com",
                        headers={"Cookie": "JSESSIONID=test-session-id"},
                        verify=True,
                    )

    @pytest.mark.asyncio
    async def test_jsessionid_can_opt_out_of_ssl_verify(self):
        """Lab/dev may pass verify=False; default remains True."""
        manager = DynamicTokenManager(
            base_url="https://api.example.com",
            **{
                ConfigKey.AUTH_STRATEGY: AuthStrategy.JSESSIONID,
                ConfigKey.LOGIN_URL: "/login",
                ConfigKey.USERNAME: "testuser",
                ConfigKey.PASSWORD: "testpass",
                "verify": False,
            },
        )
        assert manager.verify is False

        mock_response = Mock()
        mock_response.cookies = {"JSESSIONID": "test-session-id"}
        mock_response.raise_for_status.return_value = None
        mock_temp_client = AsyncMock()
        mock_temp_client.post.return_value = mock_response
        mock_temp_client.base_url = "https://api.example.com"
        mock_authenticated_client = Mock(spec=httpx.AsyncClient)

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.side_effect = [
                mock_temp_client,
                mock_authenticated_client,
            ]
            with patch.object(
                mock_temp_client, "__aenter__", return_value=mock_temp_client
            ), patch.object(mock_temp_client, "__aexit__", return_value=None):
                result = await manager.get_authenticated_http_client_for_jessonid()

        assert result == mock_authenticated_client
        mock_client_class.assert_any_call(
            base_url="https://api.example.com",
            follow_redirects=True,
            verify=False,
        )

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_missing_credentials(
        self, mock_manager_jsessionid
    ):
        """Test JSESSIONID authentication with missing credentials"""
        mock_manager_jsessionid.username = None

        result = (
            await mock_manager_jsessionid.get_authenticated_http_client_for_jessonid()
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_missing_login_url(
        self, mock_manager_jsessionid
    ):
        """Test JSESSIONID authentication with missing login URL"""
        mock_manager_jsessionid.login_url = None

        result = (
            await mock_manager_jsessionid.get_authenticated_http_client_for_jessonid()
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_missing_password(
        self, mock_manager_jsessionid
    ):
        """Test JSESSIONID authentication with missing password"""
        mock_manager_jsessionid.password = None

        result = (
            await mock_manager_jsessionid.get_authenticated_http_client_for_jessonid()
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_http_error(
        self, mock_manager_jsessionid
    ):
        """Test JSESSIONID authentication with HTTP error"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=Mock(), response=mock_response
        )
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_temp_client = AsyncMock()
        mock_temp_client.post.return_value = mock_response
        mock_temp_client.base_url = "https://api.example.com"

        with patch("httpx.AsyncClient", return_value=mock_temp_client):
            with patch.object(
                mock_temp_client, "__aenter__", return_value=mock_temp_client
            ):
                with patch.object(mock_temp_client, "__aexit__", return_value=None):
                    result = (
                        await mock_manager_jsessionid.get_authenticated_http_client_for_jessonid()
                    )

                    assert result is None

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_request_error(
        self, mock_manager_jsessionid
    ):
        """Test JSESSIONID authentication with request error"""
        mock_temp_client = AsyncMock()
        mock_temp_client.post.side_effect = httpx.RequestError("Connection failed")
        mock_temp_client.base_url = "https://api.example.com"

        with patch("httpx.AsyncClient", return_value=mock_temp_client):
            with patch.object(
                mock_temp_client, "__aenter__", return_value=mock_temp_client
            ):
                with patch.object(mock_temp_client, "__aexit__", return_value=None):
                    result = (
                        await mock_manager_jsessionid.get_authenticated_http_client_for_jessonid()
                    )

                    assert result is None

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_timeout_error(
        self, mock_manager_jsessionid
    ):
        """Test JSESSIONID authentication with timeout error"""
        mock_temp_client = AsyncMock()
        mock_temp_client.post.side_effect = asyncio.TimeoutError()
        mock_temp_client.base_url = "https://api.example.com"

        with patch("httpx.AsyncClient", return_value=mock_temp_client):
            with patch.object(
                mock_temp_client, "__aenter__", return_value=mock_temp_client
            ):
                with patch.object(mock_temp_client, "__aexit__", return_value=None):
                    result = (
                        await mock_manager_jsessionid.get_authenticated_http_client_for_jessonid()
                    )

                    assert result is None

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_unexpected_error(
        self, mock_manager_jsessionid
    ):
        """Test JSESSIONID authentication with unexpected error"""
        mock_temp_client = AsyncMock()
        mock_temp_client.post.side_effect = Exception("Unexpected error")
        mock_temp_client.base_url = "https://api.example.com"

        with patch("httpx.AsyncClient", return_value=mock_temp_client):
            with patch.object(
                mock_temp_client, "__aenter__", return_value=mock_temp_client
            ):
                with patch.object(mock_temp_client, "__aexit__", return_value=None):
                    result = (
                        await mock_manager_jsessionid.get_authenticated_http_client_for_jessonid()
                    )

                    assert result is None

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_no_jsessionid(
        self, mock_manager_jsessionid
    ):
        """Test JSESSIONID authentication when no JSESSIONID is returned"""
        mock_response = Mock()
        mock_response.cookies = {}  # No JSESSIONID
        mock_response.raise_for_status.return_value = None

        mock_temp_client = AsyncMock()
        mock_temp_client.post.return_value = mock_response
        mock_temp_client.base_url = "https://api.example.com"

        with patch("httpx.AsyncClient", return_value=mock_temp_client):
            with patch.object(
                mock_temp_client, "__aenter__", return_value=mock_temp_client
            ):
                with patch.object(mock_temp_client, "__aexit__", return_value=None):
                    with pytest.raises(
                        ValueError, match="JSESSIONID not found — login failed."
                    ):
                        await mock_manager_jsessionid.get_authenticated_http_client_for_jessonid()

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_jsessionid_none(
        self, mock_manager_jsessionid
    ):
        """Test JSESSIONID authentication when JSESSIONID is None"""
        mock_response = Mock()
        mock_response.cookies = {"JSESSIONID": None}  # JSESSIONID is None
        mock_response.raise_for_status.return_value = None

        mock_temp_client = AsyncMock()
        mock_temp_client.post.return_value = mock_response
        mock_temp_client.base_url = "https://api.example.com"

        with patch("httpx.AsyncClient", return_value=mock_temp_client):
            with patch.object(
                mock_temp_client, "__aenter__", return_value=mock_temp_client
            ):
                with patch.object(mock_temp_client, "__aexit__", return_value=None):
                    with pytest.raises(
                        ValueError, match="JSESSIONID not found — login failed."
                    ):
                        await mock_manager_jsessionid.get_authenticated_http_client_for_jessonid()

    def test_dynamic_token_manager_inheritance(self, mock_manager):
        """Test that DynamicTokenManager inherits from httpx.AsyncClient"""
        assert isinstance(mock_manager, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_get_authenticated_http_client_not_jsessionid_strategy(
        self, mock_manager
    ):
        """Test that non-JSESSIONID strategy returns None"""
        result = await mock_manager.get_authenticated_http_client_for_jessonid()
        assert result is None
