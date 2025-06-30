from typing import Optional, Dict
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, model_validator


class ToolSettings(BaseSettings):
    name: str = Field(..., description="Name of the tool")
    tool_type: str = Field(
        ..., description="Type of tool: either from a Python script or a curl command"
    )
    description: str = Field(
        ..., description="A short description of what the tool does"
    )
    curl_config: Optional[Dict] = Field(
        default=None, description="Curl command details for tool creation"
    )
    script_config: Optional[Dict] = Field(
        default=None, description="Python function definition script for tool creation"
    )
    # auth: Optional[Dict] = Field(
    #     default=None, description="Authentication configuration if needed"
    # )
    permission: Optional[Dict[str, str]] = Field(
        default=None,
        description="Permissions required to run the tool, e.g., {'role 1': 'permission 1'}",
    )

    @model_validator(mode="after")
    def validate_config_sources(self) -> "ToolSettings":
        if not self.curl_config and not self.script_config:
            raise ValueError(
                "Either 'curl_config' or 'script_config' must be provided."
            )
        return self

    @field_validator("script_config")
    def validate_curl_config(cls, curl_config):
        if curl_config:
            for k, v in curl_config.items():
                if not k.strip() and k.strip() == "value":
                    raise ValueError(
                        "Curl config key cannot be empty or key should contain a value"
                    )
                if not v.strip():
                    raise ValueError(f"Curl config value for '{k}' cannot be empty.")
        return curl_config

    @field_validator("script_config")
    def validate_script_config(cls, script_config):
        if script_config:
            for k, v in script_config.items():
                if not k.strip() and k.strip() == "value":
                    raise ValueError(
                        "Python script config key cannot be empty or key should contain a value"
                    )
                if not v.strip():
                    raise ValueError(f"Python script value for '{k}' cannot be empty.")
        return script_config
