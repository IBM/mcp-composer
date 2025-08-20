"""
Policy-based Access Control Middleware for FastMCP servers.
Follows the adapter pattern to support multiple policy providers.
"""

import time
from typing import Any, Dict, Optional, Union, List

import mcp.types as mt
from fastmcp.server.middleware import (
    Middleware,
    MiddlewareContext,
    CallNext,
)
from fastmcp.exceptions import McpError  # type: ignore

from .identity_manager import IdentityManager
from .config import SETTINGS, PolicyMode
from .base_policy_enforcer import BasePolicyEnforcer
from .file_enforcer import FilePolicyEnforcer
from .jwt_enforcer import JWEJWTPolicyEnforcer
from .vault_enforcer import HashiCorpVaultPolicyEnforcer
from .opa_enforcer import OPARegoPolicyEnforcer
from .permit_enforcer import PermitPolicyEnforcer
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class PolicyMiddleware(Middleware):
    """
    Policy-based Access Control Middleware for MCP servers.

    Uses the adapter pattern to support multiple policy providers:
    - File-based policies
    - JWT-based policies
    - HashiCorp Vault policies
    - Open Policy Agent (OPA) policies
    - Permit.io policies

    Integrates with IdentityManager for identity extraction.
    """

    def __init__(
        self,
        mode: Optional[Union[str, PolicyMode]] = None,
        policy_config: Optional[Dict[str, Any]] = None,
        enable_audit_logging: bool = True,
    ):
        """
        Initialize the policy middleware.

        Args:
            mode: Policy enforcement mode (file, jwt, vault, opa, permit)
            policy_config: Configuration for the selected policy provider
            enable_audit_logging: Whether to enable audit logging
        """
        # Determine mode
        self.mode = mode or SETTINGS.mode
        if isinstance(self.mode, str):
            self.mode = PolicyMode(self.mode)
        elif isinstance(self.mode, PolicyMode):
            self.mode = self.mode
        else:
            self.mode = PolicyMode.file  # Default fallback

        # Initialize identity manager
        self.identity_manager = IdentityManager()

        # Initialize policy enforcer based on mode
        self.policy_enforcer = self._initialize_enforcer(policy_config or {})

        # Configuration
        self.enable_audit_logging = enable_audit_logging

        # Metrics
        self.total_requests = 0
        self.allowed_requests = 0
        self.denied_requests = 0

        logger.info(
            f"Policy middleware initialized with mode: {self._get_mode_name()}, "
            f"enforcer: {type(self.policy_enforcer).__name__}"
        )

    def _get_mode_name(self) -> str:
        """Get the mode name as a string."""
        if hasattr(self.mode, "value"):
            return self.mode.value
        return str(self.mode)

    def _initialize_enforcer(self, config: Dict[str, Any]) -> BasePolicyEnforcer:
        """
        Initialize the appropriate policy enforcer based on mode.

        Args:
            config: Configuration for the enforcer

        Returns:
            Initialized policy enforcer

        Raises:
            ValueError: If mode is not supported
        """
        try:
            if self.mode == PolicyMode.file:
                policy_path = config.get("policy_path", SETTINGS.policy_file_path)
                return FilePolicyEnforcer(policy_path)

            elif self.mode == PolicyMode.jwt:
                # JWT enforcer extracts token from context and checks claims
                # The secret is only used for verification, not as policy
                jwt_secret = config.get("jwt_secret", SETTINGS.identity_jwt_secret)
                algorithms = config.get("algorithms", SETTINGS.jwt_algorithms)
                verify_signature = config.get("verify_signature", True)
                return JWEJWTPolicyEnforcer(
                    secret_key=jwt_secret,
                    algorithms=algorithms,
                    verify_signature=verify_signature,
                )

            elif self.mode == PolicyMode.vault:
                vault_url = config.get("vault_url", SETTINGS.vault_url)
                vault_token = config.get("vault_token", SETTINGS.vault_token)
                mount_point = config.get("mount_point", SETTINGS.vault_mount_point)
                policy_path = config.get("policy_path", SETTINGS.vault_policy_path)
                return HashiCorpVaultPolicyEnforcer(
                    vault_url=vault_url,
                    token=vault_token,
                    mount_point=mount_point,
                    policy_path=policy_path,
                )

            elif self.mode == PolicyMode.opa:
                opa_url = config.get("opa_url", SETTINGS.opa_url)
                policy_path = config.get("policy_path", SETTINGS.opa_policy_path)
                timeout = config.get("timeout", SETTINGS.opa_timeout)
                return OPARegoPolicyEnforcer(opa_url, policy_path, timeout=timeout)

            elif self.mode == PolicyMode.permit:
                permit_url = config.get("permit_url", SETTINGS.permit_url)
                api_key = config.get("api_key", SETTINGS.permit_api_key)
                return PermitPolicyEnforcer(permit_url, api_key)

            else:
                raise ValueError(f"Unsupported policy mode: {self.mode}")

        except Exception as e:
            logger.error(f"Failed to initialize {self._get_mode_name()} enforcer: {e}")
            # Fallback to file enforcer
            logger.info("Falling back to file enforcer")
            return FilePolicyEnforcer(SETTINGS.policy_file_path)

    async def on_call_tool(
        self,
        context: MiddlewareContext[mt.CallToolRequestParams],
        call_next: CallNext[mt.CallToolRequestParams, Any],
    ) -> Any:
        """
        Middleware hook for tool calls.

        Args:
            context: Middleware context containing tool call information
            call_next: Function to call the next middleware/tool

        Returns:
            Tool call result

        Raises:
            McpError: If access is denied
        """
        self.total_requests += 1

        # Extract tool information
        tool_name = getattr(context.message, "name", "unknown_tool")
        arguments = getattr(context.message, "arguments", {})

        # Extract identity and create context
        auth_context = self.identity_manager.create_auth_context(context)

        # Build context for policy evaluation
        context_data = {
            "tool_name": tool_name,
            "arguments": arguments,
            "user_id": auth_context.user_id,
            "roles": auth_context.roles,
            "agent_id": auth_context.agent_id,
            "authenticated": auth_context.authenticated,
            "auth_method": auth_context.auth_method,
            "metadata": auth_context.metadata,
        }

        # Check authorization
        try:
            is_allowed = self.policy_enforcer.is_allowed(tool_name, context_data)
            logger.debug(
                f"Tool '{tool_name}' is {'allowed' if is_allowed else 'denied'} by {self._get_mode_name()} enforcer"
            )
            # Update metrics
            if is_allowed:
                self.allowed_requests += 1
            else:
                self.denied_requests += 1

            # Log decision
            if self.enable_audit_logging:
                self._log_access_event(
                    context,
                    tool_name,
                    auth_context.user_id or "unknown",
                    is_allowed,
                    "policy_evaluation",
                )

            # Check if access is denied
            if not is_allowed:
                logger.warning(
                    f"Access denied for tool '{tool_name}' by {self._get_mode_name()} enforcer"
                )
                raise McpError(
                    mt.ErrorData(
                        code=-32010,
                        message="Unauthorized",
                        data=f"Access denied by {self._get_mode_name()} policy enforcer",
                    )
                )

            # Allow the tool call to proceed
            return await call_next(context)

        except Exception as e:
            # Handle policy evaluation errors
            if isinstance(e, McpError):
                raise

            logger.error(f"Policy evaluation error: {e}")
            self.denied_requests += 1

            if self.enable_audit_logging:
                self._log_access_event(
                    context,
                    tool_name,
                    auth_context.user_id or "unknown",
                    False,
                    f"policy_error: {str(e)}",
                )

            raise McpError(
                mt.ErrorData(
                    code=-32010, message="Policy Evaluation Error", data=str(e)
                )
            )

    async def on_read_resource(
        self,
        context: MiddlewareContext[mt.ReadResourceRequestParams],
        call_next: CallNext[mt.ReadResourceRequestParams, Any],
    ) -> Any:
        """Authorize resource reading."""
        self.total_requests += 1

        # Extract resource information
        resource_uri = getattr(context.message, "uri", "unknown_resource")

        # Extract identity and create context
        auth_context = self.identity_manager.create_auth_context(context)

        # Build context for policy evaluation
        context_data = {
            "resource_name": resource_uri,
            "resource_type": "resource",
            "action": "read",
            "user_id": auth_context.user_id,
            "roles": auth_context.roles,
            "agent_id": auth_context.agent_id,
            "authenticated": auth_context.authenticated,
            "auth_method": auth_context.auth_method,
            "metadata": auth_context.metadata,
        }

        # Check authorization
        try:
            is_allowed = self.policy_enforcer.is_allowed(resource_uri, context_data)

            # Update metrics
            if is_allowed:
                self.allowed_requests += 1
            else:
                self.denied_requests += 1

            # Log decision
            if self.enable_audit_logging:
                self._log_access_event(
                    context,
                    resource_uri,
                    auth_context.user_id or "unknown",
                    is_allowed,
                    "read_resource",
                )

            # Check if access is denied
            if not is_allowed:
                logger.warning(
                    f"Access denied for resource '{resource_uri}' by {self._get_mode_name()} enforcer"
                )
                raise McpError(
                    mt.ErrorData(
                        code=-32010,
                        message="Unauthorized",
                        data=f"Access denied by {self._get_mode_name()} policy enforcer",
                    )
                )

            # Allow the resource read to proceed
            return await call_next(context)

        except Exception as e:
            # Handle policy evaluation errors
            if isinstance(e, McpError):
                raise

            logger.error(f"Policy evaluation error: {e}")
            self.denied_requests += 1

            if self.enable_audit_logging:
                self._log_access_event(
                    context,
                    resource_uri,
                    auth_context.user_id or "unknown",
                    False,
                    f"policy_error: {str(e)}",
                )

            raise McpError(
                mt.ErrorData(
                    code=-32010, message="Policy Evaluation Error", data=str(e)
                )
            )

    async def on_get_prompt(
        self,
        context: MiddlewareContext[mt.GetPromptRequestParams],
        call_next: CallNext[mt.GetPromptRequestParams, Any],
    ) -> Any:
        """Authorize prompt access."""
        self.total_requests += 1

        # Extract prompt information
        prompt_name = getattr(context.message, "name", "unknown_prompt")

        # Extract identity and create context
        auth_context = self.identity_manager.create_auth_context(context)

        # Build context for policy evaluation
        context_data = {
            "resource_name": prompt_name,
            "resource_type": "prompt",
            "action": "get",
            "user_id": auth_context.user_id,
            "roles": auth_context.roles,
            "agent_id": auth_context.agent_id,
            "authenticated": auth_context.authenticated,
            "auth_method": auth_context.auth_method,
            "metadata": auth_context.metadata,
        }

        # Check authorization
        try:
            is_allowed = self.policy_enforcer.is_allowed(prompt_name, context_data)

            # Update metrics
            if is_allowed:
                self.allowed_requests += 1
            else:
                self.denied_requests += 1

            # Log decision
            if self.enable_audit_logging:
                self._log_access_event(
                    context,
                    prompt_name,
                    auth_context.user_id or "unknown",
                    is_allowed,
                    "get_prompt",
                )

            # Check if access is denied
            if not is_allowed:
                logger.warning(
                    f"Access denied for prompt '{prompt_name}' by {self._get_mode_name()} enforcer"
                )
                raise McpError(
                    mt.ErrorData(
                        code=-32010,
                        message="Unauthorized",
                        data=f"Access denied by {self._get_mode_name()} policy enforcer",
                    )
                )

            # Allow the prompt access to proceed
            return await call_next(context)

        except Exception as e:
            # Handle policy evaluation errors
            if isinstance(e, McpError):
                raise

            logger.error(f"Policy evaluation error: {e}")
            self.denied_requests += 1

            if self.enable_audit_logging:
                self._log_access_event(
                    context,
                    prompt_name,
                    auth_context.user_id or "unknown",
                    False,
                    f"policy_error: {str(e)}",
                )

            raise McpError(
                mt.ErrorData(
                    code=-32010, message="Policy Evaluation Error", data=str(e)
                )
            )

    async def on_list_tools(
        self,
        context: MiddlewareContext[mt.ListToolsRequest],
        call_next: CallNext[mt.ListToolsRequest, List],
    ) -> List:
        """Filter tools based on authorization."""
        tools = await call_next(context)
        logger.debug(f"Received tools: {tools} and len  {len(tools)}")
        if not tools:
            return tools

        filtered_tools = []

        for tool in tools:
            tool_name = getattr(tool, "name", None) or str(tool)
            try:

                # Extract identity and create context
                auth_context = self.identity_manager.create_auth_context(context)

                # Build context for policy evaluation
                context_data = {
                    "resource_name": tool_name,
                    "resource_type": "tool",
                    "action": "list",
                    "user_id": auth_context.user_id,
                    "roles": auth_context.roles,
                    "agent_id": auth_context.agent_id,
                    "authenticated": auth_context.authenticated,
                    "auth_method": auth_context.auth_method,
                    "metadata": auth_context.metadata,
                }

                # Check authorization

                is_allowed = self.policy_enforcer.is_allowed(tool_name, context_data)
                logger.info(f"Tool {tool_name} is allowed: {is_allowed}")
                if is_allowed:
                    filtered_tools.append(tool)
                    logger.debug(
                        f"Allowed tool: {tool_name} and length: {len(filtered_tools)}"
                    )
                else:
                    if self.enable_audit_logging:
                        logger.debug(f"Filtered out tool: {tool_name}")

            except Exception as e:
                logger.error(f"Error evaluating tool {tool_name}: {e}")
                # Exclude tool on error (fail secure)
                continue
        logger.info(
            f"Filtered tools: {filtered_tools} and length: {len(filtered_tools)}"
        )

        return filtered_tools

    async def on_list_resources(
        self,
        context: MiddlewareContext[mt.ListResourcesRequest],
        call_next: CallNext[mt.ListResourcesRequest, list],
    ) -> list:
        """Filter resources based on authorization."""
        resources = await call_next(context)

        if not resources:
            return resources

        filtered_resources = []

        for resource in resources:
            resource_uri = (
                getattr(resource, "uri", None)
                or getattr(resource, "name", None)
                or str(resource)
            )
            try:

                # Extract identity and create context
                auth_context = self.identity_manager.create_auth_context(context)

                # Build context for policy evaluation
                context_data = {
                    "resource_name": resource_uri,
                    "resource_type": "resource",
                    "action": "list",
                    "user_id": auth_context.user_id,
                    "roles": auth_context.roles,
                    "agent_id": auth_context.agent_id,
                    "authenticated": auth_context.authenticated,
                    "auth_method": auth_context.auth_method,
                    "metadata": auth_context.metadata,
                }

                # Check authorization
                is_allowed = self.policy_enforcer.is_allowed(resource_uri, context_data)

                if is_allowed:
                    filtered_resources.append(resource)
                else:
                    if self.enable_audit_logging:
                        logger.debug(f"Filtered out resource: {resource_uri}")

            except Exception as e:
                logger.error(f"Error evaluating resource {resource_uri}: {e}")
                # Exclude resource on error (fail secure)
                continue

        return filtered_resources

    async def on_list_prompts(
        self,
        context: MiddlewareContext[mt.ListPromptsRequest],
        call_next: CallNext[mt.ListPromptsRequest, list],
    ) -> list:
        """Filter prompts based on authorization."""
        prompts = await call_next(context)

        if not prompts:
            return prompts

        filtered_prompts = []

        for prompt in prompts:
            prompt_name = getattr(prompt, "name", None) or str(prompt)
            try:

                # Extract identity and create context
                auth_context = self.identity_manager.create_auth_context(context)

                # Build context for policy evaluation
                context_data = {
                    "resource_name": prompt_name,
                    "resource_type": "prompt",
                    "action": "list",
                    "user_id": auth_context.user_id,
                    "roles": auth_context.roles,
                    "agent_id": auth_context.agent_id,
                    "authenticated": auth_context.authenticated,
                    "auth_method": auth_context.auth_method,
                    "metadata": auth_context.metadata,
                }

                # Check authorization
                is_allowed = self.policy_enforcer.is_allowed(prompt_name, context_data)

                if is_allowed:
                    filtered_prompts.append(prompt)

                else:
                    if self.enable_audit_logging:
                        logger.debug(f"Filtered out prompt: {prompt_name}")

            except Exception as e:
                logger.error(f"Error evaluating prompt {prompt_name}: {e}")
                # Exclude prompt on error (fail secure)
                continue

        return filtered_prompts

    def _log_access_event(
        self,
        context: MiddlewareContext[Any],
        resource_name: str,
        user_id: str,
        permitted: bool,
        reason: str = "",
    ):
        """Log access event for audit purposes."""
        # Extract additional context information
        headers = getattr(context, "headers", {}) or {}
        source = getattr(context, "source", None)

        log_data = {
            "timestamp": time.time(),
            "resource_name": resource_name,
            "user_id": user_id,
            "permitted": permitted,
            "reason": reason,
            "policy_mode": self._get_mode_name(),
            "enforcer": type(self.policy_enforcer).__name__,
            "source": source,
            "user_agent": headers.get("user-agent"),
            "ip_address": headers.get("x-forwarded-for") or headers.get("x-real-ip"),
            "request_id": headers.get("x-request-id"),
        }

        if permitted:
            logger.info(f"Access granted: {log_data}")
        else:
            logger.warning(f"Access denied: {log_data}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get middleware metrics."""
        total = self.total_requests
        allowed_rate = (self.allowed_requests / total * 100) if total > 0 else 0
        denied_rate = (self.denied_requests / total * 100) if total > 0 else 0

        return {
            "total_requests": total,
            "allowed_requests": self.allowed_requests,
            "denied_requests": self.denied_requests,
            "allowed_rate_percent": round(allowed_rate, 2),
            "denied_rate_percent": round(denied_rate, 2),
            "policy_mode": self._get_mode_name(),
            "enforcer": type(self.policy_enforcer).__name__,
            "audit_logging_enabled": self.enable_audit_logging,
        }

    def reload_policy(self):
        """Reload policy configuration."""
        try:
            if hasattr(self.policy_enforcer, "reload_policy"):
                self.policy_enforcer.reload_policy()
                logger.info(f"Reloaded policy for {self._get_mode_name()} enforcer")
            else:
                logger.warning(
                    f"Policy enforcer {type(self.policy_enforcer).__name__} does not support reloading"
                )
        except Exception as e:
            logger.error(f"Failed to reload policy: {e}")

    def get_enforcer_info(self) -> Dict[str, Any]:
        """Get information about the current policy enforcer."""
        return {
            "mode": self._get_mode_name(),
            "enforcer_type": type(self.policy_enforcer).__name__,
            "supports_reload": hasattr(self.policy_enforcer, "reload_policy"),
            "supports_async": hasattr(self.policy_enforcer, "is_allowed_async"),
        }
