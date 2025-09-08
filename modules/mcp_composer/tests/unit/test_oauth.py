import os
import time
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from starlette.exceptions import HTTPException
from pydantic import AnyHttpUrl, AnyUrl
from fastmcp.exceptions import NotFoundError

from mcp_composer.core.auth_handler.oauth import ServerSettings, SimpleOAuthProvider
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken


class TestServerSettings:
    """Test cases for ServerSettings class."""

    @patch.dict(os.environ, {
        'ENABLE_OAUTH': 'true',
        'OAUTH_HOST': 'localhost',
        'OAUTH_PORT': '8080',
        'OAUTH_SERVER_URL': 'http://localhost:8080',
        'OAUTH_CLIENT_ID': 'test_client_id',
        'OAUTH_CLIENT_SECRET': 'test_client_secret',
        'OAUTH_CALLBACK_PATH': '/callback',
        'OAUTH_AUTH_URL': 'http://localhost:8080/auth',
        'OAUTH_TOKEN_URL': 'http://localhost:8080/token',
        'OAUTH_MCP_SCOPE': 'mcp:read',
        'OAUTH_PROVIDER_SCOPE': 'openid profile'
    })
    def test_server_settings_valid_environment(self):
        """Test ServerSettings with valid environment variables."""
        settings = ServerSettings()
        # Now the fields should be accessible as attributes
        assert hasattr(settings, 'model_config')
        assert settings.host == 'localhost'
        assert settings.port == '8080'
        # AnyHttpUrl might add trailing slash, so check the base URL
        assert 'localhost:8080' in str(settings.server_url)
        assert settings.client_id == 'test_client_id'
        assert settings.client_secret == 'test_client_secret'
        assert settings.callback_path == '/callback'
        assert settings.auth_url == 'http://localhost:8080/auth'
        assert settings.token_url == 'http://localhost:8080/token'
        assert settings.mcp_scope == 'mcp:read'
        assert settings.scope == 'openid profile'

    @patch.dict(os.environ, {'ENABLE_OAUTH': 'false'})
    def test_server_settings_oauth_disabled(self):
        """Test ServerSettings when OAuth is disabled."""
        settings = ServerSettings()
        # Should not raise an error when OAuth is disabled
        assert hasattr(settings, 'model_config')

    def test_server_settings_missing_environment_variables(self):
        """Test ServerSettings with missing environment variables."""
        # Test that validation fails when OAuth is enabled but required fields are missing
        with patch.dict(os.environ, {
            'ENABLE_OAUTH': 'true'
            # Missing OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET
        }, clear=False):
            # Should raise an error due to missing required fields
            with pytest.raises(NotFoundError) as exc_info:
                ServerSettings()
            assert "Failed to load OAuth settings" in str(exc_info.value)

    def test_server_settings_init_with_data(self):
        """Test ServerSettings initialization with data."""
        with patch.dict(os.environ, {'ENABLE_OAUTH': 'false'}):
            settings = ServerSettings()
            assert hasattr(settings, 'model_config')

    def test_server_settings_environment_variable_population(self):
        """Test that environment variables are correctly populated into ServerSettings attributes."""
        # Set up environment variables
        test_env = {
            'ENABLE_OAUTH': 'true',
            'OAUTH_HOST': 'testhost.example.com',
            'OAUTH_PORT': '9090',
            'OAUTH_SERVER_URL': 'https://testhost.example.com:9090',
            'OAUTH_CLIENT_ID': 'test_client_123',
            'OAUTH_CLIENT_SECRET': 'test_secret_456',
            'OAUTH_CALLBACK_PATH': 'https://testhost.example.com:9090/callback',
            'OAUTH_AUTH_URL': 'https://auth.example.com/authorize',
            'OAUTH_TOKEN_URL': 'https://auth.example.com/token',
            'OAUTH_MCP_SCOPE': 'mcp:read mcp:write',
            'OAUTH_PROVIDER_SCOPE': 'openid profile email'
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            settings = ServerSettings()
            
            # Verify all attributes are populated correctly
            assert settings.host == 'testhost.example.com'
            assert settings.port == '9090'
            assert str(settings.server_url) == 'https://testhost.example.com:9090'
            assert settings.client_id == 'test_client_123'
            assert settings.client_secret == 'test_secret_456'
            assert settings.callback_path == 'https://testhost.example.com:9090/callback'
            assert settings.auth_url == 'https://auth.example.com/authorize'
            assert settings.token_url == 'https://auth.example.com/token'
            assert settings.mcp_scope == 'mcp:read mcp:write'
            assert settings.scope == 'openid profile email'
            
            # Verify the server_url is properly converted to AnyHttpUrl
            assert isinstance(settings.server_url, AnyHttpUrl)
            assert settings.server_url.scheme == 'https'
            assert settings.server_url.host == 'testhost.example.com'
            assert settings.server_url.port == 9090

    def test_server_settings_partial_environment_variables(self):
        """Test ServerSettings with only some environment variables set."""
        # Set only some environment variables
        test_env = {
            'ENABLE_OAUTH': 'true',
            'OAUTH_HOST': 'partial.example.com',
            'OAUTH_SERVER_URL': 'http://partial.example.com',
            'OAUTH_CLIENT_ID': 'partial_client',
            'OAUTH_CLIENT_SECRET': 'partial_secret',
            'OAUTH_CALLBACK_PATH': '/partial/callback',
            'OAUTH_AUTH_URL': 'http://partial.example.com/auth',
            'OAUTH_TOKEN_URL': 'http://partial.example.com/token',
            'OAUTH_MCP_SCOPE': 'partial:scope',
            'OAUTH_PROVIDER_SCOPE': 'partial'
        }
        
        with patch.dict(os.environ, test_env, clear=True):
            settings = ServerSettings()
            
            # Verify populated attributes
            assert settings.host == 'partial.example.com'
            assert str(settings.server_url) == 'http://partial.example.com'
            assert settings.client_id == 'partial_client'
            assert settings.client_secret == 'partial_secret'
            
            # Verify missing attributes (should be empty strings or default values)
            assert settings.port == ''  # Not set in environment
            assert settings.callback_path == '/partial/callback'
            assert settings.auth_url == 'http://partial.example.com/auth'
            assert settings.token_url == 'http://partial.example.com/token'
            assert settings.mcp_scope == 'partial:scope'
            assert settings.scope == 'partial'


class TestSimpleOAuthProvider:
    """Test cases for SimpleOAuthProvider class."""

    def _create_mock_http_client(self, mock_response):
        """Helper method to create a mock HTTP client context manager."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        
        # Create a proper async context manager mock
        class MockContextManager:
            async def __aenter__(self):
                return mock_client
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None
        
        return MockContextManager()

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock()
        settings.server_url = AnyHttpUrl('http://localhost:8080')
        settings.client_id = 'test_client_id'
        settings.client_secret = 'test_client_secret'
        settings.callback_path = '/callback'
        settings.auth_url = 'http://localhost:8080/auth'
        settings.token_url = 'http://localhost:8080/token'
        settings.mcp_scope = 'mcp:read'
        settings.scope = 'openid profile'
        return settings

    @pytest.fixture
    def oauth_provider(self, mock_settings):
        """Create OAuth provider instance for testing."""
        return SimpleOAuthProvider(mock_settings)

    @pytest.fixture
    def mock_client(self):
        """Create mock OAuth client for testing."""
        client = Mock(spec=OAuthClientInformationFull)
        client.client_id = 'test_client_id'
        client.client_secret = 'test_client_secret'
        client.redirect_uris = ['http://localhost:3000/callback']
        return client

    def test_oauth_provider_initialization(self, mock_settings):
        """Test OAuth provider initialization."""
        provider = SimpleOAuthProvider(mock_settings)
        assert provider.settings == mock_settings
        assert provider.clients == {}
        assert provider.auth_codes == {}
        assert provider.tokens == {}
        assert provider.state_mapping == {}
        assert provider.token_mapping == {}
        assert provider.issuer_url == mock_settings.server_url
        assert provider.service_documentation_url == mock_settings.server_url

    @pytest.mark.asyncio
    async def test_get_client_existing(self, oauth_provider, mock_client):
        """Test getting existing client."""
        oauth_provider.clients['test_client_id'] = mock_client
        result = await oauth_provider.get_client('test_client_id')
        assert result == mock_client

    @pytest.mark.asyncio
    async def test_get_client_nonexistent(self, oauth_provider):
        """Test getting non-existent client."""
        result = await oauth_provider.get_client('nonexistent_client')
        assert result is None

    @pytest.mark.asyncio
    async def test_register_client(self, oauth_provider, mock_client):
        """Test registering a new client."""
        await oauth_provider.register_client(mock_client)
        assert oauth_provider.clients['test_client_id'] == mock_client

    @pytest.mark.asyncio
    async def test_authorize_with_state(self, oauth_provider, mock_client):
        """Test authorization with provided state."""
        params = AuthorizationParams(
            redirect_uri=AnyUrl('http://localhost:3000/callback'),
            state='test_state',
            code_challenge='test_challenge',
            redirect_uri_provided_explicitly=True,
            scopes=['mcp:read']  # Add required scopes field
        )
        
        result = await oauth_provider.authorize(mock_client, params)
        
        assert 'test_state' in result
        assert 'client_id=test_client_id' in result
        assert 'redirect_uri=/callback' in result
        assert 'scope=openid profile' in result
        assert 'response_type=code' in result
        
        # Check state mapping
        assert 'test_state' in oauth_provider.state_mapping
        state_data = oauth_provider.state_mapping['test_state']
        assert state_data['redirect_uri'] == 'http://localhost:3000/callback'
        assert state_data['code_challenge'] == 'test_challenge'
        assert state_data['redirect_uri_provided_explicitly'] == 'True'
        assert state_data['client_id'] == 'test_client_id'

    @pytest.mark.asyncio
    async def test_authorize_without_state(self, oauth_provider, mock_client):
        """Test authorization without provided state."""
        params = AuthorizationParams(
            redirect_uri=AnyUrl('http://localhost:3000/callback'),
            state=None,
            code_challenge='',  # Provide empty string instead of None
            redirect_uri_provided_explicitly=False,
            scopes=['mcp:read']  # Add required scopes field
        )
        
        result = await oauth_provider.authorize(mock_client, params)
        
        # Should generate a state
        assert 'state=' in result
        assert 'client_id=test_client_id' in result
        
        # Check that a state was generated and stored
        assert len(oauth_provider.state_mapping) == 1
        state = list(oauth_provider.state_mapping.keys())[0]
        state_data = oauth_provider.state_mapping[state]
        assert state_data['redirect_uri'] == 'http://localhost:3000/callback'
        assert state_data['redirect_uri_provided_explicitly'] == 'False'

    @pytest.mark.asyncio
    async def test_handle_callback_invalid_state(self, oauth_provider):
        """Test handling callback with invalid state."""
        with pytest.raises(HTTPException) as exc_info:
            await oauth_provider.handle_callback('test_code', 'invalid_state')
        assert exc_info.value.status_code == 400
        assert "Invalid state parameter" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch('mcp_composer.core.auth_handler.oauth.create_mcp_http_client')
    async def test_handle_callback_success(self, mock_http_client, oauth_provider):
        """Test successful callback handling."""
        # Setup state mapping
        oauth_provider.state_mapping['test_state'] = {
            'redirect_uri': 'http://localhost:3000/callback',
            'code_challenge': 'test_challenge',
            'redirect_uri_provided_explicitly': 'True',
            'client_id': 'test_client_id'
        }
        
        # Mock HTTP response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'access_token': 'test_access_token',
            'token_type': 'Bearer'
        }

        # Mock the HTTP client context manager properly
        mock_http_client.return_value = self._create_mock_http_client(mock_response)
        
        result = await oauth_provider.handle_callback('test_code', 'test_state')
        
        # Verify redirect URI construction
        assert 'http://localhost:3000/callback' in result
        assert 'code=mcp_' in result
        assert 'state=test_state' in result
        
        # Verify state was cleaned up
        assert 'test_state' not in oauth_provider.state_mapping
        
        # Verify auth code was stored
        assert len(oauth_provider.auth_codes) == 1
        auth_code = list(oauth_provider.auth_codes.values())[0]
        assert auth_code.client_id == 'test_client_id'
        assert auth_code.scopes == ['mcp:read']

    @pytest.mark.asyncio
    @patch('mcp_composer.core.auth_handler.oauth.create_mcp_http_client')
    async def test_handle_callback_http_error(self, mock_http_client, oauth_provider):
        """Test callback handling with HTTP error."""
        # Setup state mapping
        oauth_provider.state_mapping['test_state'] = {
            'redirect_uri': 'http://localhost:3000/callback',
            'code_challenge': 'test_challenge',
            'redirect_uri_provided_explicitly': 'True',
            'client_id': 'test_client_id'
        }
        
                # Mock HTTP error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {'error': 'invalid_grant'}

        # Mock the HTTP client context manager properly
        mock_http_client.return_value = self._create_mock_http_client(mock_response)
        
        with pytest.raises(HTTPException) as exc_info:
            await oauth_provider.handle_callback('test_code', 'test_state')
        assert exc_info.value.status_code == 400
        assert "Failed to exchange code for token" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch('mcp_composer.core.auth_handler.oauth.create_mcp_http_client')
    async def test_handle_callback_oauth_error(self, mock_http_client, oauth_provider):
        """Test callback handling with OAuth error response."""
        # Setup state mapping
        oauth_provider.state_mapping['test_state'] = {
            'redirect_uri': 'http://localhost:3000/callback',
            'code_challenge': 'test_challenge',
            'redirect_uri_provided_explicitly': 'True',
            'client_id': 'test_client_id'
        }
        
                # Mock OAuth error response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'error': 'invalid_grant',
            'error_description': 'Invalid authorization code'
        }

        # Mock the HTTP client context manager properly
        mock_http_client.return_value = self._create_mock_http_client(mock_response)
        
        with pytest.raises(HTTPException) as exc_info:
            await oauth_provider.handle_callback('test_code', 'test_state')
        assert exc_info.value.status_code == 400
        assert "Invalid authorization code" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch('mcp_composer.core.auth_handler.oauth.create_mcp_http_client')
    async def test_handle_callback_no_token(self, mock_http_client, oauth_provider):
        """Test callback handling with no token in response."""
        # Setup state mapping
        oauth_provider.state_mapping['test_state'] = {
            'redirect_uri': 'http://localhost:3000/callback',
            'code_challenge': 'test_challenge',
            'redirect_uri_provided_explicitly': 'True',
            'client_id': 'test_client_id'
        }
        
                # Mock response without access_token
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'token_type': 'Bearer'
            # Missing access_token
        }

        # Mock the HTTP client context manager properly
        mock_http_client.return_value = self._create_mock_http_client(mock_response)
        
        with pytest.raises(ValueError) as exc_info:
            await oauth_provider.handle_callback('test_code', 'test_state')
        assert "No valid authentication token found in response" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_load_authorization_code_existing(self, oauth_provider, mock_client):
        """Test loading existing authorization code."""
        auth_code = AuthorizationCode(
            code='test_code',
            client_id='test_client_id',
            redirect_uri=AnyUrl('http://localhost:3000/callback'),
            redirect_uri_provided_explicitly=True,
            expires_at=int(time.time()) + 300,
            scopes=['mcp:read'],
            code_challenge='test_challenge'
        )
        oauth_provider.auth_codes['test_code'] = auth_code
        
        result = await oauth_provider.load_authorization_code(mock_client, 'test_code')
        assert result == auth_code

    @pytest.mark.asyncio
    async def test_load_authorization_code_nonexistent(self, oauth_provider, mock_client):
        """Test loading non-existent authorization code."""
        result = await oauth_provider.load_authorization_code(mock_client, 'nonexistent_code')
        assert result is None

    @pytest.mark.asyncio
    async def test_exchange_authorization_code_invalid(self, oauth_provider, mock_client):
        """Test exchanging invalid authorization code."""
        auth_code = AuthorizationCode(
            code='invalid_code',
            client_id='test_client_id',
            redirect_uri=AnyUrl('http://localhost:3000/callback'),
            redirect_uri_provided_explicitly=True,
            expires_at=int(time.time()) + 300,
            scopes=['mcp:read'],
            code_challenge='test_challenge'
        )
        
        with pytest.raises(ValueError) as exc_info:
            await oauth_provider.exchange_authorization_code(mock_client, auth_code)
        assert "Invalid authorization code" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exchange_authorization_code_success(self, oauth_provider, mock_client):
        """Test successful authorization code exchange."""
        # Setup auth code
        auth_code = AuthorizationCode(
            code='test_code',
            client_id='test_client_id',
            redirect_uri=AnyUrl('http://localhost:3000/callback'),
            redirect_uri_provided_explicitly=True,
            expires_at=int(time.time()) + 300,
            scopes=['mcp:read'],
            code_challenge='test_challenge'
        )
        oauth_provider.auth_codes['test_code'] = auth_code
        
        # Setup existing auth token
        oauth_provider.tokens['auth_test_token'] = AccessToken(
            token='test_token',
            client_id='test_client_id',
            scopes=['openid profile'],
            expires_at=None
        )
        
        result = await oauth_provider.exchange_authorization_code(mock_client, auth_code)
        
        # Verify OAuthToken structure
        assert isinstance(result, OAuthToken)
        assert result.access_token.startswith('mcp_')
        assert result.token_type.lower() == 'bearer'
        assert result.expires_in == 3600
        assert result.scope == 'mcp:read'
        
        # Verify auth code was removed
        assert 'test_code' not in oauth_provider.auth_codes
        
        # Verify MCP token was stored
        assert result.access_token in oauth_provider.tokens
        mcp_token = oauth_provider.tokens[result.access_token]
        assert mcp_token.client_id == 'test_client_id'
        assert mcp_token.scopes == ['mcp:read']

    @pytest.mark.asyncio
    async def test_load_access_token_existing(self, oauth_provider):
        """Test loading existing access token."""
        token = 'test_token'
        access_token = AccessToken(
            token=token,
            client_id='test_client_id',
            scopes=['mcp:read'],
            expires_at=int(time.time()) + 3600
        )
        oauth_provider.tokens[token] = access_token
        
        result = await oauth_provider.load_access_token(token)
        assert result == access_token

    @pytest.mark.asyncio
    async def test_load_access_token_nonexistent(self, oauth_provider):
        """Test loading non-existent access token."""
        result = await oauth_provider.load_access_token('nonexistent_token')
        assert result is None

    @pytest.mark.asyncio
    async def test_load_access_token_expired(self, oauth_provider):
        """Test loading expired access token."""
        token = 'expired_token'
        access_token = AccessToken(
            token=token,
            client_id='test_client_id',
            scopes=['mcp:read'],
            expires_at=int(time.time()) - 3600  # Expired
        )
        oauth_provider.tokens[token] = access_token
        
        result = await oauth_provider.load_access_token(token)
        assert result is None
        # Token should be removed
        assert token not in oauth_provider.tokens

    @pytest.mark.asyncio
    async def test_load_access_token_no_expiry(self, oauth_provider):
        """Test loading access token with no expiry."""
        token = 'no_expiry_token'
        access_token = AccessToken(
            token=token,
            client_id='test_client_id',
            scopes=['mcp:read'],
            expires_at=None
        )
        oauth_provider.tokens[token] = access_token
        
        result = await oauth_provider.load_access_token(token)
        assert result == access_token

    @pytest.mark.asyncio
    async def test_load_refresh_token(self, oauth_provider, mock_client):
        """Test loading refresh token (not supported)."""
        result = await oauth_provider.load_refresh_token(mock_client, 'refresh_token')
        assert result is None

    @pytest.mark.asyncio
    async def test_exchange_refresh_token(self, oauth_provider, mock_client):
        """Test exchanging refresh token (not supported)."""
        refresh_token = RefreshToken(
            token='refresh_token',
            client_id='test_client_id',
            scopes=['mcp:read'],
            expires_at=int(time.time()) + 3600
        )
        
        with pytest.raises(NotImplementedError) as exc_info:
            await oauth_provider.exchange_refresh_token(mock_client, refresh_token, ['mcp:read'])
        assert "Not supported" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_revoke_token_existing(self, oauth_provider):
        """Test revoking existing token."""
        token = 'test_token'
        access_token = AccessToken(
            token=token,
            client_id='test_client_id',
            scopes=['mcp:read'],
            expires_at=int(time.time()) + 3600
        )
        oauth_provider.tokens[token] = access_token
        
        await oauth_provider.revoke_token(token)
        assert token not in oauth_provider.tokens

    @pytest.mark.asyncio
    async def test_revoke_token_nonexistent(self, oauth_provider):
        """Test revoking non-existent token."""
        # Should not raise an error
        await oauth_provider.revoke_token('nonexistent_token')
        assert 'nonexistent_token' not in oauth_provider.tokens 