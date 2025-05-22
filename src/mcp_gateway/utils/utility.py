from typing import Dict, Any, List




class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class ServerConfigValidator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.server_id = config.get("id", "<unknown>")

    def validate(self) -> None:
        """Run all validation checks."""
        self._validate_auth_dependency()
        self._validate_openapi_requirements()
        self._validate_client_requirements()  

    def _validate_auth_dependency(self) -> None:
        """Ensure 'auth' exists if 'auth_strategy' is defined."""
        if "auth_strategy" in self.config and "auth" not in self.config:
            raise ValidationError(
                f"Missing 'auth' for server with id '{self.server_id}'"
            )

    def _validate_openapi_requirements(self) -> None:
        """Ensure 'endpoint' and 'openapi_url' exist if type is 'openapi'."""
        if self.config.get("type") == "openapi":
            missing = [key for key in ("endpoint", "openapi_url") if key not in self.config]
            if missing:
                raise ValidationError(
                    f"Missing required field(s) for 'openapi' type in server '{self.server_id}': {', '.join(missing)}"
                )

    def _validate_client_requirements(self) -> None:
        if self.config.get("type") == "client" and "endpoint" not in self.config:
            raise ValidationError(
                f"Missing 'endpoint' for 'client' type in server '{self.server_id}'"
            )

class AllServersValidator:
    def __init__(self, server: List[Dict[str, Any]]):
        self.server = server

    def validate_all(self) -> None:
        for config in self.server:
            validator = ServerConfigValidator(config)
            validator.validate()