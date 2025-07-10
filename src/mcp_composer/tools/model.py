"""Tools pydantic models"""

from typing import Union, Literal
from pydantic import BaseModel, model_validator


class BearerAuth(BaseModel):
    """Bearer auth model"""

    token: str


class DynamicBearerAuth(BaseModel):
    """Dynamic Bearer auth model"""

    apikey: str
    token_url: str


class BasicAuth(BaseModel):
    """Basic auth model"""

    username: str
    password: str


class APIkey(BaseModel):
    """API Key model"""

    apikey: str
    value: str


class OpenApiToolAuthConfig(BaseModel):
    """OpenAPI model"""

    auth_strategy: Literal["bearer", "dynamic_bearer", "basic", "api_key"]
    auth: Union[BearerAuth, DynamicBearerAuth, BasicAuth, APIkey]

    @model_validator(mode="before")
    @classmethod
    def validate_and_instantiate_auth(cls, values):
        """validate auth strategy"""
        strategy = values.get("auth_strategy")
        auth = values.get("auth")

        if not strategy or not auth:
            raise ValueError("Both 'auth_strategy' and 'auth' must be provided.")

        if strategy == "bearer":
            values["auth"] = BearerAuth(**auth)
        elif strategy == "dynamic_bearer":
            values["auth"] = DynamicBearerAuth(**auth)
        elif strategy == "basic":
            values["auth"] = BasicAuth(**auth)
        elif strategy == "api_key":
            values["auth"] = APIkey(**auth)
        else:
            raise ValueError(f"Unsupported auth_strategy: {strategy}")
        return values
