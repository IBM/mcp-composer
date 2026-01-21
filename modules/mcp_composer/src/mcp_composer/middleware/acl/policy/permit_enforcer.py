from typing import Dict, Any, Optional
from mcp_composer.core.utils.logger import LoggerFactory
from mcp_composer.middleware.acl.policy.base_policy_enforcer import BasePolicyEnforcer
from mcp_composer.middleware.acl.acl_utils import extract_context_info

logger = LoggerFactory.get_logger()


class PermitPolicyEnforcer(BasePolicyEnforcer):
    """
    Policy enforcer that wraps Permit.io's PermitMcpMiddleware.

    This is an optional enforcer that requires the permit-fastmcp package.
    """

    def __init__(
        self,
        permit_url: str = "https://cloud.permit.io",
        api_key: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Initialize the Permit policy enforcer.

        Args:
            permit_url: Permit.io API URL
            api_key: Permit.io API key
            **kwargs: Additional configuration options
        """
        self.permit_url = permit_url
        self.api_key = api_key or kwargs.get("api_key")
        self.permit_middleware = None
        self._initialize_permit()

        logger.info("Initialized Permit policy enforcer - URL: %s", permit_url)

    def _initialize_permit(self) -> None:
        """Initialize the Permit middleware."""
        try:
            from permit_fastmcp import PermitMcpMiddleware  # type: ignore

            if not self.api_key:
                logger.error("Permit API key is required")
                return

            self.permit_middleware = PermitMcpMiddleware(
                permit_url=self.permit_url, api_key=self.api_key
            )

            logger.info("Successfully initialized Permit middleware")

        except ImportError:
            logger.error(
                "permit-fastmcp package not installed. "
                "Install with: pip install permit-fastmcp"
            )
            self.permit_middleware = None
        except Exception as e:
            logger.error("Failed to initialize Permit middleware: %s", e)
            self.permit_middleware = None

    def is_allowed(self, tool_name: str, context: Dict[str, Any]) -> bool:
        """
        Check if the tool is allowed using Permit.io policy.

        Args:
            tool_name: Name of the tool being accessed
            context: Request context containing user and request information

        Returns:
            bool: True if access is allowed, False otherwise
        """
        if not self.permit_middleware:
            logger.warning("Permit middleware not available, denying access")
            return False

        try:
            # Extract context information
            context_info = extract_context_info(context)

            # Prepare input for Permit
            input_data = {
                "tool": tool_name,
                "role": context_info["role"],
                "user_id": context_info["user_id"],
                "project": context_info["project"],
                "agent_type": context_info["agent_type"],
                "resource_type": context_info["resource_type"],
            }

            # Remove None values
            input_data = {k: v for k, v in input_data.items() if v is not None}

            # Use Permit middleware to check access
            # Note: This is a simplified interface - the actual PermitMcpMiddleware
            # might have a different API
            is_allowed = self.permit_middleware.check_access(input_data)

            logger.debug(
                "Permit policy check - Tool: %s, Allowed: %s, Context: %s",
                tool_name,
                is_allowed,
                context_info,
            )

            return is_allowed

        except Exception as e:
            logger.error("Error checking Permit policy: %s", e)
            return False

    def get_user_permissions(self, user_id: str) -> Dict[str, Any]:
        """
        Get user permissions from Permit.io.

        Args:
            user_id: User identifier

        Returns:
            Dict containing user permissions
        """
        if not self.permit_middleware:
            logger.warning("Permit middleware not available")
            return {}

        try:
            # This would use Permit's API to get user permissions
            # Implementation depends on the actual PermitMcpMiddleware interface
            permissions = self.permit_middleware.get_user_permissions(user_id)
            return permissions

        except Exception as e:
            logger.error("Error getting user permissions from Permit: %s", e)
            return {}
