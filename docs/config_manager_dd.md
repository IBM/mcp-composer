# 📘 Design Document: Versioned Configuration System

## Objective

To implement a modular and secure version-controlled configuration system for managing configuration snapshots of server endpoints (e.g., OpenAPI, GraphQL) using adapters such as file storage for development and Vault for production.

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Client
        A[Developer or Service] -->|save/get/rollback| B[ConfigManager]
    end

    B -->|Delegates| C{SecretAdapter Interface}

    C --> D1[FileSecretAdapter]
    C --> D2[VaultSecretAdapter]

    B --> E[model_config.py<br> (Typed config schema)]

    D1 -->|Read/Write JSON| F[(Local File)]
    D2 -->|Secure Read/Write| G[(Vault KV Store)]
```


## Versioned Config Manager

A secure and modular Python-based configuration management system with version control and pluggable storage backends.

Supports:
- ✅ File-based config versioning for local/dev use
- 🔐 IBM Cloud Secrets Manager for production
- 💾 Config rollback, audit, and restore
- 🔁 Pluggable adapters via `SecretAdapter` interface

---

## 📁 Project Structure

```
config-manager/
├── base_adapter.py # Abstract SecretAdapter interface
├── file_loader.py # File-based storage adapter
├── vault_loader.py # (Optional) Vault-based adapter
├── ibm_secret_loader.py # IBM Cloud Secrets Manager adapter
├── config_manager.py # Core version manager
├── model_config.py # Typed config schema (pydantic)
└── main.py # Example usage

```



## Installation

```bash
pip install ibm-secrets-manager ibm-cloud-sdk-core pydantic pydantic-settings
```


## Components
1. model_config.py
- Defines typed configuration schema using pydantic.RootModel to model various MCP server types.

- Supports OpenAPI, GraphQL, HTTP, SSE endpoints.

- Supports flexible authentication formats (bearer, dynamic bearer).

2. base_config.py
- Defines base configuration schema using pydantic.BaseModel.

- AppConfig: App-level environment config using pydantic-settings.

- SecretAdapter: Abstract base class for secret management adapters.

3. file_loader.py
- Concrete implementation of SecretAdapter that stores versioned configs in a local JSON file.

- Good for local dev/test.

- Implements: save, load, get_all_versions, rollback.

4. vault_loader.py
- Concrete implementation using HashiCorp Vault for secure storage.
- Reads/writes using hvac client.
- Good for production use.
- Path is namespaced with versioned-configs/{server_id}.

5. config_manager.py
- Handles all orchestration:
- Saves config versions.
- Fetches latest.
- Rolls back to specific version.
- Delegates persistence to injected SecretAdapter.

🔁 Flow: Save and Rollback Config
- Client loads a ServerModel and calls ConfigManager.save_version().
- ConfigManager appends version metadata (UUID, timestamp).
- Delegates to appropriate adapter (FileSecretAdapter or VaultSecretAdapter).
- Versions are capped by a history_limit.
- To rollback, ConfigManager.rollback() finds and returns the matching version.

⚙️ Environment Variables
|Variable|	Purpose	|Example|
|--------|----|----|
|USE_VAULT	|Flag |to switch between file/Vault mode	"true"|
|VAULT_ADDR	|Vault URL	|"http://localhost:8200"|
|VAULT_TOKEN|	Vault authentication token|	"s.abc123xyz"|
|VERSION_CONFIG_FILE_PATH	|Local JSON file path|	"config/versioned_config.json"|

## Advantages
- Secure version storage via Vault.
- Easy local testing with JSON file.
- Type-safe schema using pydantic.
- Supports config versioning + rollback.
- Easily extensible for AWS Secrets Manager, S3, Consul, etc.

## Environment (optional)

```
export VERSION_CONFIG_FILE_PATH="./versioned_config.json"
```

## Example 


```
from file_loader import FileSecretAdapter
from config_manager import ConfigManager

adapter = FileSecretAdapter()
manager = ConfigManager(adapter)

cfg = {"db_url": "sqlite:///test.db", "debug": True}
vid = manager.save_version("my-service", cfg)
print("Saved version:", vid)

latest = manager.get_latest_version("my-service")
print("Latest config:", latest)
```


### Required Environment Variables

```
export IBM_CLOUD_SM_APIKEY="<your-api-key>"
export IBM_CLOUD_SM_URL="https://<region>.secrets-manager.appdomain.cloud"
export IBM_CLOUD_SM_INSTANCE_ID="<your-instance-guid>"
export IBM_CLOUD_SM_SECRET_GROUP="default"
```

## Add Your Own Adapter
To add a new backend (e.g., AWS Secrets Manager, S3, DB):

Inherit from SecretAdapter in base_adapter.py

Implement 5 methods:

- load_config()

- save_config()

- get_all_versions()

- get_latest_version()

- get_version_by_id()


## Features
- Store JSON/YAML/Pydantic configs

- Versioned rollback per service

- Secure secret storage with IBM Secrets Manager

- Testable in local or production environments

- Typed configs with pydantic


## Sample Loader for IBM Cloud Secret Manager

```
import os
import json
import logging
from typing import Dict, List, Optional, Any

from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_secrets_manager_sdk.secrets_manager_v1 import *
from mcp_composer.settings.base_adapter import SecretAdapter

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class IBMCloudSecretAdapter(SecretAdapter):
    """
    Adapter for IBM Cloud Secrets Manager to store versioned configurations.
    Required ENV:
        - IBM_CLOUD_SM_APIKEY
        - IBM_CLOUD_SM_URL
        - IBM_CLOUD_SM_INSTANCE_ID
        - (optional) IBM_CLOUD_SM_SECRET_GROUP
    """

    def __init__(
        self,
        api_key: str = None,
        sm_url: str = None,
        instance_id: str = None,
        secret_group: str = "default",
        history_limit: int = 10,
    ):
        self.api_key = api_key or os.getenv("IBM_CLOUD_SM_APIKEY")
        self.sm_url = sm_url or os.getenv("IBM_CLOUD_SM_URL")
        self.instance_id = instance_id or os.getenv("IBM_CLOUD_SM_INSTANCE_ID")
        self.secret_group = secret_group or os.getenv("IBM_CLOUD_SM_SECRET_GROUP", "default")
        self.history_limit = history_limit
        self.client = self._connect()

    def _connect(self):
        authenticator = IAMAuthenticator(self.api_key)
        client = SecretsManagerV1(authenticator=authenticator)
        client.set_service_url(self.sm_url)
        logger.info("Connected to IBM Secrets Manager at %s", self.sm_url)
        return client

    def _secret_name(self, server_id: str) -> str:
        return f"versioned-config-{server_id}"

    def _get_secret_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        try:
            secrets = self.client.list_secrets(secret_group_name=self.secret_group).get_result()
            for secret in secrets.get("secrets", []):
                if secret.get("name") == name:
                    return self.client.get_secret(id=secret["id"]).get_result()
        except Exception as e:
            logger.warning("Error finding secret '%s': %s", name, e)
        return None

    def save_config(self, server_id: str, versions: List[Dict[str, Any]]) -> None:
        payload = json.dumps(versions[-self.history_limit:])
        name = self._secret_name(server_id)
        secret = self._get_secret_by_name(name)

        resource = SecretResource(payload=payload)

        if secret:
            secret_id = secret["resources"][0]["id"]
            self.client.update_secret(
                id=secret_id,
                secret_update=UpdateSecretOptions(
                    secret_type="arbitrary",
                    metadata=UpdateSecretMetadata(secret_group_id=self.secret_group, name=name),
                    resources=[UpdateSecretResource(payload=payload)],
                )
            )
            logger.info("Updated secret: %s", name)
        else:
            self.client.create_secret(
                secret_type="arbitrary",
                secret=CreateSecretOptions(
                    metadata=SecretMetadata(secret_group_id=self.secret_group, name=name),
                    resources=[resource],
                ),
                headers={"X-Sm-Instance-Id": self.instance_id}
            )
            logger.info("Created new secret: %s", name)

    def get_all_versions(self, server_id: str) -> List[Dict[str, Any]]:
        secret = self._get_secret_by_name(self._secret_name(server_id))
        if secret:
            try:
                payload = secret["resources"][0].get("payload", "[]")
                return json.loads(payload)
            except Exception as e:
                logger.warning("Error parsing payload: %s", e)
        return []

    def get_latest_version(self, server_id: str) -> Optional[Dict[str, Any]]:
        versions = self.get_all_versions(server_id)
        return versions[-1] if versions else None

    def get_version_by_id(self, server_id: str, version_id: str) -> Optional[Dict[str, Any]]:
        for version in self.get_all_versions(server_id):
            if version.get("version_id") == version_id:
                return version
        return None

    def load_config(self, server_id: str) -> Dict[str, Any]:
        latest = self.get_latest_version(server_id)
        return latest.get("config", {}) if latest else {}

```