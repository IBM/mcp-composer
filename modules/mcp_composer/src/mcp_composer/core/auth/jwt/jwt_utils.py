"""JWT utility functions for token manipulation and validation."""

from typing import Dict, Any, Optional, List
import jwt
from datetime import datetime, timedelta, timezone
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

# Token expiration constants
DEFAULT_TOKEN_EXPIRATION_SECONDS = 3600  # 1 hour


def extract_jwt_from_header(header_value: str, prefix: str = "Bearer") -> Optional[str]:
    """
    Extract JWT token from Authorization header.

    Args:
        header_value: Authorization header value (e.g., "Bearer eyJhbGc...")
        prefix: Token prefix (default: "Bearer")

    Returns:
        JWT token string or None if not found/invalid format

    Example:
        >>> header = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        >>> token = extract_jwt_from_header(header)
        >>> print(token)  # eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    """
    if not header_value:
        logger.debug("Empty authorization header")
        return None

    parts = header_value.strip().split()
    if len(parts) != 2:
        logger.warning("Invalid authorization header format: expected 2 parts, got %d", len(parts))
        return None

    if parts[0] != prefix:
        logger.warning("Invalid authorization prefix: expected '%s', got '%s'", prefix, parts[0])
        return None

    logger.debug("Successfully extracted JWT token from header")
    return parts[1]


def decode_jwt_token(
    token: str,
    secret: Optional[str] = None,
    public_key: Optional[str] = None,
    algorithm: str = "HS256",
    verify: bool = True,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
    leeway: int = 0,
    **options: Any,
) -> Dict[str, Any]:
    """
    Decode and optionally verify a JWT token.

    Args:
        token: JWT token string
        secret: Secret key for HMAC algorithms
        public_key: Public key for RSA/ECDSA algorithms
        algorithm: JWT algorithm
        verify: Whether to verify signature
        issuer: Expected issuer (iss claim)
        audience: Expected audience (aud claim)
        leeway: Leeway in seconds for time-based claims
        **options: Additional JWT decode options

    Returns:
        Decoded JWT claims as dictionary

    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidTokenError: If token is invalid
        jwt.InvalidIssuerError: If issuer doesn't match
        jwt.InvalidAudienceError: If audience doesn't match

    Example:
        >>> token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        >>> claims = decode_jwt_token(
        ...     token,
        ...     secret="my-secret",
        ...     algorithm="HS256",
        ...     verify=True
        ... )
        >>> print(claims["sub"])  # user@example.com
    """
    key = secret or public_key
    if not key and verify:
        raise ValueError("Secret or public_key required for verification")

    decode_options = {"verify_signature": verify}
    decode_options.update(options)

    decode_kwargs: Dict[str, Any] = {
        "algorithms": [algorithm],
        "options": decode_options,
    }

    # Add optional validation parameters
    if issuer:
        decode_kwargs["issuer"] = issuer
    if audience:
        decode_kwargs["audience"] = audience
    if leeway:
        decode_kwargs["leeway"] = leeway

    try:
        claims = jwt.decode(token, key, **decode_kwargs)
        logger.debug("Successfully decoded JWT token with %d claims", len(claims))
        return claims
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token has expired")
        raise
    except jwt.InvalidIssuerError as e:
        logger.warning("JWT issuer validation failed: %s", e)
        raise
    except jwt.InvalidAudienceError as e:
        logger.warning("JWT audience validation failed: %s", e)
        raise
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT token: %s", e)
        raise


def generate_jwt_token(
    payload: Dict[str, Any],
    secret: str,
    algorithm: str = "HS256",
    expires_in: int = DEFAULT_TOKEN_EXPIRATION_SECONDS,
    issuer: Optional[str] = None,
    audience: Optional[str] = None,
) -> str:
    """
    Generate a JWT token with the given payload.

    Args:
        payload: JWT claims to encode
        secret: Secret key for signing
        algorithm: JWT algorithm (default: HS256)
        expires_in: Token expiration in seconds (default: 3600)
        issuer: Token issuer (iss claim)
        audience: Token audience (aud claim)

    Returns:
        Encoded JWT token string

    Example:
        >>> payload = {
        ...     "sub": "user@example.com",
        ...     "name": "John Doe",
        ...     "role": "admin"
        ... }
        >>> token = generate_jwt_token(
        ...     payload,
        ...     secret="my-secret",
        ...     expires_in=3600,
        ...     issuer="https://auth.example.com"
        ... )
    """
    payload = payload.copy()
    now = datetime.now(timezone.utc)

    # Add standard claims
    payload.setdefault("iat", int(now.timestamp()))
    payload.setdefault("exp", int((now + timedelta(seconds=expires_in)).timestamp()))

    if issuer:
        payload.setdefault("iss", issuer)
    if audience:
        payload.setdefault("aud", audience)

    try:
        token = jwt.encode(payload, secret, algorithm=algorithm)
        logger.debug("Generated JWT token with expiration: %d seconds, claims: %d", expires_in, len(payload))
        return token
    except Exception as e:
        logger.error("Failed to generate JWT token: %s", e)
        raise


def validate_jwt_claims(claims: Dict[str, Any], required_claims: List[str]) -> bool:
    """
    Validate that required claims are present in JWT.

    Args:
        claims: Decoded JWT claims
        required_claims: List of required claim names

    Returns:
        True if all required claims are present, False otherwise

    Example:
        >>> claims = {"sub": "user@example.com", "role": "admin"}
        >>> required = ["sub", "role", "tenant"]
        >>> is_valid = validate_jwt_claims(claims, required)
        >>> print(is_valid)  # False (missing 'tenant')
    """
    if not required_claims:
        logger.warning("No required claims specified for JWT validation - validation skipped")
        return True
    
    missing_claims = [claim for claim in required_claims if claim not in claims]

    if missing_claims:
        logger.warning("Missing required JWT claims: %s", missing_claims)
        return False

    logger.debug("All required JWT claims are present")
    return True


def decode_jwt_without_verification(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode a JWT token without signature verification.
    
    This helper function can be reused to avoid redundant decoding operations
    when multiple functions need to inspect the same token.
    
    Args:
        token: JWT token string
        
    Returns:
        Dictionary of claims or None if decoding fails
        
    Example:
        >>> token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        >>> claims = decode_jwt_without_verification(token)
        >>> if claims:
        ...     print(claims.get("sub"))
    """
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
        logger.debug("Successfully decoded JWT without verification")
        return claims
    except Exception as e:
        logger.error("Failed to decode JWT: %s", e)
        return None


def get_jwt_expiration(token: str) -> Optional[datetime]:
    """
    Get the expiration time from a JWT token without verification.

    Args:
        token: JWT token string

    Returns:
        Expiration datetime or None if not present

    Example:
        >>> token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        >>> exp_time = get_jwt_expiration(token)
        >>> if exp_time:
        ...     print(f"Token expires at: {exp_time}")
    """
    claims = decode_jwt_without_verification(token)
    if not claims:
        return None
        
    try:
        exp = claims.get("exp")

        if exp:
            exp_datetime = datetime.fromtimestamp(exp)
            logger.debug("JWT expiration: %s", exp_datetime)
            return exp_datetime

        logger.debug("JWT has no expiration claim")
        return None
    except Exception as e:
        logger.error("Failed to get JWT expiration: %s", e)
        return None


def is_jwt_expired(token: str, leeway: int = 0) -> bool:
    """
    Check if a JWT token is expired without full verification.

    Args:
        token: JWT token string
        leeway: Leeway in seconds to account for clock skew

    Returns:
        True if token is expired, False otherwise

    Example:
        >>> token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        >>> if is_jwt_expired(token):
        ...     print("Token has expired")
    """
    exp_time = get_jwt_expiration(token)
    if not exp_time:
        # No expiration claim, consider it not expired
        return False

    now = datetime.now(timezone.utc)
    is_expired = (exp_time + timedelta(seconds=leeway)) < now

    if is_expired:
        logger.debug("JWT token is expired (exp: %s, now: %s)", exp_time, now)

    return is_expired


def extract_jwt_claims(token: str, claim_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Extract specific claims from a JWT token without verification.

    Useful for inspecting tokens without validating signatures.

    Args:
        token: JWT token string
        claim_names: List of claim names to extract (None = all claims)

    Returns:
        Dictionary of extracted claims

    Example:
        >>> token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        >>> claims = extract_jwt_claims(token, ["sub", "role", "tenant"])
        >>> print(claims)  # {"sub": "user@example.com", "role": "admin", ...}
    """
    all_claims = decode_jwt_without_verification(token)
    if not all_claims:
        return {}
        
    try:

        if claim_names is None:
            return all_claims

        # Extract only requested claims
        extracted = {name: all_claims.get(name) for name in claim_names if name in all_claims}

        logger.debug("Extracted %d claims from JWT", len(extracted))
        return extracted
    except Exception as e:
        logger.error("Failed to extract JWT claims: %s", e)
        return {}
