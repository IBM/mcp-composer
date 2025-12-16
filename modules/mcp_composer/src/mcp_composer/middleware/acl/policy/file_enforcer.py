import json
import os
from typing import Dict, Any
from mcp_composer.middleware.acl.policy.base_policy_enforcer import BasePolicyEnforcer
from mcp_composer.middleware.acl.acl_utils import resolve_role_from_context, extract_context_info
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class FilePolicyEnforcer(BasePolicyEnforcer):
    """
    Policy enforcer that loads policies from a JSON file.

    Expected JSON format:
    {
        "admin": ["tool1", "tool2", "tool3"],
        "user": ["tool1"],
        "readonly": ["tool1"]
    }
    """

    def __init__(self, policy_file: str = "policy.json", **kwargs: Any) -> None:
        """
        Initialize the file policy enforcer.

        Args:
            policy_file: Path to the JSON policy file
            **kwargs: Additional configuration options
        """
        self.policy_file = policy_file
        self.policy_data: Dict[str, Any] = {}
        self._load_policy()

    def _load_policy(self) -> None:
        """Load policy from JSON file."""
        try:
            if not os.path.exists(self.policy_file):
                logger.warning(
                    "Policy file %s not found, using empty policy", self.policy_file
                )
                self.policy_data = {}
                return

            with open(self.policy_file, "r", encoding="utf-8") as f:
                self.policy_data = json.load(f)

            logger.info(
                "Loaded policy from %s with %d roles", self.policy_file, len(self.policy_data)
            )

        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in policy file %s: %s", self.policy_file, e)
            self.policy_data = {}
        except Exception as e:
            logger.error("Error loading policy file %s: %s", self.policy_file, e)
            self.policy_data = {}

    def is_allowed(self, tool_name: str, context: Dict[str, Any]) -> bool:
        """
        Check if the tool is allowed for the current context.

        Args:
            tool_name: Name of the tool being accessed
            context: Request context containing user and request information

        Returns:
            bool: True if access is allowed, False otherwise
        """
        role = resolve_role_from_context(context)
        context_info = extract_context_info(context)

        # Get allowed tools for the role
        allowed_tools = self.policy_data.get(role, [])

        # Check if tool is in allowed list
        is_allowed = tool_name in allowed_tools

        logger.debug(
            "File policy check - Tool: %s, Role: %s, Allowed: %s, Context: %s",
            tool_name, role, is_allowed, context_info
        )

        return is_allowed

    def reload_policy(self) -> None:
        """Reload the policy from file."""
        self._load_policy()
