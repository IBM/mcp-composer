"""Test module for dynamic_token_client.py"""

import time
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from mcp_composer.core.auth_handler.dynamic_token_client import (
    DynamicTokenClient,
    DynamicTokenClientOAuth,
    DEFAULT_TOKEN_EXPIRY,
    TOKEN_REFRESH_BUFFER,
)
from mcp_composer.core.utils import AuthStrategy, ConfigKey

# pylint: disable=protected-access


class TestDynamicTokenClientOAuth:
    """Test cases for DynamicTokenClientOAuth"""

    def test_oauth_initialization(self):
        """Test DynamicTokenClientOAuth initialization"""
        oauth = DynamicTokenClientOAuth(access_token="test-token")
        assert oauth._access_token == "test-token"
        assert oauth._auth_prefix == "Bearer"

    def test_oauth_initialization_with_prefix(self):
        """Test DynamicTokenClientOAuth initialization with custom prefix"""
        oauth = DynamicTokenClientOAuth(access_token="test-token", auth_prefix="Custom")
        assert oauth._access_token == "test-token"
        assert oauth._auth_prefix == "Custom"

    def test_oauth_auth_flow(self):
        """Test DynamicTokenClientOAuth auth_flow"""
        oauth = DynamicTokenClientOAuth(access_token="test-token")
        request = Mock()
        request.headers = {}

        # Get the generator from auth_flow and consume it
        flow = oauth.auth_flow(request)
        result = next(flow)

        assert request.headers["Authorization"] == "Bearer test-token"
        assert result == request

    def test_oauth_auth_flow_with_custom_prefix(self):
        """Test DynamicTokenClientOAuth auth_flow with custom prefix"""
        oauth = DynamicTokenClientOAuth(access_token="test-token", auth_prefix="Token")
        request = Mock()
        request.headers = {}

        flow = oauth.auth_flow(request)
        result = next(flow)

        assert request.headers["Authorization"] == "Token test-token"
        assert result == request


class TestDynamicTokenClient:
    """Test cases for DynamicTokenClient"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock DynamicTokenClient"""
        auth_data = {
            ConfigKey.Token_URL: "https://auth.example.com/token",
            ConfigKey.APIKEY: "test-api-key",
            ConfigKey.TOKEN_GEN_AUTH_METHOD: "jwt",
        }
        return DynamicTokenClient(
            base_url="https://api.example.com",
            auth_data=auth_data,
        )

    @pytest.fixture
    def mock_client_iam(self):
        """Create a mock DynamicTokenClient with IAM media type"""
        auth_data = {
            ConfigKey.Token_URL: "https://auth.example.com/token",
            ConfigKey.APIKEY: "test-api-key",
            ConfigKey.TOKEN_GEN_AUTH_METHOD: "iam",
        }
        return DynamicTokenClient(
            base_url="https://api.example.com",
            auth_data=auth_data,
        )

    @pytest.fixture
    def mock_client_basic_auth(self):
        """Create a mock DynamicTokenClient with Basic auth"""
        auth_data = {
            ConfigKey.Token_URL: "https://auth.example.com/token",
            ConfigKey.ID: "test-id",
            ConfigKey.SECRET: "test-secret",
            ConfigKey.TOKEN_GEN_AUTH_METHOD: AuthStrategy.BASIC,
        }
        return DynamicTokenClient(
            base_url="https://api.example.com",
            auth_data=auth_data,
        )

    @pytest.fixture
    def mock_client_with_auth_prefix(self):
        """Create a mock DynamicTokenClient with custom auth_prefix"""
        auth_data = {
            ConfigKey.Token_URL: "https://auth.example.com/token",
            ConfigKey.APIKEY: "test-api-key",
            ConfigKey.TOKEN_GEN_AUTH_METHOD: "jwt",
            "auth_prefix": "Token",
        }
        return DynamicTokenClient(
            base_url="https://api.example.com",
            auth_data=auth_data,
        )

    def test_dynamic_token_client_initialization(self, mock_client):
        """Test DynamicTokenClient initialization"""
        assert (
            mock_client.auth_data[ConfigKey.Token_URL]
            == "https://auth.example.com/token"
        )
        assert mock_client.auth_data[ConfigKey.APIKEY] == "test-api-key"
        assert mock_client.auth_data[ConfigKey.TOKEN_GEN_AUTH_METHOD] == "jwt"
        assert mock_client._access_token is None
        assert mock_client._expires_at == 0
        assert mock_client._auth_prefix == "Bearer"

    def test_dynamic_token_client_initialization_with_auth_prefix(
        self, mock_client_with_auth_prefix
    ):
        """Test DynamicTokenClient initialization with custom auth_prefix"""
        assert mock_client_with_auth_prefix._auth_prefix == "Token"

    def test_dynamic_token_client_initialization_iam(self, mock_client_iam):
        """Test DynamicTokenClient initialization with IAM media type"""
        assert mock_client_iam.auth_data[ConfigKey.TOKEN_GEN_AUTH_METHOD] == "iam"

    def test_dynamic_token_client_initialization_invalid_base_url(self):
        """Test DynamicTokenClient initialization with invalid base_url"""
        with pytest.raises(ValueError, match="base_url cannot be empty"):
            DynamicTokenClient(base_url="")

    def test_dynamic_token_client_initialization_invalid_timeout(self):
        """Test DynamicTokenClient initialization with invalid timeout"""
        with pytest.raises(ValueError, match="timeout must be positive"):
            DynamicTokenClient(
                base_url="https://api.example.com",
                timeout=-1,
            )

    def test_dynamic_token_client_initialization_with_headers(self):
        """Test DynamicTokenClient initialization with custom headers"""
        custom_headers = {"X-Custom": "value"}
        auth_data = {
            ConfigKey.Token_URL: "https://auth.example.com/token",
            ConfigKey.APIKEY: "test-api-key",
            ConfigKey.TOKEN_GEN_AUTH_METHOD: "jwt",
        }
        client = DynamicTokenClient(
            base_url="https://api.example.com",
            auth_data=auth_data,
            headers=custom_headers,
        )
        assert client.headers["X-Custom"] == "value"

    @pytest.mark.asyncio
    async def test_refresh_token_json_success(self, mock_client):
        """Test successful token refresh with JSON media type"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            await mock_client._refresh_token()

            assert mock_client._access_token == "new-token"
            # Check that expiry is set with buffer
            expected_expires_at = time.time() + 3600 - TOKEN_REFRESH_BUFFER
            assert abs(mock_client._expires_at - expected_expires_at) < 1

    @pytest.mark.asyncio
    async def test_refresh_token_iam_success(self, mock_client_iam):
        """Test successful token refresh with IAM media type"""
        mock_response = Mock()
        mock_response.json.return_value = {"token": "new-token", "expires_in": 3600}
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            await mock_client_iam._refresh_token()

            assert mock_client_iam._access_token == "new-token"
            expected_expires_at = time.time() + 3600 - TOKEN_REFRESH_BUFFER
            assert abs(mock_client_iam._expires_at - expected_expires_at) < 1

    @pytest.mark.asyncio
    async def test_refresh_token_basic_auth_success(self, mock_client_basic_auth):
        """Test successful token refresh with BASIC auth"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            await mock_client_basic_auth._refresh_token()

            assert mock_client_basic_auth._access_token == "new-token"

    @pytest.mark.asyncio
    async def test_refresh_token_missing_apikey(self, mock_client):
        """Test token refresh with missing apikey"""
        mock_client.auth_data[ConfigKey.APIKEY] = None

        with pytest.raises(
            ValueError,
            match="Either apikey, \\(id and secret\\), or \\(client_id, client_secret, refresh_token\\) must be provided in auth_data\\.",
        ):
            await mock_client._refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_token_missing_token_url(self, mock_client):
        """Test token refresh with missing token_url"""
        mock_client.auth_data[ConfigKey.Token_URL] = None

        with pytest.raises(
            ValueError,
            match="token_url must be provided in auth_data\\.",
        ):
            await mock_client._refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_token_missing_auth_data(self):
        """Test token refresh with missing auth_data"""
        client = DynamicTokenClient(base_url="https://api.example.com")

        with pytest.raises(
            ValueError,
            match="Missing auth_data for token refresh\\.",
        ):
            await client._refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_token_http_error_with_no_token(self, mock_client):
        """Test token refresh with HTTP error and no token in response"""
        mock_response = Mock()
        mock_response.json.return_value = {"error": "unauthorized"}
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=Mock(), response=mock_response
        )

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with pytest.raises(httpx.HTTPStatusError):
                await mock_client._refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_token_http_error_with_token_in_response(self, mock_client):
        """Test token refresh with HTTP error but token in error response"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "error-token",
            "expires_in": 3600,
        }
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        http_error = httpx.HTTPStatusError(
            "401", request=Mock(), response=mock_response
        )

        with patch("httpx.AsyncClient.post", side_effect=http_error):
            await mock_client._refresh_token()

            # Should still set token even with 401
            assert mock_client._access_token == "error-token"

    @pytest.mark.asyncio
    async def test_refresh_token_request_error(self, mock_client):
        """Test token refresh with request error"""
        with patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.RequestError("Connection failed"),
        ):
            with pytest.raises(httpx.RequestError):
                await mock_client._refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_token_uses_default_expiry(self, mock_client):
        """Test token refresh uses default expiry when not provided"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-token",
        }
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            await mock_client._refresh_token()

            assert mock_client._access_token == "new-token"
            expected_expires_at = (
                time.time() + DEFAULT_TOKEN_EXPIRY - TOKEN_REFRESH_BUFFER
            )
            assert abs(mock_client._expires_at - expected_expires_at) < 1

    @pytest.mark.asyncio
    async def test_refresh_token_oauth_refresh_grant(self):
        """Test token refresh using OAuth refresh_token grant (dynamic_bearer with refresh token)"""
        auth_data = {
            ConfigKey.Token_URL: "https://auth.example.com/oauth/token",
            ConfigKey.CLIENT_ID: "client-id",
            ConfigKey.CLIENT_SECRET: "client-secret",
            ConfigKey.REFRESH_TOKEN: "refresh-token-123",
        }
        client = DynamicTokenClient(
            base_url="https://api.example.com",
            auth_data=auth_data,
        )
        with patch(
            "mcp_composer.core.auth_handler.dynamic_token_client.refresh_access_token",
            new_callable=AsyncMock,
            return_value="oauth-access-token",
        ) as mock_refresh:
            await client._refresh_token()
            mock_refresh.assert_called_once_with(
                client_id="client-id",
                client_secret="client-secret",
                token_url="https://auth.example.com/oauth/token",
                refresh_token="refresh-token-123",
                scope=None,
            )
            assert client._access_token == "oauth-access-token"
            expected_expires_at = (
                time.time() + DEFAULT_TOKEN_EXPIRY - TOKEN_REFRESH_BUFFER
            )
            assert abs(client._expires_at - expected_expires_at) < 1

    @pytest.mark.asyncio
    async def test_request_with_valid_token(self, mock_client):
        """Test request with valid token"""
        mock_client._access_token = "valid-token"
        mock_client._expires_at = time.time() + 3600  # Valid for 1 hour

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None

        with patch(
            "httpx.AsyncClient.request", return_value=mock_response
        ) as mock_super_request:
            await mock_client.request("GET", "https://api.example.com/data")

            # Verify super().request was called with Authorization header
            mock_super_request.assert_called_once()
            call_args = mock_super_request.call_args
            assert call_args[0][0] == "GET"
            assert call_args[0][1] == "https://api.example.com/data"
            assert call_args[1]["headers"]["Authorization"] == "Bearer valid-token"
            assert call_args[1]["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_request_with_expired_token(self, mock_client):
        """Test request with expired token triggers refresh"""
        mock_client._access_token = "old-token"
        mock_client._expires_at = time.time() - 1  # Expired

        mock_token_response = Mock()
        mock_token_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_token_response.status_code = 200
        mock_token_response.raise_for_status.return_value = None

        mock_data_response = Mock()
        mock_data_response.raise_for_status.return_value = None

        with (
            patch("httpx.AsyncClient.post", return_value=mock_token_response),
            patch(
                "httpx.AsyncClient.request", return_value=mock_data_response
            ) as mock_super_request,
        ):
            await mock_client.request("GET", "https://api.example.com/data")

            # Verify token was refreshed
            assert mock_client._access_token == "new-token"

            # Verify super().request was called with new token
            mock_super_request.assert_called_once()
            call_args = mock_super_request.call_args
            assert call_args[1]["headers"]["Authorization"] == "Bearer new-token"

    @pytest.mark.asyncio
    async def test_request_to_token_url_prevents_recursion(self, mock_client):
        """Test that requests to token_url don't trigger token refresh"""
        mock_client._access_token = "old-token"
        mock_client._expires_at = time.time() - 1  # Expired

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None

        with patch(
            "httpx.AsyncClient.request", return_value=mock_response
        ) as mock_super_request:
            # Request to token URL should not trigger refresh
            await mock_client.request("POST", "https://auth.example.com/token")

            # Verify super().request was called directly without refresh
            mock_super_request.assert_called_once()
            call_args = mock_super_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "https://auth.example.com/token"
            # Should not have Authorization header
            assert "Authorization" not in call_args[1].get("headers", {})

    @pytest.mark.asyncio
    async def test_request_with_no_token(self, mock_client):
        """Test request with no token triggers refresh"""
        mock_client._access_token = None

        mock_token_response = Mock()
        mock_token_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_token_response.status_code = 200
        mock_token_response.raise_for_status.return_value = None

        mock_data_response = Mock()
        mock_data_response.raise_for_status.return_value = None

        with (
            patch("httpx.AsyncClient.post", return_value=mock_token_response),
            patch(
                "httpx.AsyncClient.request", return_value=mock_data_response
            ) as mock_super_request,
        ):
            await mock_client.request("GET", "https://api.example.com/data")

            # Verify token was refreshed
            assert mock_client._access_token == "new-token"

            # Verify super().request was called with new token
            mock_super_request.assert_called_once()
            call_args = mock_super_request.call_args
            assert call_args[1]["headers"]["Authorization"] == "Bearer new-token"

    @pytest.mark.asyncio
    async def test_request_preserves_existing_headers(self, mock_client):
        """Test that request preserves existing headers"""
        mock_client._access_token = "valid-token"
        mock_client._expires_at = time.time() + 3600

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None

        with patch(
            "httpx.AsyncClient.request", return_value=mock_response
        ) as mock_super_request:
            await mock_client.request(
                "GET", "https://api.example.com/data", headers={"X-Custom": "value"}
            )

            # Verify headers are preserved
            mock_super_request.assert_called_once()
            call_args = mock_super_request.call_args
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer valid-token"
            assert headers["X-Custom"] == "value"
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_request_clears_token_on_refresh_failure(self, mock_client):
        """Test that request clears token when refresh fails"""
        mock_client._access_token = None

        with patch(
            "httpx.AsyncClient.post",
            side_effect=httpx.RequestError("Connection failed"),
        ):
            with pytest.raises(httpx.RequestError):
                await mock_client.request("GET", "https://api.example.com/data")

            # Token should be cleared
            assert mock_client._access_token is None
            assert mock_client._expires_at == 0

    def test_dynamic_token_client_inheritance(self, mock_client):
        """Test that DynamicTokenClient inherits from httpx.AsyncClient"""
        assert isinstance(mock_client, httpx.AsyncClient)

    def test_get_header_for_basic_auth(self, mock_client_basic_auth):
        """Test _get_header_for_basic_auth method"""
        headers = mock_client_basic_auth._get_header_for_basic_auth("user", "pass")

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Accept"] == "application/json"
