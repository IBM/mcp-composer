from mcp_composer.core.settings.file_loader import FileSecretAdapter
from mcp_composer.core.settings.ibm_secret_loader import IBMCloudSecretAdapter

# from mcp_composer.settings.postgres_loader import PostgresSecretAdapter  # Example future one

ADAPTER_REGISTRY = {
    "file": FileSecretAdapter,
    "ibm_vault": IBMCloudSecretAdapter,
    # "postgres": PostgresSecretAdapter,
}
