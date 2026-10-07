"""
Constants for the LayeredOpenAPIFactory module.
"""

# HTTP Methods
HTTP_METHODS = ["get", "post", "put", "delete", "patch"]
HTTP_METHODS_UPPER = [item.upper() for item in HTTP_METHODS]

# Default patterns and values
DEFAULT_PATTERN = ".*"
DEFAULT_MCP_TYPE = ""

# Service metadata keys
SERVICE_KEYS = {
    "NAME": "name",
    "OPERATION_ID": "operationId",
    "DESCRIPTION": "description",
    "SUMMARY": "summary",
    "HTTP_METHOD": "http_method",
    "PATH": "path",
    "PARAMETERS": "parameters",
    "REQUEST_BODY": "requestBody",
    "RESPONSES": "responses",
    "TAGS": "tags",
}

# Parameter keys
PARAMETER_KEYS = {
    "NAME": "name",
    "IN": "in",
    "REQUIRED": "required",
    "SCHEMA": "schema",
    "TYPE": "type",
    "DESCRIPTION": "description",
    "EXAMPLE": "example",
}

# Schema keys
SCHEMA_KEYS = {
    "TYPE": "type",
    "REF": "$ref",
    "CONTENT": "content",
    "APPLICATION_JSON": "application/json",
    "SCHEMA": "schema",
    "EXAMPLE": "example",
    "DESCRIPTION": "description",
}

# Request keys
REQUEST_KEYS = {
    "PATH_PARAMS": "path_params",
    "QUERY_PARAMS": "query_params",
    "HEADERS": "headers",
    "BODY": "body",
    "REQUEST_BODY": "requestBody",
}

# Response keys
RESPONSE_KEYS = {
    "SUCCESS": "success",
    "SERVICE": "service",
    "STATUS_CODE": "status_code",
    "DATA": "data",
    "ERROR": "error",
    "CONTENT": "content",
    "APPLICATION_JSON": "application/json",
    "SCHEMA": "schema",
}

# Error messages
ERROR_MESSAGES = {
    "SERVICE_NOT_FOUND": "Service '{}' not found",
    "API_CALL_FAILED": "API call failed: {}",
}

# Success messages
SUCCESS_MESSAGES = {"API_CALL_SUCCESS": "API call successful"}

# Fallback when productId / subscriptionName is missing from instance/subscription data
FALLBACK_UNKNOWN = "unknown"

# Default values
DEFAULT_VALUES = {
    "REQUIRED": False,
    "UNKNOWN_TYPE": "unknown",
    "EMPTY_STRING": "",
    "EMPTY_LIST": [],
    "EMPTY_DICT": {},
    "DEFAULT_PATTERN": ".*",
    "DEFAULT_STATUS_CODE": "200",
}

# Usage messages
USAGE_MESSAGES = {
    "GET_SERVICE_INFO": (
        "Call get_service_info(query='...') to search; "
        "get_service_info(service='operationId') for a concise summary; "
        "then get_type_info for schemas and make_tool_call to execute."
    ),
    "GET_TYPE_INFO": (
        "Call get_type_info(service='operationId') for full "
        "parameter/request/response schemas."
    ),
}

# Cap on make_tool_call response payload returned to the agent (chars of JSON/text).
MAX_TOOL_RESPONSE_CHARS = 50_000

# Shared LLM instructions for layered discovery (OA + MCP)
LAYERED_DISCOVERY_INSTRUCTIONS = """This MCP server provides layered access with three capabilities:

1. **get_service_info** - Discover available operations/tools (query-first):
   - Prefer get_service_info(query='...', limit=20) to search the catalog
   - Optional tags filter: get_service_info(query='...', tags=['tag'])
   - Call with service='name' (or tool name) for a concise summary (no full schemas)
   - With no args on a large catalog you get 'names' (every available name) plus
     'groups'/'tags' facets — names only, no summaries or schemas. Pick a name or search.
   - If a search returns no matches, 'names' is included: retry with different
     wording, or pick a name from it directly.

2. **get_type_info** - Get detailed schemas/parameters for a specific service/tool:
   - Call after you know the exact name from discovery

3. **make_tool_call** - Execute the operation/tool with arguments

Usage workflow:
1. get_service_info(query='...') to find relevant operations (never dump the full large catalog)
2. get_type_info(name) for schemas
3. make_tool_call(...) to execute"""


# OpenAPI spec keys
OPENAPI_KEYS = {
    "PATHS": "paths",
    "OPENAPI": "openapi",
    "INFO": "info",
    "COMPONENTS": "components",
    "SERVERS": "servers",
}


# Operation keys
OPERATION_KEYS = {
    "OPERATION_ID": "operationId",
    "DESCRIPTION": "description",
    "SUMMARY": "summary",
    "PARAMETERS": "parameters",
    "REQUEST_BODY": "requestBody",
    "RESPONSES": "responses",
    "TAGS": "tags",
}

# Default exclude configuration
DEFAULT_EXCLUDE_CONFIG = [
    {
        "methods": ["POST", "DELETE", "PUT", "PATCH", "GET"],
        "pattern": ".*",
        "mcp_type": "EXCLUDE",
    }
]
