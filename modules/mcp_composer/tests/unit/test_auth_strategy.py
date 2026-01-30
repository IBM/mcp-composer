from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from mcp_composer.core.utils.auth_strategy import get_client


class TestAuthStrategy:
    """Test cases for auth strategy module."""

    @pytest.mark.asyncio
    async def test_get_client_no_auth(self):
        """Test getting client with no authentication."""
        auth_config = {}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_dynamic_bearer(self):
        """Test getting client with DYNAMIC_BEARER authentication."""
        auth_config = {
            "auth_strategy": "dynamic_bearer",
            "auth": {
                "token_url": "https://example.com/token",
                "apikey": "test_api_key",
            },
        }

        with patch(
            "mcp_composer.core.utils.auth_strategy.DynamicTokenClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_bearer(self):
        """Test getting client with BEARER authentication."""
        auth_config = {"auth_strategy": "bearer", "auth": {"token": "test_token"}}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_apitoken(self):
        """Test getting client with APITOKEN authentication."""
        auth_config = {
            "auth_strategy": "apiToken",
            "auth": {"auth_prefix": "ApiKey", "token": "test_token"},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_jsessionid(self):
        """Test getting client with JSESSIONID authentication."""
        auth_config = {
            "auth_strategy": "jessionid",
            "auth": {
                "login_url": "/login",
                "username": "test_user",
                "password": "test_password",
            },
        }

        with patch(
            "mcp_composer.core.utils.auth_strategy.DynamicTokenManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_client = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.get_authenticated_http_client_for_jessonid = AsyncMock(
                return_value=mock_client
            )

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_manager_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_basic(self):
        """Test getting client with BASIC authentication."""
        auth_config = {
            "auth_strategy": "basic",
            "auth": {"username": "test_user", "password": "test_password"},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_basic_missing_credentials(self):
        """Test getting client with BASIC authentication but missing credentials."""
        auth_config = {
            "auth_strategy": "basic",
            "auth": {},
            # Missing username and password
        }

        with pytest.raises(
            ValueError, match="username and password are required for BASIC strategy"
        ):
            await get_client("https://example.com", auth_config)

    @pytest.mark.asyncio
    async def test_get_client_bearer_missing_token(self):
        """Test getting client with BEARER authentication but missing token."""
        auth_config = {
            "auth_strategy": "bearer",
            "auth": {},
            # Missing token
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_apitoken_missing_token(self):
        """Test getting client with APITOKEN authentication but missing token."""
        auth_config = {
            "auth_strategy": "apiToken",
            "auth": {},
            # Missing token
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_client_class.return_value = mock_client
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_jsessionid_missing_token(self):
        """Test getting client with JSESSIONID authentication but missing token."""
        auth_config = {
            "auth_strategy": "jessionid",
            "auth": {},
            # Missing token
        }

        with patch(
            "mcp_composer.core.utils.auth_strategy.DynamicTokenManager"
        ) as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_manager.get_authenticated_http_client_for_jessonid = AsyncMock(
                return_value=None
            )

            with pytest.raises(
                RuntimeError,
                match="Failed to get authenticated HTTP client for JSESSIONID",
            ):
                await get_client("https://example.com", auth_config)

    @pytest.mark.asyncio
    async def test_get_client_dynamic_bearer_missing_params(self):
        """Test getting client with DYNAMIC_BEARER authentication but missing parameters."""
        auth_config = {
            "auth_strategy": "dynamic_bearer",
            "auth": {},
            # Missing token_url, client_id, client_secret
        }

        with patch(
            "mcp_composer.core.utils.auth_strategy.DynamicTokenClient"
        ) as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_unknown_strategy(self):
        """Test getting client with unknown authentication strategy."""
        auth_config = {"auth_strategy": "UNKNOWN_STRATEGY"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_with_timeout(self):
        """Test getting client with timeout configuration."""
        auth_config = {"timeout": 30}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_with_headers(self):
        """Test getting client with custom headers."""
        auth_config = {
            "headers": {"User-Agent": "TestClient/1.0", "Accept": "application/json"}
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_with_verify_ssl(self):
        """Test getting client with SSL verification disabled."""
        auth_config = {"verify": False}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_comprehensive_config(self):
        """Test getting client with comprehensive configuration."""
        auth_config = {
            "auth_strategy": "bearer",
            "auth": {"token": "test_token"},
            "timeout": 60,
            "headers": {"User-Agent": "TestClient/1.0"},
            "verify": True,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_empty_config(self):
        """Test getting client with empty configuration."""
        auth_config = {}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_none_config(self):
        """Test getting client with None configuration."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", None)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_case_insensitive_strategy(self):
        """Test getting client with case insensitive strategy names."""
        auth_config = {
            "auth_strategy": "bearer",  # lowercase
            "auth": {"token": "test_token"},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_with_proxy(self):
        """Test getting client with proxy configuration."""
        auth_config = {
            "proxies": {
                "http": "http://proxy.example.com:8080",
                "https": "https://proxy.example.com:8080",
            }
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_with_custom_transport(self):
        """Test getting client with custom transport configuration."""
        auth_config = {"transport": "custom_transport"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = await get_client("https://example.com", auth_config)

            assert result == mock_client
            mock_client_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_error_handling(self):
        """Test error handling in get_client function."""
        auth_config = {"auth_strategy": "bearer", "auth": {"token": "test_token"}}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.side_effect = Exception("Connection error")

            with pytest.raises(Exception) as exc_info:
                await get_client("https://example.com", auth_config)
            assert "Connection error" in str(exc_info.value)
