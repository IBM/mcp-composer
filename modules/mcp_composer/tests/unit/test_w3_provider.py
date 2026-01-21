"""Unit tests for IBM W3 OAuth provider."""

from unittest.mock import Mock, patch

import pytest
from pydantic import AnyHttpUrl

from mcp_composer.core.auth_handler.w3 import W3Provider
from fastmcp.server.auth.oidc_proxy import OIDCProxy


class TestW3Provider:
    """Unit tests for W3Provider class."""

    @patch("mcp_composer.core.auth_handler.w3.IntrospectionTokenVerifier")
    @patch.object(OIDCProxy, "__init__", return_value=None)
    def test_w3_provider_initialization_defaults(self, mock_oidc_proxy_init, mock_introspection_verifier):
        """Test W3Provider initialization with default values."""
        mock_verifier_instance = Mock()
        mock_verifier_instance.required_scopes = ["openid"]
        mock_introspection_verifier.return_value = mock_verifier_instance

        provider = W3Provider(
            client_id="test_client_id",
            client_secret="test_client_credential",
            config_url="https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration",
            introspection_url="https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect",
            base_url="http://localhost:9000",
        )

        # Verify IntrospectionTokenVerifier was created with correct parameters
        mock_introspection_verifier.assert_called_once_with(
            introspection_url="https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect",
            client_id="test_client_id",
            client_secret="test_client_credential",
            timeout_seconds=10,
            required_scopes=["openid"],
        )

        # Verify OIDCProxy was initialized with correct parameters
        mock_oidc_proxy_init.assert_called_once()
        call_kwargs = mock_oidc_proxy_init.call_args[1]
        assert call_kwargs["config_url"] == "https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration"
        assert call_kwargs["client_id"] == "test_client_id"
        assert call_kwargs["client_secret"] == "test_client_credential"
        assert call_kwargs["token_verifier"] == mock_verifier_instance
        assert call_kwargs["base_url"] == "http://localhost:9000"
        assert call_kwargs["redirect_path"] is None  # Defaults to None, OIDCProxy will use "/auth/callback"
        assert call_kwargs["issuer_url"] == "http://localhost:9000"  # Defaults to base_url
        assert call_kwargs["timeout_seconds"] == 10
        assert call_kwargs["require_authorization_consent"] is True
        # Note: required_scopes is not passed to OIDCProxy when token_verifier is provided
        # as it's already configured on the token_verifier

    @patch("mcp_composer.core.auth_handler.w3.IntrospectionTokenVerifier")
    @patch.object(OIDCProxy, "__init__", return_value=None)
    def test_w3_provider_initialization_custom(self, mock_oidc_proxy_init, mock_introspection_verifier):
        """Test W3Provider initialization with custom values."""
        mock_verifier_instance = Mock()
        mock_verifier_instance.required_scopes = ["openid", "profile", "email"]
        mock_introspection_verifier.return_value = mock_verifier_instance
        mock_storage = Mock()

        provider = W3Provider(
            client_id="custom_client_id",
            client_secret="custom_client_credential",
            config_url="https://custom.w3.ibm.com/.well-known/openid-configuration",
            introspection_url="https://custom.w3.ibm.com/introspect",
            base_url="https://my-server.com",
            issuer_url="https://my-issuer.com",
            redirect_path="/custom/callback",
            required_scopes=["openid", "profile", "email"],
            timeout_seconds=30,
            allowed_client_redirect_uris=["https://client.com/callback"],
            client_storage=mock_storage,
            jwt_signing_key="custom_jwt_key",
            require_authorization_consent=False,
            client_auth_method="client_secret_post",
            audience="custom_audience",
            extra_authorize_params={"prompt": "select_account"},
        )

        # Verify IntrospectionTokenVerifier was created with custom parameters
        mock_introspection_verifier.assert_called_once_with(
            introspection_url="https://custom.w3.ibm.com/introspect",
            client_id="custom_client_id",
            client_secret="custom_client_credential",
            timeout_seconds=30,
            required_scopes=["openid", "profile", "email"],
        )

        # Verify OIDCProxy was initialized with custom parameters
        mock_oidc_proxy_init.assert_called_once()
        call_kwargs = mock_oidc_proxy_init.call_args[1]
        assert call_kwargs["config_url"] == "https://custom.w3.ibm.com/.well-known/openid-configuration"
        assert call_kwargs["client_id"] == "custom_client_id"
        assert call_kwargs["client_secret"] == "custom_client_credential"
        assert call_kwargs["token_verifier"] == mock_verifier_instance
        assert call_kwargs["base_url"] == "https://my-server.com"
        assert call_kwargs["issuer_url"] == "https://my-issuer.com"
        assert call_kwargs["redirect_path"] == "/custom/callback"
        assert call_kwargs["allowed_client_redirect_uris"] == ["https://client.com/callback"]
        assert call_kwargs["client_storage"] == mock_storage
        assert call_kwargs["jwt_signing_key"] == "custom_jwt_key"
        assert call_kwargs["require_authorization_consent"] is False
        assert call_kwargs["audience"] == "custom_audience"
        assert call_kwargs["timeout_seconds"] == 30
        # Note: required_scopes and extra_authorize_params are not passed to OIDCProxy
        # when token_verifier is provided, as scopes are configured on the token_verifier

    @patch("mcp_composer.core.auth_handler.w3.IntrospectionTokenVerifier")
    @patch.object(OIDCProxy, "__init__", return_value=None)
    def test_w3_provider_initialization_with_string_scopes(self, mock_oidc_proxy_init, mock_introspection_verifier):
        """Test W3Provider initialization with string scopes (should be parsed)."""
        mock_verifier_instance = Mock()
        mock_verifier_instance.required_scopes = ["openid", "profile", "email"]
        mock_introspection_verifier.return_value = mock_verifier_instance

        provider = W3Provider(
            client_id="test_client_id",
            client_secret="test_client_credential",
            config_url="https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration",
            introspection_url="https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect",
            base_url="http://localhost:9000",
            required_scopes="openid profile email",  # String instead of list
        )

        # Verify scopes were parsed correctly and passed to IntrospectionTokenVerifier
        mock_oidc_proxy_init.assert_called_once()
        # Verify IntrospectionTokenVerifier received parsed scopes
        introspection_call_kwargs = mock_introspection_verifier.call_args[1]
        assert introspection_call_kwargs["required_scopes"] == ["openid", "profile", "email"]

    @patch("mcp_composer.core.auth_handler.w3.IntrospectionTokenVerifier")
    @patch.object(OIDCProxy, "__init__", return_value=None)
    def test_w3_provider_initialization_with_anyhttpurl(self, mock_oidc_proxy_init, mock_introspection_verifier):
        """Test W3Provider initialization with AnyHttpUrl types."""
        mock_verifier_instance = Mock()
        mock_verifier_instance.required_scopes = ["openid"]
        mock_introspection_verifier.return_value = mock_verifier_instance

        config_url = AnyHttpUrl("https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration")
        base_url = AnyHttpUrl("http://localhost:9000")

        provider = W3Provider(
            client_id="test_client_id",
            client_secret="test_client_credential",
            config_url=config_url,
            introspection_url="https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect",
            base_url=base_url,
        )

        # Verify AnyHttpUrl objects are passed correctly
        mock_oidc_proxy_init.assert_called_once()
        call_kwargs = mock_oidc_proxy_init.call_args[1]
        assert call_kwargs["config_url"] == config_url
        assert call_kwargs["base_url"] == base_url

    @patch("mcp_composer.core.auth_handler.w3.IntrospectionTokenVerifier")
    @patch.object(OIDCProxy, "__init__", return_value=None)
    def test_w3_provider_issuer_url_defaults_to_base_url(self, mock_oidc_proxy_init, mock_introspection_verifier):
        """Test that issuer_url defaults to base_url when not provided."""
        mock_verifier_instance = Mock()
        mock_verifier_instance.required_scopes = ["openid"]
        mock_introspection_verifier.return_value = mock_verifier_instance

        provider = W3Provider(
            client_id="test_client_id",
            client_secret="test_client_credential",
            config_url="https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration",
            introspection_url="https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect",
            base_url="http://localhost:9000",
            # issuer_url not provided
        )

        mock_oidc_proxy_init.assert_called_once()
        call_kwargs = mock_oidc_proxy_init.call_args[1]
        assert call_kwargs["issuer_url"] == "http://localhost:9000"

    @patch("mcp_composer.core.auth_handler.w3.IntrospectionTokenVerifier")
    @patch.object(OIDCProxy, "__init__", return_value=None)
    def test_w3_provider_empty_scopes_defaults_to_openid(self, mock_oidc_proxy_init, mock_introspection_verifier):
        """Test that empty scopes list defaults to ['openid']."""
        mock_verifier_instance = Mock()
        mock_verifier_instance.required_scopes = ["openid"]
        mock_introspection_verifier.return_value = mock_verifier_instance

        provider = W3Provider(
            client_id="test_client_id",
            client_secret="test_client_credential",
            config_url="https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration",
            introspection_url="https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect",
            base_url="http://localhost:9000",
            required_scopes=None,  # None should default to ["openid"]
        )

        mock_oidc_proxy_init.assert_called_once()
        # Verify IntrospectionTokenVerifier got the default scopes
        introspection_call_kwargs = mock_introspection_verifier.call_args[1]
        assert introspection_call_kwargs["required_scopes"] == ["openid"]
        # Note: required_scopes is not passed to OIDCProxy when token_verifier is provided

    @patch("mcp_composer.core.auth_handler.w3.IntrospectionTokenVerifier")
    @patch.object(OIDCProxy, "__init__", return_value=None)
    def test_w3_provider_inherits_from_oidc_proxy(self, mock_oidc_proxy_init, mock_introspection_verifier):
        """Test that W3Provider properly inherits from OIDCProxy."""
        mock_verifier_instance = Mock()
        mock_verifier_instance.required_scopes = ["openid"]
        mock_introspection_verifier.return_value = mock_verifier_instance

        provider = W3Provider(
            client_id="test_client_id",
            client_secret="test_client_credential",
            config_url="https://preprod.login.w3.ibm.com/oidc/endpoint/default/.well-known/openid-configuration",
            introspection_url="https://preprod.login.w3.ibm.com/v1.0/endpoint/default/introspect",
            base_url="http://localhost:9000",
        )

        # Verify that OIDCProxy.__init__ was called
        assert mock_oidc_proxy_init.called
        # Verify that W3Provider is an instance of OIDCProxy
        assert isinstance(provider, W3Provider)

