"""Test module for dynamic_token_client.py"""

import pytest
import time
import httpx
from unittest.mock import Mock, patch, AsyncMock
from mcp_composer.core.auth_handler.dynamic_token_client import DynamicTokenClient
from mcp_composer.core.utils import ConfigKey


class TestDynamicTokenClient:
    """Test cases for DynamicTokenClient"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock DynamicTokenClient"""
        return DynamicTokenClient(
            base_url="https://api.example.com",
            token_url="https://auth.example.com/token",
            api_key="test-api-key",
            media_type=ConfigKey.MEDIA_TYPE_JSON,
        )

    @pytest.fixture
    def mock_client_iam(self):
        """Create a mock DynamicTokenClient with IAM media type"""
        return DynamicTokenClient(
            base_url="https://api.example.com",
            token_url="https://auth.example.com/token",
            api_key="test-api-key",
            media_type="application/x-www-form-urlencoded",
        )

    def test_dynamic_token_client_initialization(self, mock_client):
        """Test DynamicTokenClient initialization"""
        assert mock_client.token_url == "https://auth.example.com/token"
        assert mock_client.apikey == "test-api-key"
        assert mock_client.media_type == ConfigKey.MEDIA_TYPE_JSON
        assert mock_client._access_token is None
        assert mock_client._expires_at == 0

    def test_dynamic_token_client_initialization_iam(self, mock_client_iam):
        """Test DynamicTokenClient initialization with IAM media type"""
        assert mock_client_iam.media_type == "application/x-www-form-urlencoded"

    @pytest.mark.asyncio
    async def test_refresh_token_json_success(self, mock_client):
        """Test successful token refresh with JSON media type"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            await mock_client._refresh_token()

            assert mock_client._access_token == "new-token"
            assert mock_client._expires_at > time.time()

    @pytest.mark.asyncio
    async def test_refresh_token_iam_success(self, mock_client_iam):
        """Test successful token refresh with IAM media type"""
        mock_response = Mock()
        mock_response.json.return_value = {"token": "new-token", "expires_in": 3600}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            await mock_client_iam._refresh_token()

            assert mock_client_iam._access_token == "new-token"
            assert mock_client_iam._expires_at > time.time()

    @pytest.mark.asyncio
    async def test_refresh_token_missing_apikey(self, mock_client):
        """Test token refresh with missing apikey"""
        mock_client.apikey = None

        with pytest.raises(
            ValueError,
            match="Missing 'apikey' or 'token_url' in headers for token refresh.",
        ):
            await mock_client._refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_token_missing_token_url(self, mock_client):
        """Test token refresh with missing token_url"""
        mock_client.token_url = None

        with pytest.raises(
            ValueError,
            match="Missing 'apikey' or 'token_url' in headers for token refresh.",
        ):
            await mock_client._refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_token_http_error(self, mock_client):
        """Test token refresh with HTTP error"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=Mock(), response=mock_response
        )

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with pytest.raises(httpx.HTTPStatusError):
                await mock_client._refresh_token()

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
        mock_token_response.raise_for_status.return_value = None

        mock_data_response = Mock()
        mock_data_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", return_value=mock_token_response), patch(
            "httpx.AsyncClient.request", return_value=mock_data_response
        ) as mock_super_request:

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
        mock_token_response.raise_for_status.return_value = None

        mock_data_response = Mock()
        mock_data_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.post", return_value=mock_token_response), patch(
            "httpx.AsyncClient.request", return_value=mock_data_response
        ) as mock_super_request:

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

    def test_dynamic_token_client_inheritance(self, mock_client):
        """Test that DynamicTokenClient inherits from httpx.AsyncClient"""
        assert isinstance(mock_client, httpx.AsyncClient)
