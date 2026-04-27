"""Tools pydantic models"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from mcp_composer.core.models.oauth import (
    APIkey,
    BasicAuth,
    BearerAuth,
    DynamicBearerAuth,
)


class ToolBuilderConfig(BaseModel):
    """Tool builder config for tool creation using curl command or Python script"""

    name: str = Field(..., description="Name of the tool")
    tool_type: str = Field(
        ..., description="Type of tool: either from a Python script or a curl command"
    )
    description: str = Field(
        ..., description="A short description of what the tool does"
    )
    curl_config: dict[str, object] | None = Field(
        default=None, description="Curl command details for tool creation"
    )
    script_config: dict[str, object] | None = Field(
        default=None, description="Python function definition script for tool creation"
    )
    # auth: Dict | None = Field(
    #     default=None, description="Authentication configuration if needed"
    # )
    permission: dict[str, str] | None = Field(
        default=None,
        description="Permissions required to run the tool, e.g., {'role 1': 'permission 1'}",
    )

    @model_validator(mode="after")
    def validate_config_sources(self) -> "ToolBuilderConfig":
        """Validate config value is present or not"""
        if not self.curl_config and not self.script_config:
            raise ValueError(
                "Either 'curl_config' or 'script_config' must be provided."
            )
        return self

    @field_validator("curl_config")
    def validate_curl_config(
        cls, curl_config: dict[str, object] | None
    ) -> dict[str, object] | None:  # pylint: disable=E0213
        """validate curl config is not empty"""
        if curl_config:
            for k, v in curl_config.items():
                if not k.strip():
                    raise ValueError(
                        "Curl config key cannot be empty or key should contain a value"
                    )
                # Handle nested dictionaries and other non-string values
                if isinstance(v, str) and not v.strip():
                    raise ValueError(f"Curl config value for '{k}' cannot be empty.")
        return curl_config

    @field_validator("script_config")
    def validate_script_config(
        cls, script_config: dict[str, object] | None
    ) -> dict[str, object] | None:  # pylint: disable=E0213
        """validate python script config is not empty"""
        if script_config:
            for k, v in script_config.items():
                if not k.strip():
                    raise ValueError(
                        "Python script config key cannot be empty or key should contain a value"
                    )
                # Handle nested dictionaries and other non-string values
                if isinstance(v, str) and not v.strip():
                    raise ValueError(f"Python script value for '{k}' cannot be empty.")
        return script_config


class OpenApiToolAuthConfig(BaseModel):
    """OpenAPI tool auth config model"""

    auth_strategy: Literal["bearer", "dynamic_bearer", "basic", "api_key"]
    auth: BearerAuth | DynamicBearerAuth | BasicAuth | APIkey

    @model_validator(mode="before")
    @classmethod
    def validate_and_instantiate_auth(
        cls, values: dict[str, object]
    ) -> dict[str, object]:
        """validate auth strategy"""
        strategy = values.get("auth_strategy")
        auth = values.get("auth")

        if not strategy or not auth:
            raise ValueError("Both 'auth_strategy' and 'auth' must be provided.")

        if strategy == "bearer":
            values["auth"] = BearerAuth(**auth)  # type: ignore[arg-type]
        elif strategy == "dynamic_bearer":
            values["auth"] = DynamicBearerAuth(**auth)  # type: ignore[arg-type]
        elif strategy == "basic":
            values["auth"] = BasicAuth(**auth)  # type: ignore[arg-type]
        elif strategy == "api_key":
            values["auth"] = APIkey(**auth)  # type: ignore[arg-type]
        else:
            raise ValueError(f"Unsupported auth_strategy: {strategy}")
        return values
