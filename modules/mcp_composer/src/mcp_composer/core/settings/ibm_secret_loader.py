# Not working currently
import json
import logging
import os
from typing import Any, TYPE_CHECKING

# Lazy import for optional IBM Cloud dependencies
try:
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator  # type: ignore[import-untyped]
    from ibm_secrets_manager_sdk.secrets_manager_v2 import SecretsManagerV2  # type: ignore[import-untyped]
    _IBM_SECRETS_AVAILABLE = True
except ImportError:
    _IBM_SECRETS_AVAILABLE = False
    if not TYPE_CHECKING:
        IAMAuthenticator = None  # type: ignore
        SecretsManagerV2 = None  # type: ignore

from mcp_composer.core.settings.base_adapter import SecretAdapter

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class IBMCloudSecretAdapter(SecretAdapter):
    """
    Adapter for IBM Cloud Secrets Manager v2 to store versioned configurations.
    Required ENV variables:
        - IBM_CLOUD_SM_APIKEY
        - IBM_CLOUD_SM_URL
        - (optional) IBM_CLOUD_SM_SECRET_GROUP
    """

    def __init__(
        self,
        api_key: str | None = None,
        sm_url: str | None = None,
        secret_group: str = "default",
        history_limit: int = 10,
    ):
        if not _IBM_SECRETS_AVAILABLE:
            raise ImportError(
                "IBM Secrets Manager support requires 'ibm-cloud' extras. "
                "Install with: pip install mcp-composer[ibm-cloud]"
            )
        self.api_key = api_key or os.getenv("IBM_CLOUD_SM_APIKEY")
        self.sm_url = sm_url or os.getenv("IBM_CLOUD_SM_URL")
        self.secret_group = secret_group or os.getenv(
            "IBM_CLOUD_SM_SECRET_GROUP", "default"
        )
        self.history_limit = history_limit

        if not self.api_key or not self.sm_url:
            raise ValueError("IBM_CLOUD_SM_APIKEY and IBM_CLOUD_SM_URL must be set")
        self.client = self._connect()

    def _connect(self) -> Any:
        authenticator = IAMAuthenticator(str(self.api_key))
        client = SecretsManagerV2(authenticator=authenticator)
        client.set_service_url(str(self.sm_url))
        logger.info("Connected to IBM Secrets Manager v2 at %s", self.sm_url)
        return client

    def _secret_name(self, server_id: str) -> str:
        return f"versioned-config-{server_id}"

    def _get_secret_by_name(self, name: str) -> dict[str, Any] | None:
        try:
            secret = self.client.get_secret_by_name_type(
                secret_type="kv", name=name, secret_group_name=self.secret_group
            )
            secret.get_result()
            return secret
            # secrets = self.client.list_secrets(groups=["default"]).get_result()
            # for secret in secrets.get("secrets", []):
            #     if secret.get("name") == name:
        except (OSError, ValueError, KeyError) as e:
            logger.warning("Error finding secret '%s': %s", name, e)
        return None

    def save_config(self, server_id: str, versions: list[dict[str, Any]]) -> None:
        payload = json.dumps(versions[-self.history_limit :])
        name = self._secret_name(server_id)
        secret = self._get_secret_by_name(name)

        secret_prototype = {
            "secret_type": "arbitrary",
            "name": name,
            "secret_group_id": self.secret_group,
            "resources": [{"payload": payload}],
        }

        if secret:
            secret_id = secret["id"]
            self.client.update_secret(id=secret_id, secret_prototype=secret_prototype)  # type: ignore
            logger.info("Updated secret: %s", name)
        else:
            self.client.create_secret(secret_prototype=secret_prototype)
            logger.info("Created new secret: %s", name)

    def get_all_versions(self, server_id: str) -> list[dict[str, Any]]:
        secret = self._get_secret_by_name(self._secret_name(server_id))
        logger.info("fetched the secret by name: %s", secret)
        if secret:
            try:
                secret_id = secret["id"]
                secret_details = self.client.get_secret(id=secret_id).get_result()
                payload = secret_details["resources"][0].get("payload", "[]")
                return json.loads(payload)
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.warning(
                    "Error parsing payload for server_id %s: %s", server_id, e
                )
        return []

    def get_latest_version(self, server_id: str) -> dict[str, Any] | None:
        versions = self.get_all_versions(server_id)
        return versions[-1] if versions else None

    def get_version_by_id(
        self, server_id: str, version_id: str
    ) -> dict[str, Any] | None:
        for version in self.get_all_versions(server_id):
            if version.get("version_id") == version_id:
                return version
        return None

    def load_config(self, server_id: str) -> dict[str, Any]:
        latest = self.get_latest_version(server_id)
        return latest.get("config", {}) if latest else {}

    def rollback(self, server_id: str, version_id: str) -> dict[str, Any]:
        version = self.get_version_by_id(server_id, version_id)
        if version:
            return version["config"]
        raise ValueError(
            f"Version ID '{version_id}' not found for server '{server_id}'"
        )
