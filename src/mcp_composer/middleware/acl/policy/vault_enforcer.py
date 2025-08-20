import os
import hvac
import json
from typing import Dict, Any, Optional, List
from mcp_composer.middleware.acl.policy.base_policy_enforcer import BasePolicyEnforcer
from mcp_composer.middleware.acl.acl_utils import (
    resolve_role_from_context,
    extract_context_info,
)
from mcp_composer.core.utils.logger import LoggerFactory

logger = LoggerFactory.get_logger()


class HashiCorpVaultPolicyEnforcer(BasePolicyEnforcer):
    """
    Policy enforcer that checks policies stored in HashiCorp Vault KV v2.

    Expected Vault KV structure:
    secret/data/mcp-policies/
    ├── admin.json
    ├── user.json
    └── readonly.json

    Each policy file contains:
    {
        "allowed_tools": ["tool1", "tool2", "tool3"],
        "conditions": {
            "time_restrictions": ["9:00-17:00"],
            "project_restrictions": ["project1", "project2"]
        }
    }
    """

    def __init__(
        self,
        vault_url: str = os.getenv("VAULT_URL", "http://localhost:8200"),
        token: Optional[str] = os.getenv("VAULT_TOKEN", "root"),
        mount_point: str = os.getenv("VAULT_MOUNT_POINT", "secret"),
        policy_path: str = os.getenv("VAULT_POLICY_PATH", "mcp-policies"),
        **kwargs: Any,
    ):
        """
        Initialize the Vault policy enforcer.

        Args:
            vault_url: URL of the Vault server
            token: Vault authentication token
            mount_point: KV secrets engine mount point
            policy_path: Path within the KV store where policies are stored
            **kwargs: Additional configuration options
        """
        self.vault_url = vault_url
        self.token = token or kwargs.get("token")
        self.mount_point = mount_point
        self.policy_path = policy_path
        self.client = None
        self._initialize_client()

        logger.info(
            f"Initialized Vault policy enforcer - URL: {vault_url}, Path: {mount_point}/{policy_path}"
        )

    def _initialize_client(self) -> None:
        """Initialize the Vault client."""
        try:

            self.client = hvac.Client(url=self.vault_url, token=self.token)

            # Test the connection
            if self.client and not self.client.is_authenticated():
                logger.warning(
                    f"Vault client is not authenticated. URL: {self.vault_url}, Token: {'***' if self.token else 'None'}"
                )
                return

            logger.info(f"Successfully connected to Vault at {self.vault_url}")

        except ImportError:
            logger.error("hvac library not installed. Install with: pip install hvac")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Vault client: {e}")
            self.client = None

    def _get_policy_from_vault(self, role: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve policy for a specific role from Vault.

        Args:
            role: User role

        Returns:
            Policy dictionary or None if not found
        """
        if not self.client or not self.client.is_authenticated():
            logger.warning("Vault client not available or not authenticated")
            return None

        try:
            # Read policy from KV v2
            secret_path = f"{self.policy_path}/{role}"
            logger.debug(
                f"Retrieving policy for role {role} from Vault from path {secret_path}"
            )
            response = self.client.secrets.kv.v2.read_secret_version(
                path=secret_path, mount_point=self.mount_point
            )

            logger.debug(
                f"Response from Vault: {json.dumps(response, indent=4)} - {response}"
            )
            if response and "data" in response and "data" in response["data"]:
                policy_data = response["data"]["data"]
                logger.debug(
                    f"Retrieved policy for role {role} from Vault as {policy_data}"
                )
                return policy_data
            else:
                logger.warning(f"No policy data found for role {role} in Vault")
                return None

        except Exception as e:
            if "InvalidPath" in str(e):
                logger.debug(f"No policy found for role {role} in Vault")
            else:
                logger.error(f"Error retrieving policy for role {role} from Vault: {e}")
            return None

    def _evaluate_conditions(
        self, policy: Dict[str, Any], context_info: Dict[str, Any]
    ) -> bool:
        """
        Evaluate policy conditions against context.

        Args:
            policy: Policy dictionary containing conditions
            context_info: Extracted context information

        Returns:
            bool: True if conditions are met, False otherwise
        """
        conditions = policy.get("conditions", {})

        # Check time restrictions
        time_restrictions = conditions.get("time_restrictions", [])
        if time_restrictions:
            # Simple time check - in production, you'd want more sophisticated time parsing
            import datetime

            current_time = datetime.datetime.now().time()
            current_hour = current_time.hour

            time_allowed = False
            for restriction in time_restrictions:
                if "-" in restriction:
                    start_str, end_str = restriction.split("-")
                    try:
                        start_hour = int(start_str.split(":")[0])
                        end_hour = int(end_str.split(":")[0])
                        if start_hour <= current_hour <= end_hour:
                            time_allowed = True
                            break
                    except (ValueError, IndexError):
                        logger.warning(
                            f"Invalid time restriction format: {restriction}"
                        )

            if not time_allowed:
                logger.debug(f"Time restriction not met: {time_restrictions}")
                return False

        # Check project restrictions
        project_restrictions = conditions.get("project_restrictions", [])
        if project_restrictions and context_info.get("project"):
            if context_info["project"] not in project_restrictions:
                logger.debug(
                    f"Project restriction not met: {context_info['project']} not in {project_restrictions}"
                )
                return False

        # Check agent type restrictions
        agent_restrictions = conditions.get("agent_restrictions", [])
        if agent_restrictions and context_info.get("agent_type"):
            if context_info["agent_type"] not in agent_restrictions:
                logger.debug(
                    f"Agent type restriction not met: {context_info['agent_type']} not in {agent_restrictions}"
                )
                return False

        return True

    def is_allowed(self, tool_name: str, context: Dict[str, Any]) -> bool:
        """
        Check if the tool is allowed based on Vault policy.

        Args:
            tool_name: Name of the tool being accessed
            context: Request context containing user and request information

        Returns:
            bool: True if access is allowed, False otherwise
        """
        # Check if client is available and authenticated

        logger.debug(f"Checking Vault policy for tool: {tool_name}, Context: {context}")
        if not self.client or not self.client.is_authenticated():
            logger.warning(
                "Vault client not available or not authenticated, denying access"
            )
            return False

        role = resolve_role_from_context(context)
        context_info = extract_context_info(context)

        # Get policy from Vault
        policy = self._get_policy_from_vault(role)
        logger.debug(f"Retrieved policy for role {role} from Vault: {policy}")
        if not policy:
            logger.warning(f"No policy found for role {role} in Vault")
            return False

        # Check if tool is in allowed list
        allowed_tools = policy.get("tools", [])
        logger.debug(f"Allowed tools for role {role}: {allowed_tools}")
        if tool_name not in allowed_tools:
            logger.debug(f"Tool {tool_name} not in allowed tools for role {role}")
            return False

        # Evaluate conditions
        if not self._evaluate_conditions(policy, context_info):
            logger.debug(f"Policy conditions not met for role {role}")
            return False

        logger.debug(
            f"Vault policy check - Tool: {tool_name}, Role: {role}, "
            f"Allowed: True, Context: {context_info}"
        )

        return True

    def update_policy(self, role: str, policy_data: Dict[str, Any]) -> bool:
        """
        Update policy for a role in Vault.

        Args:
            role: User role
            policy_data: New policy data

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.client or not self.client.is_authenticated():
            logger.error("Vault client not available or not authenticated")
            return False

        try:
            secret_path = f"{self.policy_path}/{role}"
            self.client.secrets.kv.v2.create_or_update_secret(
                path=secret_path, secret=policy_data, mount_point=self.mount_point
            )

            logger.info(f"Successfully updated policy for role {role} in Vault")
            return True

        except Exception as e:
            logger.error(f"Error updating policy for role {role} in Vault: {e}")
            return False

    def list_policies(self) -> List[str]:
        """
        List all available policies in Vault.

        Returns:
            list: List of policy names
        """
        if not self.client or not self.client.is_authenticated():
            logger.error("Vault client not available or not authenticated")
            return []

        try:
            response = self.client.secrets.kv.v2.list_secrets(
                path=self.policy_path, mount_point=self.mount_point
            )

            if response and "data" in response and "keys" in response["data"]:
                return response["data"]["keys"]
            else:
                return []

        except Exception as e:
            logger.error(f"Error listing policies in Vault: {e}")
            return []

    def get_connection_status(self) -> Dict[str, Any]:
        """
        Get the current connection status of the Vault client.

        Returns:
            dict: Connection status information
        """
        authenticated = False
        if self.client is not None:
            authenticated = self.client.is_authenticated()

        return {
            "client_available": self.client is not None,
            "authenticated": authenticated,
            "vault_url": self.vault_url,
            "mount_point": self.mount_point,
            "policy_path": self.policy_path,
            "token_provided": bool(self.token),
        }

    def reconnect(self) -> bool:
        """
        Attempt to reconnect to Vault.

        Returns:
            bool: True if reconnection successful, False otherwise
        """
        logger.info("Attempting to reconnect to Vault...")
        self._initialize_client()
        if self.client is None:
            return False
        return self.client.is_authenticated()
