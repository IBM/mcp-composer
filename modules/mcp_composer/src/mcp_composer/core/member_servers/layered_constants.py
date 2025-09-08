"""
Constants for the LayeredOpenAPIFactory module.
"""

# HTTP Methods
HTTP_METHODS = ['get', 'post', 'put', 'delete', 'patch']
HTTP_METHODS_UPPER = [item.upper() for item in HTTP_METHODS]

# Default patterns and values
DEFAULT_PATTERN = ".*"
DEFAULT_MCP_TYPE = ""

# Service metadata keys
SERVICE_KEYS = {
    'NAME': 'name',
    'OPERATION_ID': 'operationId',
    'DESCRIPTION': 'description',
    'SUMMARY': 'summary',
    'HTTP_METHOD': 'http_method',
    'PATH': 'path',
    'PARAMETERS': 'parameters',
    'REQUEST_BODY': 'requestBody',
    'RESPONSES': 'responses',
    'TAGS': 'tags'
}

# Parameter keys
PARAMETER_KEYS = {
    'NAME': 'name',
    'IN': 'in',
    'REQUIRED': 'required',
    'SCHEMA': 'schema',
    'TYPE': 'type',
    'DESCRIPTION': 'description',
    'EXAMPLE': 'example'
}

# Schema keys
SCHEMA_KEYS = {
    'TYPE': 'type',
    'REF': '$ref',
    'CONTENT': 'content',
    'APPLICATION_JSON': 'application/json',
    'SCHEMA': 'schema',
    'EXAMPLE': 'example',
    'DESCRIPTION': 'description'
}

# Request keys
REQUEST_KEYS = {
    'PATH_PARAMS': 'path_params',
    'QUERY_PARAMS': 'query_params',
    'HEADERS': 'headers',
    'BODY': 'body',
    'REQUEST_BODY': 'requestBody'
}

# Response keys
RESPONSE_KEYS = {
    'SUCCESS': 'success',
    'SERVICE': 'service',
    'STATUS_CODE': 'status_code',
    'DATA': 'data',
    'ERROR': 'error',
    'CONTENT': 'content',
    'APPLICATION_JSON': 'application/json',
    'SCHEMA': 'schema'
}

# Error messages
ERROR_MESSAGES = {
    'SERVICE_NOT_FOUND': "Service '{}' not found",
    'API_CALL_FAILED': "API call failed: {}"
}

# Success messages
SUCCESS_MESSAGES = {
    'API_CALL_SUCCESS': "API call successful"
}

# Default values
DEFAULT_VALUES = {
    'REQUIRED': False,
    'UNKNOWN_TYPE': 'unknown',
    'EMPTY_STRING': '',
    'EMPTY_LIST': [],
    'EMPTY_DICT': {},
    'DEFAULT_PATTERN': '.*',
    'DEFAULT_STATUS_CODE': '200'
}

# Usage messages
USAGE_MESSAGES = {
    'GET_SERVICE_INFO': "Call get_service_info(service='operationId') for detailed info"
}



# OpenAPI spec keys
OPENAPI_KEYS = {
    'PATHS': 'paths',
    'OPENAPI': 'openapi',
    'INFO': 'info',
    'COMPONENTS': 'components',
    'SERVERS': 'servers'
}


# Operation keys
OPERATION_KEYS = {
    'OPERATION_ID': 'operationId',
    'DESCRIPTION': 'description',
    'SUMMARY': 'summary',
    'PARAMETERS': 'parameters',
    'REQUEST_BODY': 'requestBody',
    'RESPONSES': 'responses',
    'TAGS': 'tags'
}

# Default exclude configuration
DEFAULT_EXCLUDE_CONFIG = [
    {
        "methods": [
            "POST",
            "DELETE",
            "PUT",
            "PATCH",
            "GET"
        ],
        "pattern": ".*",
        "mcp_type": "EXCLUDE"
    }
]
