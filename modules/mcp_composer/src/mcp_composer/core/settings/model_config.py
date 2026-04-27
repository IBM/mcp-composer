from typing import Literal

from pydantic import BaseModel, HttpUrl, RootModel


class CustomRoute(BaseModel):
    methods: list[str]
    pattern: str
    mcp_type: Literal["TOOL", "EXCLUDE", "RESOURCE_TEMPLATE"]


class OpenAPIConfig(BaseModel):
    endpoint: HttpUrl
    spec_filepath: str
    custom_routes: list[CustomRoute]


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
    open_api: OpenAPIConfig | None = None
    graphql: GraphQLConfig | None = None
    endpoint: HttpUrl | None = None
    auth_strategy: Literal["dynamic_bearer", "bearer"] | None = None
    auth: AuthDynamicBearer | AuthBearer | None = None
    _id: str | None = None


class ServerConfigList(RootModel[list[ServerModel]]):
    """Root model wrapping a list of server configurations."""
