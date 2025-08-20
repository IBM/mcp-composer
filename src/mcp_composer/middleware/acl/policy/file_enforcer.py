import json
import os
from typing import Dict, Any
from .base_policy_enforcer import BasePolicyEnforcer
from ..acl_utils import resolve_role_from_context, extract_context_info
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
                    f"Policy file {self.policy_file} not found, using empty policy"
                )
                self.policy_data = {}
                return

            with open(self.policy_file, "r") as f:
                self.policy_data = json.load(f)

            logger.info(
                f"Loaded policy from {self.policy_file} with {len(self.policy_data)} roles"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in policy file {self.policy_file}: {e}")
            self.policy_data = {}
        except Exception as e:
            logger.error(f"Error loading policy file {self.policy_file}: {e}")
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
            f"File policy check - Tool: {tool_name}, Role: {role}, "
            f"Allowed: {is_allowed}, Context: {context_info}"
        )

        return is_allowed

    def reload_policy(self) -> None:
        """Reload the policy from file."""
        self._load_policy()
