import httpx
import json
from typing import Dict, Any, Optional
from .base_policy_enforcer import BasePolicyEnforcer
from ..acl_utils import resolve_role_from_context, extract_context_info
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class OPARegoPolicyEnforcer(BasePolicyEnforcer):
    """
    Policy enforcer that queries Open Policy Agent (OPA) using Rego policies.

    Expected OPA query format:
    POST /v1/data/mcp/allow
    {
        "input": {
            "tool": "tool_name",
            "role": "user_role",
            "user_id": "user123",
            "project": "project_name",
            "agent_type": "chatbot"
        }
    }

    Expected OPA response:
    {
        "result": true
    }
    """

    def __init__(
        self,
        opa_url: str = "http://localhost:8181",
        policy_path: str = "mcp/allow",
        **kwargs: Any,
    ):
        """
        Initialize the OPA policy enforcer.

        Args:
            opa_url: URL of the OPA server
            policy_path: Path to the policy rule (e.g., "mcp/allow")
            **kwargs: Additional configuration options
        """
        self.opa_url = opa_url.rstrip("/")
        self.policy_path = policy_path
        self.timeout = kwargs.get("timeout", 10.0)
        self.verify_ssl = kwargs.get("verify_ssl", True)

        # Build the full query URL
        self.query_url = f"{self.opa_url}/v1/data/{self.policy_path}"

        logger.info(f"Initialized OPA policy enforcer - URL: {self.query_url}")

    async def _query_opa(self, input_data: Dict[str, Any]) -> Optional[bool]:
        """
        Query OPA server for policy decision.

        Args:
            input_data: Input data for the policy query

        Returns:
            Policy decision (True/False) or None if query failed
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, verify=self.verify_ssl
            ) as client:
                response = await client.post(
                    self.query_url,
                    json={"input": input_data},
                    headers={"Content-Type": "application/json"},
                )

                if response.status_code == 200:
                    result = response.json()
                    # OPA returns {"result": true/false}
                    return result.get("result", False)
                else:
                    logger.error(
                        f"OPA query failed with status {response.status_code}: {response.text}"
                    )
                    return None

        except httpx.TimeoutException:
            logger.error(f"OPA query timed out after {self.timeout} seconds")
            return None
        except httpx.RequestError as e:
            logger.error(f"OPA request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error querying OPA: {e}")
            return None

    def is_allowed(self, tool_name: str, context: Dict[str, Any]) -> bool:
        """
        Check if the tool is allowed using OPA policy.

        Args:
            tool_name: Name of the tool being accessed
            context: Request context containing user and request information

        Returns:
            bool: True if access is allowed, False otherwise
        """
        # Extract context information
        context_info = extract_context_info(context)

        # Prepare input data for OPA
        input_data = {
            "tool": tool_name,
            "role": context_info["role"],
            "user_id": context_info["user_id"],
            "project": context_info["project"],
            "agent_type": context_info["agent_type"],
            "resource_type": context_info["resource_type"],
            "timestamp": context_info["timestamp"],
        }

        # Remove None values
        input_data = {k: v for k, v in input_data.items() if v is not None}

        # Query OPA (this is async but we need to handle it synchronously)
        # For now, we'll use a simple fallback approach
        # In a real implementation, you might want to use asyncio.run() or make this method async

        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, we can't use asyncio.run()
                # For now, fall back to a simple role-based check
                logger.warning(
                    "OPA query called from async context, falling back to role-based check"
                )
                return self._fallback_check(tool_name, context_info)
            else:
                result = asyncio.run(self._query_opa(input_data))
        except RuntimeError:
            # No event loop available, fall back to simple check
            logger.warning(
                "No event loop available for OPA query, falling back to role-based check"
            )
            return self._fallback_check(tool_name, context_info)

        if result is None:
            logger.warning("OPA query returned None, falling back to role-based check")
            return self._fallback_check(tool_name, context_info)

        logger.debug(
            f"OPA policy check - Tool: {tool_name}, "
            f"Allowed: {result}, Context: {context_info}"
        )

        return result

    def _fallback_check(self, tool_name: str, context_info: Dict[str, Any]) -> bool:
        """
        Fallback policy check when OPA is unavailable.

        Args:
            tool_name: Name of the tool being accessed
            context_info: Extracted context information

        Returns:
            bool: True if access is allowed, False otherwise
        """
        # Simple fallback: admin role gets access to everything
        if context_info["role"] == "admin":
            return True

        # For other roles, deny by default (fail secure)
        logger.warning(
            f"Fallback policy check - denying access to {tool_name} for role {context_info['role']}"
        )
        return False

    async def is_allowed_async(self, tool_name: str, context: Dict[str, Any]) -> bool:
        """
        Async version of is_allowed for use in async contexts.

        Args:
            tool_name: Name of the tool being accessed
            context: Request context containing user and request information

        Returns:
            bool: True if access is allowed, False otherwise
        """
        context_info = extract_context_info(context)

        input_data = {
            "tool": tool_name,
            "role": context_info["role"],
            "user_id": context_info["user_id"],
            "project": context_info["project"],
            "agent_type": context_info["agent_type"],
            "resource_type": context_info["resource_type"],
            "timestamp": context_info["timestamp"],
        }

        input_data = {k: v for k, v in input_data.items() if v is not None}

        result = await self._query_opa(input_data)

        if result is None:
            logger.warning("OPA query returned None, falling back to role-based check")
            return self._fallback_check(tool_name, context_info)

        logger.debug(
            f"OPA policy check (async) - Tool: {tool_name}, "
            f"Allowed: {result}, Context: {context_info}"
        )

        return result
