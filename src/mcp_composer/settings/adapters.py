from mcp_composer.settings.file_loader import FileSecretAdapter
from mcp_composer.settings.ibm_secret_loader import IBMCloudSecretAdapter
# from mcp_composer.settings.postgres_loader import PostgresSecretAdapter  # Example future one

ADAPTER_REGISTRY = {
    "file": lambda **kwargs: FileSecretAdapter(**kwargs),
    "ibm_vault": lambda **kwargs: IBMCloudSecretAdapter(**kwargs),
    # "postgres": lambda: PostgresSecretAdapter(),
}