"""JWT authentication provider wrapper for FastMCP."""

from typing import Optional, Any
from fastmcp.server.auth.providers.jwt import JWTVerifier
from .jwt_config import JWTConfig
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


class JWTAuthProvider:
    """
    Wrapper around FastMCP's JWTVerifier for MCP Composer.

    This class provides a convenient interface for creating and managing
    JWT authentication in MCP Composer applications. It wraps FastMCP's
    built-in JWTVerifier with additional configuration and utility methods.

    Attributes:
        config: JWTConfig instance containing authentication settings

    Example:
        >>> from mcp_composer.core.auth.jwt import JWTAuthProvider, JWTConfig
        >>>
        >>> # Create from config
        >>> config = JWTConfig(secret="my-secret", algorithm="HS256")
        >>> provider = JWTAuthProvider(config=config)
        >>>
        >>> # Use with MCPComposer
        >>> from mcp_composer import MCPComposer
        >>> composer = MCPComposer("my-app", auth=provider.get_verifier())
    """

    def __init__(self, config: Optional[JWTConfig] = None, **kwargs: Any):
        """
        Initialize JWT authentication provider.

        Args:
            config: JWTConfig instance or None to load from environment
            **kwargs: Additional arguments to override config values

        Example:
            >>> # Load from environment
            >>> provider = JWTAuthProvider()
            >>>
            >>> # With explicit config
            >>> config = JWTConfig(secret="my-secret")
            >>> provider = JWTAuthProvider(config=config)
            >>>
            >>> # Override config values
            >>> provider = JWTAuthProvider(
            ...     config=config,
            ...     verify_exp=False  # Override for testing
            ... )
        """
        if config is None:
            logger.info("Loading JWT config from environment")
            config = JWTConfig.from_env()

        # Override config with kwargs
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)
                logger.debug("Overriding config.%s = %s", key, value)

        self.config = config
        self._verifier: Optional[JWTVerifier] = None

        logger.info(
            "Initialized JWT auth provider with algorithm: %s, verify_exp: %s", config.algorithm, config.verify_exp
        )

    def get_verifier(self) -> JWTVerifier:
        """
        Get or create the FastMCP JWTVerifier instance.

        This method lazily creates the JWTVerifier on first access and
        caches it for subsequent calls.

        Returns:
            JWTVerifier instance configured with current settings

        Example:
            >>> provider = JWTAuthProvider.from_secret("my-secret")
            >>> verifier = provider.get_verifier()
            >>>
            >>> # Use with MCPComposer
            >>> composer = MCPComposer("app", auth=verifier)
        """
        if self._verifier is None:
            logger.debug("Creating new JWTVerifier instance")
            self._verifier = self._create_verifier()
        return self._verifier

    def _create_verifier(self) -> JWTVerifier:
        """
        Create a new JWTVerifier instance from config.

        Returns:
            Configured JWTVerifier instance
        """
        verifier_kwargs = self.config.to_verifier_kwargs()
        logger.debug("Creating JWTVerifier with kwargs: %s", verifier_kwargs)

        try:
            verifier = JWTVerifier(**verifier_kwargs)
            logger.info("Successfully created JWTVerifier")
            return verifier
        except Exception as e:
            logger.error("Failed to create JWTVerifier: %s", e)
            raise

    @classmethod
    def from_secret(cls, secret: str, algorithm: str = "HS256", **kwargs: Any) -> "JWTAuthProvider":
        """
        Create JWT provider with a secret key (for HMAC algorithms).

        This is a convenience method for creating a provider with HMAC-based
        algorithms (HS256, HS384, HS512).

        Args:
            secret: Secret key for HMAC algorithms
            algorithm: JWT algorithm (default: HS256)
            **kwargs: Additional configuration options

        Returns:
            JWTAuthProvider instance

        Example:
            >>> provider = JWTAuthProvider.from_secret(
            ...     secret="my-secret-key",
            ...     algorithm="HS256",
            ...     issuer="https://auth.example.com",
            ...     verify_exp=True
            ... )
        """
        logger.info("Creating JWT provider with secret (algorithm: %s)", algorithm)
        config = JWTConfig(secret=secret, algorithm=algorithm, **kwargs)
        return cls(config=config)

    @classmethod
    def from_public_key(cls, public_key: str, algorithm: str = "RS256", **kwargs: Any) -> "JWTAuthProvider":
        """
        Create JWT provider with a public key (for RSA/ECDSA algorithms).

        This is a convenience method for creating a provider with asymmetric
        algorithms (RS256, ES256, PS256, etc.).

        Args:
            public_key: Public key for RSA/ECDSA algorithms (PEM format)
            algorithm: JWT algorithm (default: RS256)
            **kwargs: Additional configuration options

        Returns:
            JWTAuthProvider instance

        Example:
            >>> public_key = '''-----BEGIN PUBLIC KEY-----
            ... MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA...
            ... -----END PUBLIC KEY-----'''
            >>>
            >>> provider = JWTAuthProvider.from_public_key(
            ...     public_key=public_key,
            ...     algorithm="RS256",
            ...     issuer="https://auth.example.com",
            ...     audience="my-api"
            ... )
        """
        logger.info("Creating JWT provider with public key (algorithm: %s)", algorithm)
        config = JWTConfig(public_key=public_key, algorithm=algorithm, **kwargs)
        return cls(config=config)

    @classmethod
    def from_env(cls, prefix: str = "JWT_") -> "JWTAuthProvider":
        """
        Create JWT provider from environment variables.

        Args:
            prefix: Prefix for environment variables (default: JWT_)

        Returns:
            JWTAuthProvider instance loaded from environment

        Example:
            >>> # Set environment variables
            >>> import os
            >>> os.environ["JWT_SECRET"] = "my-secret"
            >>> os.environ["JWT_ALGORITHM"] = "HS256"
            >>>
            >>> # Create provider
            >>> provider = JWTAuthProvider.from_env()
        """
        logger.info("Creating JWT provider from environment (prefix: %s)", prefix)
        config = JWTConfig.from_env(prefix=prefix)
        return cls(config=config)

    def refresh_verifier(self) -> JWTVerifier:
        """
        Force recreation of the JWTVerifier instance.

        This is useful if configuration has changed and you need to
        recreate the verifier with new settings.

        Returns:
            New JWTVerifier instance

        Example:
            >>> provider = JWTAuthProvider.from_secret("old-secret")
            >>>
            >>> # Update config
            >>> provider.config.secret = "new-secret"
            >>>
            >>> # Refresh verifier with new config
            >>> new_verifier = provider.refresh_verifier()
        """
        logger.info("Refreshing JWTVerifier instance")
        self._verifier = None
        return self.get_verifier()

    def validate_config(self) -> bool:
        """
        Validate the current configuration.

        Returns:
            True if configuration is valid

        Raises:
            ValueError: If configuration is invalid

        Example:
            >>> provider = JWTAuthProvider.from_secret("my-secret")
            >>> if provider.validate_config():
            ...     print("Configuration is valid")
        """
        try:
            # Try to create a verifier to validate config
            self._create_verifier()
            logger.info("JWT configuration is valid")
            return True
        except Exception as e:
            logger.error("JWT configuration is invalid: %s", e)
            raise ValueError(f"Invalid JWT configuration: {e}") from e
