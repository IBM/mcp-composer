import pytest
from unittest.mock import patch, Mock
from pydantic import AnyHttpUrl
from mcp_composer.core.auth_handler.providers import OAuthProviderFactory


class TestOAuthProviderFactory:
    """Unit tests for OAuthProviderFactory"""

    def test_init_default(self):
        """Test initialization with default values"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            introspection_url="http://introspect.com",
            client_secret="test_secret",
            base_url="http://example.com",
        )
        assert factory.provider == "oidc"
        assert factory.client_id == "test_id"
        assert factory.introspection_url == "http://introspect.com"
        assert factory.client_secret == "test_secret"
        assert factory.base_url == "http://example.com"
        assert factory.redirect_path == "/auth/callback"

    def test_init_custom(self):
        """Test initialization with custom values"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            provider="github",
            redirect_path="/custom/callback",
            user_pool_id="pool123",
            aws_region="us-east-1",
            tenant_id="tenant456",
            config_url="http://config.com",
            audience="aud",
            algorithm="RS256",
            required_scopes=["scope1"],
            timeout_seconds=30,
            allowed_client_redirect_uris=["http://redirect.com"],
            client_storage=Mock(),
            token_endpoint_auth_method="client_secret_post",
        )
        assert factory.provider == "github"
        assert factory.redirect_path == "/custom/callback"
        assert factory.user_pool_id == "pool123"
        assert factory.aws_region == "us-east-1"
        assert factory.tenant_id == "tenant456"
        assert factory.config_url == "http://config.com"
        assert factory.audience == "aud"
        assert factory.algorithm == "RS256"
        assert factory.required_scopes == ["scope1"]
        assert factory.timeout_seconds == 30
        assert factory.allowed_client_redirect_uris == ["http://redirect.com"]
        assert isinstance(factory.client_storage, Mock)
        assert factory.token_endpoint_auth_method == "client_secret_post"

    def test_get_provider_config(self):
        """Test _get_provider_config returns correct common config"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            redirect_path="/custom",
        )
        config = factory._get_provider_config()
        expected = {
            "client_id": "test_id",
            "client_secret": "test_secret",
            "base_url": "http://example.com",
            "redirect_path": "/custom",
        }
        assert config == expected

    @patch("mcp_composer.core.auth_handler.providers.GitHubProvider")
    def test_get_provider_instance_github(self, MockGitHubProvider):
        """Test get_provider_instance for GitHub"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            provider="github",
        )
        instance = factory.get_provider_instance()
        MockGitHubProvider.assert_called_once_with(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            redirect_path="/auth/callback",
        )
        assert instance == MockGitHubProvider.return_value

    @patch("mcp_composer.core.auth_handler.providers.GoogleProvider")
    def test_get_provider_instance_google(self, MockGoogleProvider):
        """Test get_provider_instance for Google"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            provider="google",
        )
        instance = factory.get_provider_instance()
        MockGoogleProvider.assert_called_once_with(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            redirect_path="/auth/callback",
        )
        assert instance == MockGoogleProvider.return_value

    @patch("mcp_composer.core.auth_handler.providers.AWSCognitoProvider")
    def test_get_provider_instance_aws(self, MockAWSCognitoProvider):
        """Test get_provider_instance for AWS Cognito"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            provider="aws",
            user_pool_id="pool123",
            aws_region="us-east-1",
        )
        instance = factory.get_provider_instance()
        MockAWSCognitoProvider.assert_called_once_with(
            user_pool_id="pool123",
            aws_region="us-east-1",
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            redirect_path="/auth/callback",
        )
        assert instance == MockAWSCognitoProvider.return_value

    def test_get_provider_instance_aws_missing_params(self):
        """Test get_provider_instance for AWS with missing params raises ValueError"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            provider="aws",
        )
        with pytest.raises(
            ValueError, match="AWS provider requires user_pool_id and aws_region"
        ):
            factory.get_provider_instance()

    @patch("mcp_composer.core.auth_handler.providers.AzureProvider")
    def test_get_provider_instance_azure(self, MockAzureProvider):
        """Test get_provider_instance for Azure"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            provider="azure",
            tenant_id="tenant456",
        )
        instance = factory.get_provider_instance()
        MockAzureProvider.assert_called_once_with(
            tenant_id="tenant456",
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            redirect_path="/auth/callback",
        )
        assert instance == MockAzureProvider.return_value

    def test_get_provider_instance_azure_missing_params(self):
        """Test get_provider_instance for Azure with missing tenant_id raises ValueError"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            provider="azure",
        )
        with pytest.raises(ValueError, match="Azure provider requires tenant_id"):
            factory.get_provider_instance()

    @patch("mcp_composer.core.auth_handler.providers.IntrospectionTokenVerifier")
    @patch("mcp_composer.core.auth_handler.providers.OIDCProxy")
    def test_get_provider_instance_oidc(
        self, MockOIDCProxy, MockIntrospectionTokenVerifier
    ):
        """Test get_provider_instance for OIDC"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            introspection_url="http://introspect.com",
            client_secret="test_secret",
            base_url="http://example.com",
            provider="oidc",
            config_url="http://config.com",
            audience="aud",
            algorithm="RS256",
            required_scopes=["scope1"],
            timeout_seconds=30,
            allowed_client_redirect_uris=["http://redirect.com"],
            client_storage=Mock(),
            token_endpoint_auth_method="client_secret_post",
        )
        instance = factory.get_provider_instance()
        MockIntrospectionTokenVerifier.assert_called_once_with(
            introspection_url="http://introspect.com",
            client_id="test_id",
            client_secret="test_secret",
        )
        MockOIDCProxy.assert_called_once_with(
            config_url="http://config.com",
            audience="aud",
            algorithm="RS256",
            required_scopes=["scope1"],
            timeout_seconds=30,
            allowed_client_redirect_uris=["http://redirect.com"],
            client_storage=factory.client_storage,
            token_endpoint_auth_method="client_secret_post",
            token_verifier=MockIntrospectionTokenVerifier.return_value,
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            redirect_path="/auth/callback",
        )
        assert instance == MockOIDCProxy.return_value

    def test_get_provider_instance_unknown_provider(self):
        """Test get_provider_instance for unknown provider raises ValueError"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            provider="unknown",
        )
        with pytest.raises(ValueError, match="Unknown OAuth provider: unknown"):
            factory.get_provider_instance()

    @patch(
        "mcp_composer.core.auth_handler.providers.GitHubProvider",
        side_effect=Exception("Init error"),
    )
    def test_get_provider_instance_creation_error(self, MockGitHubProvider):
        """Test get_provider_instance handles creation errors"""
        factory = OAuthProviderFactory(
            client_id="test_id",
            client_secret="test_secret",
            base_url="http://example.com",
            provider="github",
        )
        with pytest.raises(
            ValueError, match="Error creating provider instance: Init error"
        ):
            factory.get_provider_instance()
