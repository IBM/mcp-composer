from typing import List, Literal, Optional, Union

from pydantic import BaseModel, HttpUrl, RootModel


class CustomRoute(BaseModel):
    methods: List[str]
    pattern: str
    mcp_type: Literal["TOOL", "EXCLUDE", "RESOURCE_TEMPLATE"]


class OpenAPIConfig(BaseModel):
    endpoint: HttpUrl
    spec_filepath: str
    custom_routes: List[CustomRoute]


class GraphQLConfig(BaseModel):
    endpoint: HttpUrl
    schema_filepath: str


class AuthDynamicBearer(BaseModel):
    apikey: str
    token_url: HttpUrl
    media_type: str


class AuthBearer(BaseModel):
    token: str


class ServerModel(BaseModel):
    id: str
    type: Literal["openapi", "graphql", "http", "sse"]
    open_api: Optional[OpenAPIConfig] = None
    graphql: Optional[GraphQLConfig] = None
    endpoint: Optional[HttpUrl] = None
    auth_strategy: Optional[Literal["dynamic_bearer", "bearer"]] = None
    auth: Optional[Union[AuthDynamicBearer, AuthBearer]] = None
    _id: Optional[str] = None


class ServerConfigList(RootModel[List[ServerModel]]):
    """Root model wrapping a list of server configurations."""
