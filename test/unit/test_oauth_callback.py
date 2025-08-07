"""Test module for oauth_callback.py"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from starlette.requests import Request
from starlette.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException
from mcp_composer.core.auth_handler.oauth_callback import register_oauth_callback


class TestOAuthCallback:
    """Test cases for OAuth callback functionality"""

    @pytest.fixture
    def mock_self(self):
        """Mock self object with custom_route method"""
        mock = Mock()
        mock.custom_route = Mock()
        return mock

    @pytest.fixture
    def mock_settings(self):
        """Mock settings object"""
        mock = Mock()
        mock.callback_path = "http://localhost:8000/callback"
        return mock

    @pytest.fixture
    def mock_auth_provider(self):
        """Mock auth provider"""
        mock = AsyncMock()
        return mock

    @pytest.fixture
    def mock_request(self):
        """Mock request object"""
        mock = Mock(spec=Request)
        mock.query_params = {}
        return mock

    def test_register_oauth_callback_function_exists(self, mock_self, mock_settings, mock_auth_provider):
        """Test that register_oauth_callback function exists and is callable"""
        assert callable(register_oauth_callback)

    def test_register_oauth_callback_calls_custom_route(self, mock_self, mock_settings, mock_auth_provider):
        """Test that register_oauth_callback calls custom_route"""
        register_oauth_callback(mock_self, mock_settings, mock_auth_provider)
        
        # Verify custom_route was called
        mock_self.custom_route.assert_called_once()
        args, kwargs = mock_self.custom_route.call_args
        assert kwargs['methods'] == ["GET"]

    @pytest.mark.asyncio
    async def test_callback_handler_missing_code_and_state(self, mock_self, mock_settings, mock_auth_provider):
        """Test callback handler with missing code and state parameters"""
        register_oauth_callback(mock_self, mock_settings, mock_auth_provider)
        
        # Get the registered callback handler
        callback_handler = mock_self.custom_route.call_args[1]['methods'][0]
        
        # Create mock request with missing parameters
        mock_request = Mock(spec=Request)
        mock_request.query_params = {}
        
        # Test that it raises HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await callback_handler(mock_request)
        
        assert exc_info.value.status_code == 400
        assert "Missing code or state parameter" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_callback_handler_success(self, mock_self, mock_settings, mock_auth_provider):
        """Test successful callback handler"""
        register_oauth_callback(mock_self, mock_settings, mock_auth_provider)
        
        # Get the registered callback handler
        callback_handler = mock_self.custom_route.call_args[1]['methods'][0]
        
        # Mock successful auth provider response
        mock_auth_provider.handle_callback.return_value = "http://localhost:3000/success"
        
        # Create mock request with valid parameters
        mock_request = Mock(spec=Request)
        mock_request.query_params = {"code": "test_code", "state": "test_state"}
        
        # Test successful response
        response = await callback_handler(mock_request)
        
        assert isinstance(response, RedirectResponse)
        assert response.status_code == 302
        assert response.url == "http://localhost:3000/success"
        mock_auth_provider.handle_callback.assert_called_once_with("test_code", "test_state")

    @pytest.mark.asyncio
    async def test_callback_handler_http_exception(self, mock_self, mock_settings, mock_auth_provider):
        """Test callback handler when auth provider raises HTTPException"""
        register_oauth_callback(mock_self, mock_settings, mock_auth_provider)
        
        # Get the registered callback handler
        callback_handler = mock_self.custom_route.call_args[1]['methods'][0]
        
        # Mock auth provider raising HTTPException
        mock_auth_provider.handle_callback.side_effect = HTTPException(400, "Bad request")
        
        # Create mock request with valid parameters
        mock_request = Mock(spec=Request)
        mock_request.query_params = {"code": "test_code", "state": "test_state"}
        
        # Test that HTTPException is re-raised
        with pytest.raises(HTTPException) as exc_info:
            await callback_handler(mock_request)
        
        assert exc_info.value.status_code == 400
        assert "Bad request" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_callback_handler_unexpected_error(self, mock_self, mock_settings, mock_auth_provider):
        """Test callback handler with unexpected error"""
        register_oauth_callback(mock_self, mock_settings, mock_auth_provider)
        
        # Get the registered callback handler
        callback_handler = mock_self.custom_route.call_args[1]['methods'][0]
        
        # Mock auth provider raising unexpected exception
        mock_auth_provider.handle_callback.side_effect = Exception("Unexpected error")
        
        # Create mock request with valid parameters
        mock_request = Mock(spec=Request)
        mock_request.query_params = {"code": "test_code", "state": "test_state"}
        
        # Test that JSONResponse is returned with error
        response = await callback_handler(mock_request)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 500
        assert response.body.decode() == '{"error":"server_error","error_description":"Unexpected error"}' 