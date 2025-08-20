"""
Identity manager for extracting and managing user identity information.
Inspired by permit-fastmcp's comprehensive identity extraction approach.
"""

import re
import jwt
from typing import Dict, Any, Optional, Tuple
from .config import SETTINGS, IdentityMode, Settings
from .schemas import AuthContext
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class IdentityManager:
    """Manages user identity extraction and authentication."""

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the identity manager.

        Args:
            settings: Configuration settings (uses global SETTINGS if None)
        """
        self.settings = settings or SETTINGS
        logger.info(
            f"Identity manager initialized with mode: {self.settings.identity_mode}"
        )

    def extract_identity(self, context: Any) -> Tuple[str, Dict[str, Any]]:
        """
        Extract user identity from context based on configured mode.

        Args:
            context: Middleware context containing request information

        Returns:
            Tuple of (user_id, attributes)
        """
        try:
            if self.settings.identity_mode == IdentityMode.jwt:
                return self._extract_jwt_identity(context)
            elif self.settings.identity_mode == IdentityMode.fixed:
                return self._extract_fixed_identity(context)
            elif self.settings.identity_mode == IdentityMode.header:
                return self._extract_header_identity(context)
            elif self.settings.identity_mode == IdentityMode.source:
                return self._extract_source_identity(context)
            elif self.settings.identity_mode == IdentityMode.api_key:
                return self._extract_api_key_identity(context)
            else:
                logger.warning(f"Unknown identity mode: {self.settings.identity_mode}")
                return "unknown", {"type": "unknown_mode"}
        except Exception as e:
            logger.error(f"Error extracting identity: {e}")
            return "unknown", {"type": "extraction_error", "error": str(e)}

    def _extract_jwt_identity(self, context: Any) -> Tuple[str, Dict[str, Any]]:
        """Extract identity from JWT token."""
        headers = self._get_headers(context)

        # Get JWT from header
        header_val = headers.get(self.settings.identity_header) or headers.get(
            self.settings.identity_header.lower()
        )

        if not header_val:
            return "unknown", {"type": "missing_jwt_header"}

        # Extract token using regex
        match = re.match(self.settings.identity_header_regex, header_val)
        if not match:
            return "unknown", {"type": "invalid_jwt_header_format"}

        token = match.group(1)

        try:
            # Decode JWT
            if self.settings.identity_jwt_secret:
                payload = jwt.decode(
                    token,
                    self.settings.identity_jwt_secret,
                    algorithms=self.settings.jwt_algorithms,
                    options={"verify_signature": True},
                )
            else:
                # Decode without verification (for development/testing)
                payload = jwt.decode(token, options={"verify_signature": False})

            # Extract user ID from configured field
            user_id = payload.get(self.settings.identity_jwt_field, "unknown")

            # Extract additional attributes
            attributes = {
                "type": "jwt",
                "jwt_payload": payload,
                "roles": payload.get("roles", []),
                "permissions": payload.get("permissions", []),
                "tenant": payload.get("tenant"),
                "audience": payload.get("aud"),
                "issuer": payload.get("iss"),
                "expires_at": payload.get("exp"),
                "issued_at": payload.get("iat"),
            }

            logger.debug(f"Extracted JWT identity: {user_id}")
            return user_id, attributes

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return "unknown", {"type": "jwt_expired"}
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return "unknown", {"type": "jwt_invalid", "error": str(e)}
        except Exception as e:
            logger.error(f"Error decoding JWT: {e}")
            return "unknown", {"type": "jwt_decode_error", "error": str(e)}

    def _extract_fixed_identity(self, context: Any) -> Tuple[str, Dict[str, Any]]:
        """Extract fixed identity value."""
        user_id = self.settings.identity_fixed_value
        attributes = {
            "type": "fixed_identity",
            "mode": "fixed",
        }

        logger.debug(f"Using fixed identity: {user_id}")
        return user_id, attributes

    def _extract_header_identity(self, context: Any) -> Tuple[str, Dict[str, Any]]:
        """Extract identity from header."""
        headers = self._get_headers(context)

        user_id = headers.get(self.settings.identity_header) or headers.get(
            self.settings.identity_header.lower()
        )

        if not user_id:
            return "unknown", {"type": "missing_header_identity"}

        attributes = {
            "type": "header_identity",
            "header": self.settings.identity_header,
        }

        logger.debug(f"Extracted header identity: {user_id}")
        return user_id, attributes

    def _extract_source_identity(self, context: Any) -> Tuple[str, Dict[str, Any]]:
        """Extract identity from context source."""
        source = getattr(context, "source", None)

        if not source:
            return "unknown", {"type": "missing_source"}

        user_id = str(source)
        attributes = {
            "type": "source_identity",
            "source": source,
        }

        logger.debug(f"Extracted source identity: {user_id}")
        return user_id, attributes

    def _extract_api_key_identity(self, context: Any) -> Tuple[str, Dict[str, Any]]:
        """Extract identity from API key."""
        headers = self._get_headers(context)

        api_key = headers.get(self.settings.api_key_header) or headers.get(
            self.settings.api_key_header.lower()
        )

        if not api_key:
            return "unknown", {"type": "missing_api_key"}

        # Map API key to user ID (in production, you'd validate against a database)
        # For demo purposes, we'll use the API key as the user ID
        user_id = api_key
        attributes = {
            "type": "api_key_identity",
            "api_key": api_key,
            "header": self.settings.api_key_header,
        }

        logger.debug(f"Extracted API key identity: {user_id}")
        return user_id, attributes

    def _get_headers(self, context: Any) -> Dict[str, str]:
        """Extract headers from context."""
        headers: Dict[str, str] = {}

        # Try different ways to get headers
        if hasattr(context, "headers"):
            headers = context.headers or {}
        elif hasattr(context, "fastmcp_context"):
            if hasattr(context.fastmcp_context, "request_context"):
                if hasattr(context.fastmcp_context.request_context, "request"):
                    if hasattr(
                        context.fastmcp_context.request_context.request, "headers"
                    ):
                        headers = (
                            context.fastmcp_context.request_context.request.headers
                            or {}
                        )

        return headers

    def create_auth_context(self, context: Any) -> AuthContext:
        """
        Create an AuthContext from the given context.

        Args:
            context: Middleware context

        Returns:
            AuthContext with extracted identity information
        """
        user_id, attributes = self.extract_identity(context)

        # Determine authentication status
        authenticated = user_id != "unknown" and attributes.get("type") not in [
            "missing_jwt_header",
            "missing_header_identity",
            "missing_api_key",
            "missing_source",
        ]

        # Extract roles from attributes
        roles = attributes.get("roles", [])
        if not roles and authenticated:
            # Fallback to default role
            roles = [self.settings.default_user_role]

        # Extract agent ID
        agent_id = attributes.get("agent_id") or attributes.get("sub")

        # Determine auth method
        auth_method = self.settings.identity_mode.value

        return AuthContext(
            user_id=user_id,
            roles=roles,
            agent_id=agent_id,
            authenticated=authenticated,
            auth_method=auth_method,
            metadata=attributes,
        )

    def validate_api_key(self, api_key: str) -> bool:
        """
        Validate an API key (placeholder for production implementation).

        Args:
            api_key: The API key to validate

        Returns:
            True if valid, False otherwise
        """
        # In production, you would validate against a database or external service
        # For demo purposes, we'll accept any non-empty API key
        return bool(api_key and api_key.strip())

    def get_user_permissions(self, user_id: str) -> Dict[str, Any]:
        """
        Get user permissions (placeholder for production implementation).

        Args:
            user_id: User identifier

        Returns:
            Dictionary containing user permissions
        """
        # In production, you would fetch from a database or external service
        # For demo purposes, return empty permissions
        return {
            "permissions": [],
            "roles": [self.settings.default_user_role],
            "metadata": {},
        }

    def resolve_role_from_context(self, context: dict) -> str:
        """
        Derives the effective role from context. Supports:
        - agent_type (e.g., 'worker', 'supervisor') => agent_worker, agent_supervisor
        - fallback to 'role' field if available
        - default to 'end_user'
        """
        if "agent_type" in context:
            return f"agent_{context['agent_type']}"
        if "role" in context:
            return context["role"]
        return "end_user"
