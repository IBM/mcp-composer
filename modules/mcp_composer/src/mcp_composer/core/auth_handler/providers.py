from typing import Type, Dict, Any
from pydantic import AnyHttpUrl
from key_value.aio.protocols import AsyncKeyValue
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.auth.providers.google import GoogleProvider
from fastmcp.server.auth.providers.azure import AzureProvider
from fastmcp.server.auth.providers.aws import AWSCognitoProvider
from fastmcp.server.auth.oidc_proxy import OIDCProxy
from fastmcp.server.auth.providers.introspection import IntrospectionTokenVerifier

from mcp_composer.core.utils import LoggerFactory


logger = LoggerFactory.get_logger()


class OAuthProviderFactory:
    """
    Manages OAuth provider configuration and facilitates the creation of
    specific provider instances (GitHub, Google, AWS Cognito).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: AnyHttpUrl | str,
        # For OIDC Provider
        introspection_url: str | None = None,
        # Deprecated, Adding for Backward compatibility,
        server_url: AnyHttpUrl | str | None = None,
        provider: str | None = "oidc",
        redirect_path: str | None = None,
        user_pool_id: str | None = None,
        aws_region: str | None = None,
        config_url: AnyHttpUrl | str | None = None,
        audience: str | None = None,
        algorithm: str | None = None,
        required_scopes: list[str] | None = None,
        timeout_seconds: int | None = None,
        allowed_client_redirect_uris: list[str] | None = None,
        client_storage: AsyncKeyValue | None = None,
        token_endpoint_auth_method: str | None = None,
        tenant_id: (
            str | None
        ) = None,  # Required: your Azure tenant ID from Azure Portal
    ):
        self.provider = provider.lower() if provider else "oidc"
        self.introspection_url = introspection_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.redirect_path = redirect_path or "/auth/callback"  # Set default once
        self.user_pool_id = user_pool_id
        self.aws_region = aws_region
        self.tenant_id = tenant_id
        self.config_url = config_url
        self.audience = audience
        self.algorithm = algorithm
        self.required_scopes = required_scopes
        self.timeout_seconds = timeout_seconds
        self.allowed_client_redirect_uris = allowed_client_redirect_uris
        self.client_storage = client_storage
        self.token_endpoint_auth_method = token_endpoint_auth_method

    def _get_provider_config(self) -> Dict[str, Any]:
        """
        Generates common configuration arguments for all providers.
        """
        return {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "base_url": self.base_url,
            "redirect_path": self.redirect_path,
        }

    def get_provider_instance(self):
        """
        Creates and returns an instance of the appropriate OAuth provider.

        Returns:
            An instance of a specific provider class (e.g., GitHubProvider).

        Raises:
            ValueError: If the provider is unknown or required AWS parameters are missing.
        """
        # Define a dictionary mapping provider name to a tuple: (ProviderClass, extra_args_dict)
        try:
            provider_map: Dict[str, Type] = {
                "github": GitHubProvider,
                "google": GoogleProvider,
            }
            # --- Handle AWS Cognito Separately due to different required arguments ---
            if self.provider == "aws":
                logger.info("Creating AWS Cognito Provider")
                if not self.user_pool_id or not self.aws_region:
                    raise ValueError(
                        "AWS provider requires user_pool_id and aws_region."
                    )

                common_config = self._get_provider_config()
                return AWSCognitoProvider(
                    user_pool_id=self.user_pool_id,
                    aws_region=self.aws_region,
                    **common_config,
                )

            # --- Handle Azure Separately due to different required arguments ---
            if self.provider == "azure":
                logger.info("Creating Azure Provider")
                if not self.tenant_id:
                    raise ValueError("Azure provider requires tenant_id.")

                common_config = self._get_provider_config()
                return AzureProvider(
                    tenant_id=self.tenant_id,
                    **common_config,
                )

            # --- Handle Standard Providers (GitHub, Google) ---
            if self.provider in provider_map:
                ProviderClass = provider_map[self.provider]
                logger.info("Creating %s Provider", self.provider.capitalize())
                return ProviderClass(**self._get_provider_config())

            # --- Handle OIDC Provider ---
            if self.provider == "oidc":
                logger.info("Creating OIDC Provider")
                common_config = self._get_provider_config()
                if not self.introspection_url:
                    raise ValueError("OIDC provider requires introspection_url.")

                verifier = IntrospectionTokenVerifier(
                    introspection_url=self.introspection_url,
                    client_id=common_config["client_id"],
                    client_secret=common_config["client_secret"],
                )
                return OIDCProxy(
                    # Provider's configuration URL
                    config_url=self.config_url,  # type: ignore
                    audience=self.audience,
                    algorithm=self.algorithm,
                    required_scopes=self.required_scopes,
                    timeout_seconds=self.timeout_seconds,
                    allowed_client_redirect_uris=self.allowed_client_redirect_uris,
                    client_storage=self.client_storage,
                    token_endpoint_auth_method=self.token_endpoint_auth_method,  # type: ignore
                    token_verifier=verifier,
                    **common_config,
                )

            # Unknown provider
            logger.error("Unknown OAuth provider: %s", self.provider)
            raise ValueError(f"Unknown OAuth provider: {self.provider}")

        except Exception as e:
            logger.error("Error creating provider instance for: %s", self.provider)
            raise ValueError(f"Error creating provider instance: {e}") from e
