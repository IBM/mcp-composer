"""Test module for aspera_auth_handler.py"""

import os
import time
import pytest
import httpx
import jwt
from unittest.mock import Mock, patch, AsyncMock, mock_open
from mcp_composer.core.auth_handler.aspera_auth_handler import AsperaJWTClient
from mcp_composer.core.utils import ConfigKey


class TestAsperaJWTClient:
    """Test cases for AsperaJWTClient"""

    @pytest.fixture
    def mock_private_key(self):
        """Mock private key for JWT signing"""
        return """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890abcdefghijklmnopqrstuvwxyz
-----END RSA PRIVATE KEY-----"""

    @pytest.fixture
    def auth_data(self):
        """Create mock auth data"""
        return {
            ConfigKey.CLIENT_ID: "test_client_id",
            ConfigKey.CLIENT_SECRET: "test_client_secret",
            ConfigKey.Token_URL: "https://api.example.com/oauth2/token",
            ConfigKey.TOKEN_URL_WITH_ORG: "https://api.example.com/oauth2/org/token",
            ConfigKey.CERT_PATH: "/path/to/cert.pem",
            "user_email": "test@example.com",
            ConfigKey.SCOPE: "user:all",
        }

    @pytest.fixture
    def client(self, auth_data):
        """Create a mock AsperaJWTClient"""
        return AsperaJWTClient(
            base_url="https://api.example.com",
            auth_data=auth_data,
        )

    def test_initialization_success(self, auth_data):
        """Test successful initialization"""
        client = AsperaJWTClient(
            base_url="https://api.example.com",
            auth_data=auth_data,
            timeout=30.0,
            headers={"X-Custom": "value"},
        )

        assert client._access_token is None
        assert client._expires_at == 0.0
        assert client.auth_data == auth_data
        assert client._resolved_token_url is None
        assert client.base_url == "https://api.example.com"
        # httpx.AsyncClient converts float timeout to Timeout object
        assert client.timeout.connect == 30.0

    def test_initialization_empty_base_url(self):
        """Test initialization with empty base_url raises ValueError"""
        with pytest.raises(ValueError, match="base_url cannot be empty"):
            AsperaJWTClient(base_url="", auth_data={})

    def test_initialization_invalid_timeout(self, auth_data):
        """Test initialization with invalid timeout raises ValueError"""
        with pytest.raises(ValueError, match="timeout must be positive"):
            AsperaJWTClient(base_url="https://api.example.com", auth_data=auth_data, timeout=-1)

    def test_initialization_no_auth_data(self):
        """Test initialization without auth_data"""
        client = AsperaJWTClient(base_url="https://api.example.com")
        assert client.auth_data == {}

    @patch("builtins.open", new_callable=mock_open, read_data="-----BEGIN RSA PRIVATE KEY-----\nMOCK_KEY\n-----END RSA PRIVATE KEY-----")
    @patch("jwt.encode")
    def test_generate_jwt_assertion_success(self, mock_jwt_encode, mock_file, client, mock_private_key):
        """Test successful JWT assertion generation"""
        mock_jwt_encode.return_value = "mock.jwt.token"

        assertion = client._generate_jwt_assertion()

        assert assertion == "mock.jwt.token"
        mock_file.assert_called_once_with("/path/to/cert.pem", "r", encoding="utf-8")
        mock_jwt_encode.assert_called_once()
        
        # Verify JWT payload structure
        call_args = mock_jwt_encode.call_args
        payload = call_args[0][0]
        headers = call_args[1]["headers"]
        
        assert payload["iss"] == "test_client_id"
        assert payload["sub"] == "test@example.com"
        assert payload["aud"] == "https://api.example.com/oauth2/token"
        assert "iat" in payload
        assert "nbf" in payload
        assert "exp" in payload
        assert "jti" in payload
        assert headers["typ"] == "JWT"
        assert headers["alg"] == "RS256"

    @patch("mcp_composer.core.auth_handler.aspera_auth_handler.resolve_env_value")
    def test_generate_jwt_assertion_missing_user_email(self, mock_resolve, client):
        """Test JWT assertion generation with missing user_email"""
        # Mock resolve_env_value to return values for other fields but None/empty for user_email
        user_email_value = client.auth_data.get("user_email")
        def resolve_side_effect(x):
            # Return None/empty for user_email to simulate missing value
            if x == user_email_value:
                return None  # user_email resolves to None (which will be falsy)
            # Return original value for other fields (or resolved value if it's an ENV_ var)
            return x if x is not None else ""
        
        mock_resolve.side_effect = resolve_side_effect

        with pytest.raises(ValueError, match=r"user_email must be provided"):
            client._generate_jwt_assertion()

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_sign_payload_file_not_found(self, mock_file, client):
        """Test _sign_payload raises ValueError when certificate file not found"""
        with pytest.raises(ValueError, match="Certificate/private key not found"):
            client._sign_payload("/nonexistent/cert.pem", {}, {})

    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_sign_payload_permission_error(self, mock_file, client):
        """Test _sign_payload raises ValueError on permission error"""
        with pytest.raises(ValueError, match="Error reading private key"):
            client._sign_payload("/path/to/cert.pem", {}, {})

    @patch("mcp_composer.core.auth_handler.aspera_auth_handler.resolve_env_value")
    def test_generate_jwt_assertion_with_env_variables(self, mock_resolve, auth_data):
        """Test JWT assertion generation with environment variable resolution"""
        env_resolutions = {
            "ENV_CLIENT_ID": "resolved_client_id",
            "ENV_USER_EMAIL": "resolved@example.com",
            "ENV_TOKEN_URL": "https://resolved.example.com/token",
            "ENV_CERT_PATH": "/resolved/cert.pem",
        }
        
        def resolve_side_effect(x):
            # Return resolved value if it's an ENV_ variable, otherwise return the original value
            if x is None:
                return ""
            return env_resolutions.get(x, x)
        
        mock_resolve.side_effect = resolve_side_effect

        # Create a new auth_data dict to avoid modifying the fixture
        test_auth_data = auth_data.copy()
        test_auth_data[ConfigKey.CLIENT_ID] = "ENV_CLIENT_ID"
        test_auth_data["user_email"] = "ENV_USER_EMAIL"
        test_auth_data[ConfigKey.Token_URL] = "ENV_TOKEN_URL"
        test_auth_data[ConfigKey.CERT_PATH] = "ENV_CERT_PATH"

        client = AsperaJWTClient(base_url="https://api.example.com", auth_data=test_auth_data)

        with patch("builtins.open", new_callable=mock_open, read_data="MOCK_KEY"), \
             patch("jwt.encode", return_value="mock.jwt.token"):
            assertion = client._generate_jwt_assertion()
            assert assertion == "mock.jwt.token"

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client, mock_private_key):
        """Test successful token refresh"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-access-token",
            "expires_in": 3600,
        }
        mock_response.status_code = 201
        mock_response.raise_for_status.return_value = None

        with patch("builtins.open", new_callable=mock_open, read_data=mock_private_key), \
             patch("jwt.encode", return_value="mock.jwt.assertion"), \
             patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response):
            
            await client._refresh_token()

            assert client._access_token == "new-access-token"
            assert client._expires_at > time.time()
            assert client._expires_at <= time.time() + 3600

    @pytest.mark.asyncio
    async def test_refresh_token_with_token_field(self, client, mock_private_key):
        """Test token refresh when response uses 'token' field instead of 'access_token'"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "token": "token-field-value",
            "expires_in": 1800,
        }
        mock_response.status_code = 201
        mock_response.raise_for_status.return_value = None

        with patch("builtins.open", new_callable=mock_open, read_data=mock_private_key), \
             patch("jwt.encode", return_value="mock.jwt.assertion"), \
             patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response):
            
            await client._refresh_token()

            assert client._access_token == "token-field-value"
            assert client._expires_at > time.time()

    @pytest.mark.asyncio
    async def test_refresh_token_missing_token_url_with_org(self, client):
        """Test token refresh with missing token_url_with_org"""
        client.auth_data.pop(ConfigKey.TOKEN_URL_WITH_ORG, None)

        with patch("builtins.open", new_callable=mock_open, read_data="MOCK_KEY"), \
             patch("jwt.encode", return_value="mock.jwt.assertion"):
            with pytest.raises(ValueError, match=r"token_url_with_org must be provided"):
                await client._refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_token_no_access_token_in_response(self, client, mock_private_key):
        """Test token refresh when response has no access_token"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "error": "invalid_grant",
        }
        mock_response.status_code = 201
        mock_response.raise_for_status.return_value = None

        with patch("builtins.open", new_callable=mock_open, read_data=mock_private_key), \
             patch("jwt.encode", return_value="mock.jwt.assertion"), \
             patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response):
            
            with pytest.raises(ValueError, match="No access_token in response"):
                await client._refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_token_http_error(self, client, mock_private_key):
        """Test token refresh with HTTP error"""
        mock_response = Mock()
        mock_response.json.return_value = {"error": "unauthorized"}
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401", request=Mock(), response=mock_response
        )

        with patch("builtins.open", new_callable=mock_open, read_data=mock_private_key), \
             patch("jwt.encode", return_value="mock.jwt.assertion"), \
             patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response):
            
            with pytest.raises(httpx.HTTPStatusError):
                await client._refresh_token()

    @pytest.mark.asyncio
    async def test_refresh_token_default_expires_in(self, client, mock_private_key):
        """Test token refresh uses default expires_in when not provided"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-token",
        }
        mock_response.status_code = 201
        mock_response.raise_for_status.return_value = None

        with patch("builtins.open", new_callable=mock_open, read_data=mock_private_key), \
             patch("jwt.encode", return_value="mock.jwt.assertion"), \
             patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response):
            
            await client._refresh_token()

            assert client._access_token == "new-token"
            # Should use default 3600 seconds minus buffer (60 seconds)
            # Allow some tolerance for time.time() calls at different times
            expected_min = time.time() + 3530  # 3600 - 60 buffer - 10 tolerance
            expected_max = time.time() + 3550  # 3600 - 60 buffer + 10 tolerance
            assert expected_min < client._expires_at < expected_max

    @pytest.mark.asyncio
    async def test_refresh_token_custom_scope(self, auth_data, mock_private_key):
        """Test token refresh with custom scope"""
        auth_data[ConfigKey.SCOPE] = "custom:scope"
        client = AsperaJWTClient(base_url="https://api.example.com", auth_data=auth_data)

        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_response.status_code = 201
        mock_response.raise_for_status.return_value = None

        with patch("builtins.open", new_callable=mock_open, read_data=mock_private_key), \
             patch("jwt.encode", return_value="mock.jwt.assertion"), \
             patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            
            await client._refresh_token()

            # Verify scope was included in the request
            call_args = mock_post.call_args
            content = call_args[1]["content"].decode('utf-8')
            assert "scope=custom%3Ascope" in content or "scope=custom:scope" in content

    @pytest.mark.asyncio
    async def test_request_with_valid_token(self, client):
        """Test request with valid token"""
        client._access_token = "valid-token"
        client._expires_at = time.time() + 3600  # Valid for 1 hour

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response) as mock_http_request:
            await client.request("GET", "https://api.example.com/data")

            # Verify super().request was called with Authorization header
            mock_http_request.assert_called_once()
            call_args = mock_http_request.call_args
            assert call_args[0][0] == "GET"
            assert call_args[0][1] == "https://api.example.com/data"
            assert call_args[1]["headers"]["Authorization"] == "Bearer valid-token"
            assert call_args[1]["headers"]["Accept"] == "application/json"

    @pytest.mark.asyncio
    async def test_request_with_expired_token(self, client, mock_private_key):
        """Test request with expired token triggers refresh"""
        client._access_token = "old-token"
        client._expires_at = time.time() - 1  # Expired

        mock_token_response = Mock()
        mock_token_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_token_response.status_code = 201
        mock_token_response.raise_for_status.return_value = None

        mock_data_response = Mock()
        mock_data_response.raise_for_status.return_value = None

        with patch("builtins.open", new_callable=mock_open, read_data=mock_private_key), \
             patch("jwt.encode", return_value="mock.jwt.assertion"), \
             patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_token_response), \
             patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_data_response) as mock_http_request:

            await client.request("GET", "https://api.example.com/data")

            # Verify token was refreshed
            assert client._access_token == "new-token"

            # Verify super().request was called with new token
            mock_http_request.assert_called_once()
            call_args = mock_http_request.call_args
            assert call_args[1]["headers"]["Authorization"] == "Bearer new-token"

    @pytest.mark.asyncio
    async def test_request_to_token_url_prevents_recursion(self, client):
        """Test that requests to token_url don't trigger token refresh"""
        client._access_token = "old-token"
        client._expires_at = time.time() - 1  # Expired
        client._resolved_token_url = "https://api.example.com/oauth2/token"

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response) as mock_http_request:
            # Request to token URL should not trigger refresh
            await client.request("POST", "https://api.example.com/oauth2/token")

            # Verify super().request was called directly without refresh
            mock_http_request.assert_called_once()
            call_args = mock_http_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "https://api.example.com/oauth2/token"
            # Should not have Authorization header (since it's a token request)
            assert "Authorization" not in call_args[1].get("headers", {})

    @pytest.mark.asyncio
    async def test_request_to_oauth2_token_pattern(self, client):
        """Test that requests matching /oauth2/.../token pattern don't trigger refresh"""
        client._access_token = "old-token"
        client._expires_at = time.time() - 1  # Expired

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response) as mock_http_request:
            # Request matching oauth2 token pattern should not trigger refresh
            await client.request("POST", "https://api.example.com/oauth2/org/token")

            # Verify super().request was called directly without refresh
            mock_http_request.assert_called_once()
            # Should not have Authorization header
            call_args = mock_http_request.call_args
            headers = call_args[1].get("headers", {})
            assert "Authorization" not in headers

    @pytest.mark.asyncio
    async def test_request_with_no_token(self, client, mock_private_key):
        """Test request with no token triggers refresh"""
        client._access_token = None
        client._expires_at = 0.0  # Ensure it's expired

        mock_token_response = Mock()
        mock_token_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_token_response.status_code = 201
        mock_token_response.raise_for_status.return_value = None

        mock_data_response = Mock()
        mock_data_response.raise_for_status.return_value = None

        with patch("builtins.open", new_callable=mock_open, read_data=mock_private_key), \
             patch("jwt.encode", return_value="mock.jwt.assertion"), \
             patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_token_response), \
             patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_data_response) as mock_http_request:

            await client.request("GET", "https://api.example.com/data")

            # Verify token was refreshed
            assert client._access_token == "new-token"

            # Verify super().request was called with new token
            mock_http_request.assert_called_once()
            call_args = mock_http_request.call_args
            assert call_args[1]["headers"]["Authorization"] == "Bearer new-token"

    @pytest.mark.asyncio
    async def test_request_preserves_existing_headers(self, client):
        """Test that request preserves existing headers"""
        client._access_token = "valid-token"
        client._expires_at = time.time() + 3600

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response) as mock_http_request:
            await client.request(
                "GET", "https://api.example.com/data", headers={"X-Custom": "value"}
            )

            # Verify headers are preserved
            mock_http_request.assert_called_once()
            call_args = mock_http_request.call_args
            headers = call_args[1]["headers"]
            assert headers["Authorization"] == "Bearer valid-token"
            assert headers["X-Custom"] == "value"
            assert headers["Accept"] == "application/json"

    @pytest.mark.asyncio
    async def test_request_sets_content_type_for_json_body(self, client):
        """Test that request sets Content-Type for JSON body"""
        client._access_token = "valid-token"
        client._expires_at = time.time() + 3600

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response) as mock_http_request:
            await client.request("POST", "https://api.example.com/data", json={"key": "value"})

            call_args = mock_http_request.call_args
            headers = call_args[1]["headers"]
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_request_respects_existing_content_type(self, client):
        """Test that request respects existing Content-Type header"""
        client._access_token = "valid-token"
        client._expires_at = time.time() + 3600

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.request", new_callable=AsyncMock, return_value=mock_response) as mock_http_request:
            await client.request(
                "POST",
                "https://api.example.com/data",
                headers={"Content-Type": "application/xml"},
                json={"key": "value"},
            )

            call_args = mock_http_request.call_args
            headers = call_args[1]["headers"]
            assert headers["Content-Type"] == "application/xml"

    def test_aspera_jwt_client_inheritance(self, client):
        """Test that AsperaJWTClient inherits from httpx.AsyncClient"""
        assert isinstance(client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_refresh_token_request_format(self, client, mock_private_key):
        """Test that refresh token request is formatted correctly"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_response.status_code = 201
        mock_response.raise_for_status.return_value = None

        with patch("builtins.open", new_callable=mock_open, read_data=mock_private_key), \
             patch("jwt.encode", return_value="mock.jwt.assertion"), \
             patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            
            await client._refresh_token()

            # Verify POST was called with correct parameters
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://api.example.com/oauth2/org/token"
            
            # Verify content type
            assert call_args[1]["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
            
            # Verify BasicAuth was used
            assert call_args[1]["auth"] is not None
            
            # Verify content contains required fields
            content = call_args[1]["content"].decode('utf-8')
            assert "assertion=" in content
            assert "grant_type=" in content
            assert "scope=" in content
            # The grant_type is URL-encoded, so check for the encoded version
            assert "urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer" in content

