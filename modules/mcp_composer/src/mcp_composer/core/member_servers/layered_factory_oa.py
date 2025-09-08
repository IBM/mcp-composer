import re
from typing import Dict, List, Any, Optional, Union
import httpx
import asyncio
from fastmcp import FastMCP
from fastmcp.tools.tool import Tool
from fastmcp.server.openapi import MCPType, RouteMap
from fastmcp.utilities.openapi import (
    parse_openapi_to_http_routes,
    generate_example_from_schema,
    clean_schema_for_display,
    extract_output_schema_from_responses,
)

from mcp_composer.core.utils import load_custom_mappings_from_json
from mcp_composer.core.member_servers.layered_constants import (
    HTTP_METHODS,
    HTTP_METHODS_UPPER,
    DEFAULT_PATTERN,
    DEFAULT_MCP_TYPE,
    SERVICE_KEYS,
    PARAMETER_KEYS,
    SCHEMA_KEYS,
    REQUEST_KEYS,
    RESPONSE_KEYS,
    ERROR_MESSAGES,
    USAGE_MESSAGES,
    OPENAPI_KEYS,
    OPERATION_KEYS,
    DEFAULT_EXCLUDE_CONFIG,
    DEFAULT_VALUES
)

class LayeredOpenAPIFactory(FastMCP):

    def __init__(self, openapi_spec: dict[str, Any],
                client: httpx.AsyncClient, custom_routes: list[RouteMap]  | None = None,
                custom_routes_exclude_all:list[RouteMap]  | None = None):
        # Initialize the parent FastMCP class first
        super().__init__(
            name="Layered OpenAPI FastMCP",
            instructions="""This MCP server provides access to OpenAPI-based tools with three main capabilities:

1. **get_service_info** - Discover and list all available API operations/tools:
   - Call without parameters to see all available services
   - Call with a specific service name to get detailed information including schema summaries
   - Use this to understand what API operations are available

2. **get_type_info** - Get detailed parameter, input, and output information for a specific service:
   - Call with a service name (operationId) to get comprehensive details
   - Returns parameter schemas, request body schemas, response schemas, and examples
   - Use this to understand how to call a specific API operation

3. **make_tool_call** - Execute an actual API call to the specified service:
   - Call with a service name and optional request parameters
   - This is the tool that actually performs the HTTP request to the underlying API
   - Use this after understanding the service details from the other tools

Usage workflow:
1. First use get_service_info() to see what's available
2. Then use get_type_info(service_name) to understand the specific service
3. Finally use make_tool_call(service_name, request_data) to execute the API call

All tools automatically resolve OpenAPI schema references and provide enhanced metadata including examples and cleaned schemas."""
        )

        self.openapi_spec = openapi_spec
        self.client = client
        self.custom_routes = custom_routes or []
        self.service_info = self._build_service_metadata()

        # Create the underlying FastMCP server with custom routes
        #self._mcp_server = FastMCP.from_openapi(self.openapi_spec,
        #client=self.client, route_maps= custom_routes_exclude_all)

        # Add our custom tools
        self.add_tool(Tool.from_function(self.get_service_info))
        self.add_tool(Tool.from_function(self.get_type_info))
        self.add_tool(Tool.from_function(self.make_tool_call))

    def _resolve_schema_reference(self, ref: str) -> Dict[str, Any]:
        """
        Resolve a schema reference to its actual definition.
        
        Args:
            ref: The reference string (e.g., "#/components/schemas/GetApplications")
            
        Returns:
            Dict containing the resolved schema definition
        """
        if not ref or not ref.startswith('#/'):
            return {}
        
        # Remove the leading '#/' and split by '/'
        parts = ref[2:].split('/')
        
        # Navigate through the OpenAPI spec to find the referenced schema
        current = self.openapi_spec
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return {}
        
        return current if isinstance(current, dict) else {}

    def _extract_parameter_schemas(self, parameters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract and enhance parameter information including schema details.
        
        Args:
            parameters: List of parameters from the OpenAPI spec
            
        Returns:
            List of enhanced parameter information
        """
        if not parameters:
            return []
        
        enhanced_params = []
        for param in parameters:
            if isinstance(param, dict):
                schema = param.get(PARAMETER_KEYS['SCHEMA'], {})
                original_ref = None
                
                # Handle schema references
                if schema and SCHEMA_KEYS['REF'] in schema:
                    original_ref = schema[SCHEMA_KEYS['REF']]
                    resolved_schema = self._resolve_schema_reference(original_ref)
                    if resolved_schema:
                        schema = resolved_schema
                
                # Clean the schema for display
                cleaned_schema = clean_schema_for_display(schema) if schema else {}
                
                enhanced_param = {
                    PARAMETER_KEYS['NAME']: param.get(PARAMETER_KEYS['NAME']),
                    PARAMETER_KEYS['IN']: param.get(PARAMETER_KEYS['IN']),
                    PARAMETER_KEYS['REQUIRED']: param.get(PARAMETER_KEYS['REQUIRED'], DEFAULT_VALUES['REQUIRED']),
                    PARAMETER_KEYS['TYPE']: schema.get(SCHEMA_KEYS['TYPE'], DEFAULT_VALUES['UNKNOWN_TYPE']) if schema else DEFAULT_VALUES['UNKNOWN_TYPE'],
                    PARAMETER_KEYS['DESCRIPTION']: param.get(PARAMETER_KEYS['DESCRIPTION'], DEFAULT_VALUES['EMPTY_STRING']),
                    PARAMETER_KEYS['EXAMPLE']: param.get(PARAMETER_KEYS['EXAMPLE']),
                    'schema': cleaned_schema,
                    'original_ref': original_ref
                }
                
                enhanced_params.append(enhanced_param)
        
        return enhanced_params

    def _extract_request_body_schema(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and clean schema from request body using fastmcp utilities.
        
        Args:
            request_body: The request body object from the OpenAPI spec
            
        Returns:
            Dict containing the cleaned schema and example
        """
        if not request_body:
            return {}
        
        # Extract schema from content.application/json.schema
        content = request_body.get(SCHEMA_KEYS['CONTENT'], {})
        json_content = content.get(SCHEMA_KEYS['APPLICATION_JSON'], {})
        schema = json_content.get(SCHEMA_KEYS['SCHEMA'], {})
        original_ref = None
        
        if schema:
            # Handle schema references
            if SCHEMA_KEYS['REF'] in schema:
                original_ref = schema[SCHEMA_KEYS['REF']]
                resolved_schema = self._resolve_schema_reference(original_ref)
                if resolved_schema:
                    schema = resolved_schema
            
            # Clean the schema for display
            cleaned_schema = clean_schema_for_display(schema)
            if cleaned_schema:
                # Generate example if possible
                try:
                    example = generate_example_from_schema(schema)
                    if example:
                        cleaned_schema[SCHEMA_KEYS['EXAMPLE']] = example
                except Exception:
                    # Example generation is optional, continue without it
                    pass
                
                # Add original schema reference if it exists
                if original_ref:
                    cleaned_schema['original_ref'] = original_ref
                
                return cleaned_schema
        
        return {}

    def _extract_response_schemas(self, responses: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and clean schemas from responses using fastmcp utilities.
        
        Args:
            responses: The responses object from the OpenAPI spec
            
        Returns:
            Dict containing the cleaned response schemas
        """
        if not responses:
            return {}
        
        # Use the existing fastmcp utility to extract output schema
        try:
            output_schema = extract_output_schema_from_responses(responses)
            
            # Clean the schema for display
            if output_schema:
                cleaned_schema = clean_schema_for_display(output_schema)
                if cleaned_schema:
                    return cleaned_schema
        except Exception:
            # If schema extraction fails, fall back to basic response info
            pass
        
        # Fallback: extract basic response information with schema resolution
        cleaned_responses = {}
        for status_code, response in responses.items():
            if isinstance(response, dict):
                content = response.get(SCHEMA_KEYS['CONTENT'], {})
                json_content = content.get(SCHEMA_KEYS['APPLICATION_JSON'], {})
                schema = json_content.get(SCHEMA_KEYS['SCHEMA'], {})
                original_ref = None
                
                # Handle schema references
                if schema and SCHEMA_KEYS['REF'] in schema:
                    original_ref = schema[SCHEMA_KEYS['REF']]
                    resolved_schema = self._resolve_schema_reference(original_ref)
                    if resolved_schema:
                        schema = resolved_schema
                
                cleaned_responses[status_code] = {
                    'description': response.get('description', ''),
                    'schema': clean_schema_for_display(schema) if schema else {},
                    'original_ref': original_ref
                }
        
        return cleaned_responses

    def _build_service_metadata(self) -> Dict[str, Dict]:
        """
        Build service metadata from operations by parsing OpenAPI spec and applying custom routes filtering.
        Only operations that match the custom routes (TOOL) are included in service_info.
        """
        services = {}

        # Parse the OpenAPI spec paths and apply custom routes filtering
        if OPENAPI_KEYS['PATHS'] in self.openapi_spec:
            for path, path_item in self.openapi_spec[OPENAPI_KEYS['PATHS']].items():
                for http_method, operation in path_item.items():
                    if http_method.lower() in HTTP_METHODS:
                        # Check if this operation should be included based on custom routes
                        if self._should_include_operation(http_method.upper(), path):
                            operation_id = operation.get(OPERATION_KEYS['OPERATION_ID'])
                            if operation_id:
                                services[operation_id] = {
                                    SERVICE_KEYS['NAME']: operation_id,
                                    SERVICE_KEYS['OPERATION_ID']: operation_id,
                                    SERVICE_KEYS['DESCRIPTION']: operation.get(OPERATION_KEYS['DESCRIPTION'], operation.get(OPERATION_KEYS['SUMMARY'], f"API operation: {operation_id}")),
                                    SERVICE_KEYS['SUMMARY']: operation.get(OPERATION_KEYS['SUMMARY'], DEFAULT_VALUES['EMPTY_STRING']),
                                    SERVICE_KEYS['HTTP_METHOD']: http_method.upper(),
                                    SERVICE_KEYS['PATH']: path,
                                    SERVICE_KEYS['PARAMETERS']: self._extract_parameter_schemas(operation.get(OPERATION_KEYS['PARAMETERS'], DEFAULT_VALUES['EMPTY_LIST'])),
                                    SERVICE_KEYS['REQUEST_BODY']: self._extract_request_body_schema(operation.get(OPERATION_KEYS['REQUEST_BODY'])),
                                    SERVICE_KEYS['RESPONSES']: self._extract_response_schemas(operation.get(OPERATION_KEYS['RESPONSES'], DEFAULT_VALUES['EMPTY_DICT'])),
                                    SERVICE_KEYS['TAGS']: operation.get(OPERATION_KEYS['TAGS'], DEFAULT_VALUES['EMPTY_LIST'])
                                }
        return services

    def _should_include_operation(self, http_method: str, path: str) -> bool:
        """
        Determine if an operation should be included based on custom routes.
        If no custom routes are provided, include all operations.
        If custom routes are provided, only include operations that are explicitly marked as TOOL/RESOURCE.
        Operations marked as EXCLUDE are always excluded.
        """
        if not self.custom_routes:
            # Default behavior: include all operations if no custom routes specified
            return True

        # Track if this operation has been explicitly handled by any rule
        operation_handled = False
        should_include = False

        # Apply custom routes filtering based on user configuration
        for route_rule in self.custom_routes:
            # RouteMap objects have attributes, not dict-like access
            methods = getattr(route_rule, 'methods', DEFAULT_VALUES['EMPTY_LIST'])
            pattern = getattr(route_rule, 'pattern', DEFAULT_PATTERN)
            mcp_type = getattr(route_rule, 'mcp_type', DEFAULT_MCP_TYPE)

            # Check if this operation matches the route rule
            if http_method in methods and self._matches_pattern(path, pattern):
                operation_handled = True
                
                if mcp_type == MCPType.TOOL or mcp_type == MCPType.RESOURCE:
                    should_include = True
                elif mcp_type == MCPType.EXCLUDE:
                    # EXCLUDE rules take precedence - always exclude
                    return False

        # If operation was handled by custom routes, return the decision
        if operation_handled:
            return should_include
        
        # If no custom route rule matched this operation, exclude it by default
        # This ensures that only explicitly allowed operations are included
        return False

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """
        Check if a path matches the pattern from custom routes.
        Supports regex patterns and wildcards.
        """
        try:
            return re.match(pattern, path) is not None
        except re.error:
            # If pattern is invalid regex, treat as exact match
            return path == pattern

    def get_type_info(self, service: str) -> Dict[str, Any]:
            """
            Get detailed parameter information for a service.
            
            Args:
                service: The service name (operationId)
            """
            if service not in self.service_info:
                return {
                    RESPONSE_KEYS['ERROR']: ERROR_MESSAGES['SERVICE_NOT_FOUND'].format(service),
                    'available_services': list(self.service_info.keys())
                }

            service_data = self.service_info[service]

            # Parameters are already enhanced with schema information
            parameters = service_data.get(SERVICE_KEYS['PARAMETERS'], DEFAULT_VALUES['EMPTY_LIST'])

            return {
                'service': service,
                SERVICE_KEYS['OPERATION_ID']: service_data[SERVICE_KEYS['OPERATION_ID']],
                SERVICE_KEYS['SUMMARY']: service_data[SERVICE_KEYS['SUMMARY']],
                SERVICE_KEYS['DESCRIPTION']: service_data[SERVICE_KEYS['DESCRIPTION']],
                SERVICE_KEYS['HTTP_METHOD']: service_data[SERVICE_KEYS['HTTP_METHOD']],
                SERVICE_KEYS['PATH']: service_data[SERVICE_KEYS['PATH']],
                'parameters': parameters,
                SERVICE_KEYS['REQUEST_BODY']: service_data[SERVICE_KEYS['REQUEST_BODY']],
                SERVICE_KEYS['RESPONSES']: service_data[SERVICE_KEYS['RESPONSES']],
                SERVICE_KEYS['TAGS']: service_data[SERVICE_KEYS['TAGS']]
            }

    def get_service_info(self, service: Optional[str] = None) -> Dict[str, Any]:
            """
            Discover available services (operations).
            
            Args:
                service: Optional service name (operationId). If None, lists all services.
            """
            if service is None:
                return {
                    'available_services': {
                        name: {
                            SERVICE_KEYS['OPERATION_ID']: info[SERVICE_KEYS['OPERATION_ID']],
                            SERVICE_KEYS['DESCRIPTION']: info[SERVICE_KEYS['DESCRIPTION']],
                            SERVICE_KEYS['SUMMARY']: info[SERVICE_KEYS['SUMMARY']],
                            SERVICE_KEYS['HTTP_METHOD']: info[SERVICE_KEYS['HTTP_METHOD']],
                            SERVICE_KEYS['PATH']: info[SERVICE_KEYS['PATH']],
                            SERVICE_KEYS['TAGS']: info[SERVICE_KEYS['TAGS']]
                        }
                        for name, info in self.service_info.items()
                    },
                    'total_services': len(self.service_info),
                    'usage': USAGE_MESSAGES['GET_SERVICE_INFO']
                }

            if service not in self.service_info:
                return {
                    RESPONSE_KEYS['ERROR']: ERROR_MESSAGES['SERVICE_NOT_FOUND'].format(service),
                    'available_services': list(self.service_info.keys())
                }

            service_data = self.service_info[service]

            # Build schema summary
            schema_summary = {
                'service': service,
                'operation_id': service_data.get(SERVICE_KEYS['OPERATION_ID']),
                'http_method': service_data.get(SERVICE_KEYS['HTTP_METHOD']),
                'path': service_data.get(SERVICE_KEYS['PATH']),
                'parameters_summary': {
                    'count': len(service_data.get(SERVICE_KEYS['PARAMETERS'], [])),
                    'path_params': len([p for p in service_data.get(SERVICE_KEYS['PARAMETERS'], []) if p.get(PARAMETER_KEYS['IN']) == 'path']),
                    'query_params': len([p for p in service_data.get(SERVICE_KEYS['PARAMETERS'], []) if p.get(PARAMETER_KEYS['IN']) == 'query']),
                    'header_params': len([p for p in service_data.get(SERVICE_KEYS['PARAMETERS'], []) if p.get(PARAMETER_KEYS['IN']) == 'header']),
                    'has_schemas': any(p.get('schema') for p in service_data.get(SERVICE_KEYS['PARAMETERS'], []) if isinstance(p, dict))
                },
                'request_body_summary': {
                    'has_schema': bool(service_data.get(SERVICE_KEYS['REQUEST_BODY'])),
                    'has_example': bool(service_data.get(SERVICE_KEYS['REQUEST_BODY'], {}).get(SCHEMA_KEYS['EXAMPLE'])) if service_data.get(SERVICE_KEYS['REQUEST_BODY']) else False,
                    'has_ref': bool(service_data.get(SERVICE_KEYS['REQUEST_BODY'], {}).get('original_ref')) if service_data.get(SERVICE_KEYS['REQUEST_BODY']) else False,
                    'schema_type': service_data.get(SERVICE_KEYS['REQUEST_BODY'], {}).get(SCHEMA_KEYS['TYPE']) if service_data.get(SERVICE_KEYS['REQUEST_BODY']) else None
                },
                'responses_summary': {
                    'count': len(service_data.get(SERVICE_KEYS['RESPONSES'], {})),
                    'has_schemas': any(r.get('schema') for r in service_data.get(SERVICE_KEYS['RESPONSES'], {}).values() if isinstance(r, dict)),
                    'has_refs': any(r.get('original_ref') for r in service_data.get(SERVICE_KEYS['RESPONSES'], {}).values() if isinstance(r, dict)),
                    'status_codes': list(service_data.get(SERVICE_KEYS['RESPONSES'], {}).keys()) if isinstance(service_data.get(SERVICE_KEYS['RESPONSES'], {}), dict) else []
                }
            }
            
            return {
                'service': service,
                SERVICE_KEYS['OPERATION_ID']: service_data[SERVICE_KEYS['OPERATION_ID']],
                SERVICE_KEYS['SUMMARY']: service_data[SERVICE_KEYS['SUMMARY']],
                SERVICE_KEYS['DESCRIPTION']: service_data[SERVICE_KEYS['DESCRIPTION']],
                SERVICE_KEYS['HTTP_METHOD']: service_data[SERVICE_KEYS['HTTP_METHOD']],
                SERVICE_KEYS['PATH']: service_data[SERVICE_KEYS['PATH']],
                'parameters': service_data[SERVICE_KEYS['PARAMETERS']],
                SERVICE_KEYS['REQUEST_BODY']: service_data[SERVICE_KEYS['REQUEST_BODY']],
                SERVICE_KEYS['RESPONSES']: service_data[SERVICE_KEYS['RESPONSES']],
                SERVICE_KEYS['TAGS']: service_data[SERVICE_KEYS['TAGS']],
                'schema_summary': schema_summary
            }

    async def make_tool_call(
        self,
        service: str,
        request: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
            """
            Execute an API call to the specified service.
            
            Args:
                service: The service name (operationId)
                request: Request data with path_params, query_params, headers, body
            """
            if service not in self.service_info:
                return {
                    RESPONSE_KEYS['ERROR']: ERROR_MESSAGES['SERVICE_NOT_FOUND'].format(service),
                    'available_services': list(self.service_info.keys())
                }

            # Ensure request is a dictionary
            request_dict = request if request is not None else DEFAULT_VALUES['EMPTY_DICT']

            service_data = self.service_info[service]

            try:
                # Manual request execution using the httpx client
                url_path = service_data[SERVICE_KEYS['PATH']]
                path_params = request_dict.get(REQUEST_KEYS['PATH_PARAMS'], DEFAULT_VALUES['EMPTY_DICT'])
                for param_name, param_value in path_params.items():
                    url_path = url_path.replace(f"{{{param_name}}}", str(param_value))

                response = await self.client.request(
                    method=service_data[SERVICE_KEYS['HTTP_METHOD']],
                    url=url_path,
                    params=request_dict.get(REQUEST_KEYS['QUERY_PARAMS'], DEFAULT_VALUES['EMPTY_DICT']),
                    headers=request_dict.get(REQUEST_KEYS['HEADERS'], DEFAULT_VALUES['EMPTY_DICT']),
                    json=request_dict.get(REQUEST_KEYS['BODY'])
                )

                try:
                    response_data = response.json()
                except:
                    response_data = response.text

                return {
                    RESPONSE_KEYS['SUCCESS']: True,
                    RESPONSE_KEYS['SERVICE']: service,
                    RESPONSE_KEYS['STATUS_CODE']: response.status_code,
                    RESPONSE_KEYS['DATA']: response_data
                }

            except Exception as e:
                return {
                    RESPONSE_KEYS['SUCCESS']: False,
                    RESPONSE_KEYS['SERVICE']: service,
                    RESPONSE_KEYS['ERROR']: ERROR_MESSAGES['API_CALL_FAILED'].format(str(e))
                }

