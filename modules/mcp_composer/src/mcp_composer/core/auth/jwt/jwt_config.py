"""JWT configuration models for MCP Composer."""

from pydantic import BaseModel, Field, field_validator, model_validator
import os


class JWTConfig(BaseModel):
    """
    Configuration for JWT authentication.

    This class defines all configuration options for JWT token verification
    including algorithm selection, validation options, and token extraction settings.

    Note:
        HMAC algorithms (HS256, HS384, HS512) are supported for utility functions
        but NOT for FastMCP integration, which requires asymmetric keys (RS256, ES256, PS256).
        Use asymmetric algorithms for production FastMCP deployments.

    Attributes:
        secret: Secret key for HMAC algorithms (HS256, HS384, HS512)
        public_key: Public key for RSA/ECDSA algorithms (RS256, ES256, PS256)
        algorithm: JWT signing algorithm (default: HS256)
        issuer: Expected token issuer (iss claim)
        audience: Expected token audience (aud claim)
        verify_exp: Whether to verify token expiration
        verify_iss: Whether to verify token issuer
        verify_aud: Whether to verify token audience
        verify_signature: Whether to verify token signature
        header_name: HTTP header containing JWT (default: Authorization)
        header_prefix: Token prefix in header (default: Bearer)
        required_claims: List of required claims in JWT
        leeway: Leeway in seconds for exp/nbf/iat validation

    Example:
        >>> config = JWTConfig(
        ...     secret="my-secret-key",
        ...     algorithm="HS256",
        ...     issuer="https://auth.example.com",
        ...     verify_exp=True
        ... )
        >>>
        >>> # Or load from environment
        >>> config = JWTConfig.from_env(prefix="JWT_")
    """

    # Secret or public key (one required)
    secret: str | None = Field(
        None, description="Secret key for HS256/HS384/HS512 algorithms"
    )
    public_key: str | None = Field(
        None, description="Public key for RS256/ES256/PS256 algorithms"
    )

    # Algorithm
    algorithm: str = Field(
        default="HS256", description="JWT signing algorithm (HS256, RS256, ES256, etc.)"
    )

    # Validation options
    issuer: str | None = Field(None, description="Expected token issuer (iss claim)")
    audience: str | None = Field(
        None, description="Expected token audience (aud claim)"
    )
    verify_exp: bool = Field(default=True, description="Verify token expiration")
    verify_iss: bool = Field(default=False, description="Verify token issuer")
    verify_aud: bool = Field(default=False, description="Verify token audience")
    verify_signature: bool = Field(default=True, description="Verify token signature")

    # Token extraction
    header_name: str = Field(
        default="Authorization", description="HTTP header containing JWT"
    )
    header_prefix: str = Field(default="Bearer", description="Token prefix in header")

    # Additional options
    required_claims: list[str] = Field(
        default_factory=list, description="List of required claims in JWT"
    )
    leeway: int = Field(
        default=0, description="Leeway in seconds for exp/nbf/iat validation"
    )

    @field_validator("public_key")
    @classmethod
    def validate_public_key_format(cls, v):
        """Validate PEM format for public key."""
        if v:
            v_stripped = v.strip()
            if not (v_stripped.startswith("-----BEGIN") and "-----END" in v_stripped):
                raise ValueError(
                    "Invalid PEM key format. Key must contain BEGIN and END markers "
                    "(e.g., '-----BEGIN PUBLIC KEY-----' and '-----END PUBLIC KEY-----')"
                )
        return v

    @field_validator("secret")
    @classmethod
    def validate_secret_length(cls, v):
        """Validate minimum length for secrets."""
        if v and len(v) < 32:
            raise ValueError(
                "Secret key must be at least 32 characters long for security. "
                f"Current length: {len(v)}"
            )
        return v

    @model_validator(mode="after")
    def validate_key_presence(self):
        """Ensure at least one of secret or public_key is provided."""
        if not self.secret and not self.public_key:
            raise ValueError("Either secret or public_key must be provided")
        return self

    @field_validator("algorithm")
    @classmethod
    def validate_algorithm(cls, v):
        """Validate JWT algorithm."""
        valid_algorithms = [
            "HS256",
            "HS384",
            "HS512",  # HMAC
            "RS256",
            "RS384",
            "RS512",  # RSA
            "ES256",
            "ES384",
            "ES512",  # ECDSA
            "PS256",
            "PS384",
            "PS512",  # RSA-PSS
        ]
        if v not in valid_algorithms:
            raise ValueError(
                f"Invalid algorithm: {v}. Must be one of {valid_algorithms}"
            )
        return v

    @classmethod
    def from_env(cls, prefix: str = "JWT_") -> "JWTConfig":
        """
        Load configuration from environment variables.

        Args:
            prefix: Prefix for environment variables (default: JWT_)

        Note:
            The prefix will be automatically normalized to end with underscore.

        Returns:
            JWTConfig instance loaded from environment

        Environment Variables:
            {PREFIX}SECRET: Secret key for HMAC algorithms
            {PREFIX}PUBLIC_KEY: Public key for RSA/ECDSA algorithms
            {PREFIX}ALGORITHM: JWT algorithm (default: HS256)
            {PREFIX}ISSUER: Expected token issuer
            {PREFIX}AUDIENCE: Expected token audience
            {PREFIX}VERIFY_EXP: Verify expiration (default: true)
            {PREFIX}VERIFY_ISS: Verify issuer (default: false)
            {PREFIX}VERIFY_AUD: Verify audience (default: false)
            {PREFIX}VERIFY_SIGNATURE: Verify signature (default: true)
            {PREFIX}HEADER_NAME: Header name (default: Authorization)
            {PREFIX}HEADER_PREFIX: Header prefix (default: Bearer)
            {PREFIX}REQUIRED_CLAIMS: Comma-separated required claims
            {PREFIX}LEEWAY: Leeway in seconds (default: 0)

        Example:
            >>> # Set environment variables
            >>> os.environ["JWT_SECRET"] = "my-secret"
            >>> os.environ["JWT_ALGORITHM"] = "HS256"
            >>>
            >>> # Load config
            >>> config = JWTConfig.from_env()
        """
        # Normalize prefix to ensure it ends with underscore
        if prefix and not prefix.endswith("_"):
            prefix = f"{prefix}_"

        def get_bool(key: str, default: bool) -> bool:
            """Get boolean from environment."""
            value = os.getenv(f"{prefix}{key}")
            if value is None:
                return default
            return value.lower() in ("true", "1", "yes", "on")

        def get_list(key: str) -> list[str]:
            """Get list from comma-separated environment variable."""
            value = os.getenv(f"{prefix}{key}", "")
            return [item.strip() for item in value.split(",") if item.strip()]

        return cls(
            secret=os.getenv(f"{prefix}SECRET"),
            public_key=os.getenv(f"{prefix}PUBLIC_KEY"),
            algorithm=os.getenv(f"{prefix}ALGORITHM", "HS256"),
            issuer=os.getenv(f"{prefix}ISSUER"),
            audience=os.getenv(f"{prefix}AUDIENCE"),
            verify_exp=get_bool("VERIFY_EXP", True),
            verify_iss=get_bool("VERIFY_ISS", False),
            verify_aud=get_bool("VERIFY_AUD", False),
            verify_signature=get_bool("VERIFY_SIGNATURE", True),
            header_name=os.getenv(f"{prefix}HEADER_NAME", "Authorization"),
            header_prefix=os.getenv(f"{prefix}HEADER_PREFIX", "Bearer"),
            required_claims=get_list("REQUIRED_CLAIMS"),
            leeway=int(os.getenv(f"{prefix}LEEWAY", "0")),
        )

    def to_verifier_kwargs(self) -> dict:
        """
        Convert config to kwargs for FastMCP's JWTVerifier.

        FastMCP's JWTVerifier only accepts:
        - public_key, jwks_uri, issuer, audience, algorithm, required_scopes, base_url

        Returns:
            Dictionary of kwargs for JWTVerifier initialization
        """
        kwargs: dict[str, str | list[str]] = {}

        # Add algorithm
        if self.algorithm:
            kwargs["algorithm"] = self.algorithm

        # Add public key (FastMCP doesn't support 'secret' for HMAC)
        if self.public_key:
            kwargs["public_key"] = self.public_key

        # Add optional parameters
        if self.issuer:
            kwargs["issuer"] = self.issuer
        if self.audience:
            kwargs["audience"] = self.audience

        # Convert required_claims to required_scopes (FastMCP uses scopes)
        if self.required_claims:
            kwargs["required_scopes"] = (
                self.required_claims
                if isinstance(self.required_claims, list)
                else [self.required_claims]
            )

        return kwargs
