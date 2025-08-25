import jwt
import json
from typing import Dict, Any, Optional, List
from .base_policy_enforcer import BasePolicyEnforcer
from ..acl_utils import resolve_role_from_context, extract_context_info
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class JWEJWTPolicyEnforcer(BasePolicyEnforcer):
    """
    Policy enforcer that validates JWT tokens and extracts allowed tools from claims.

    Expected JWT claims format:
    {
        "sub": "user123",
        "role": "admin",
        "allowed_tools": ["tool1", "tool2", "tool3"],
        "exp": 1234567890
    }
    """

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithms: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        """
        Initialize the JWT policy enforcer.

        Args:
            secret_key: Secret key for JWT verification (can be None for unverified tokens)
            algorithms: List of allowed JWT algorithms
            **kwargs: Additional configuration options
        """
        self.secret_key = secret_key or kwargs.get("secret_key")
        self.algorithms = algorithms or kwargs.get("algorithms", ["HS256", "RS256"])
        self.verify_signature = kwargs.get("verify_signature", True)

        logger.info(
            f"Initialized JWT policy enforcer with algorithms: {self.algorithms}"
        )

    def _extract_jwt_from_context(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Extract JWT token from context.

        Args:
            context: Request context

        Returns:
            JWT token string or None if not found
        """
        # Check for JWT in various locations
        if "token" in context:
            return context["token"]

        if "jwt" in context:
            return context["jwt"]

        if "headers" in context and isinstance(context["headers"], dict):
            headers = context["headers"]
            # Check Authorization header
            auth_header = headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                return auth_header[7:]  # Remove "Bearer " prefix

            # Check custom JWT header
            if "X-JWT-Token" in headers:
                return headers["X-JWT-Token"]

        return None

    def _decode_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and verify JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded claims or None if invalid
        """
        try:
            if self.verify_signature and self.secret_key:
                # Verify signature
                claims = jwt.decode(
                    token,
                    self.secret_key,
                    algorithms=self.algorithms,
                    options={"verify_signature": True},
                )
            else:
                # Decode without verification (for development/testing)
                claims = jwt.decode(token, options={"verify_signature": False})

            logger.debug(f"Successfully decoded JWT with claims: {list(claims.keys())}")
            return claims

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error decoding JWT: {e}")
            return None

    def is_allowed(self, tool_name: str, context: Dict[str, Any]) -> bool:
        """
        Check if the tool is allowed based on JWT claims.

        Args:
            tool_name: Name of the tool being accessed
            context: Request context containing JWT token

        Returns:
            bool: True if access is allowed, False otherwise
        """
        # Extract JWT from context
        token = self._extract_jwt_from_context(context)
        if not token:
            logger.warning("No JWT token found in context")
            return False

        # Decode JWT
        claims = self._decode_jwt(token)
        if not claims:
            logger.warning("Failed to decode JWT token")
            return False

        # Extract allowed tools from claims
        allowed_tools = claims.get("allowed_tools", [])
        if not isinstance(allowed_tools, list):
            logger.warning("allowed_tools in JWT claims is not a list")
            return False

        # Check if tool is allowed
        is_allowed = tool_name in allowed_tools

        # Extract additional context info for logging
        context_info = extract_context_info(context)
        context_info.update(
            {
                "jwt_subject": claims.get("sub"),
                "jwt_role": claims.get("role"),
                "jwt_allowed_tools_count": len(allowed_tools),
            }
        )

        logger.debug(
            f"JWT policy check - Tool: {tool_name}, "
            f"Allowed: {is_allowed}, Context: {context_info}"
        )

        return is_allowed

    def get_claims_from_context(
        self, context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Get JWT claims from context for debugging/inspection.

        Args:
            context: Request context

        Returns:
            JWT claims or None if not available
        """
        token = self._extract_jwt_from_context(context)
        if token:
            return self._decode_jwt(token)
        return None
