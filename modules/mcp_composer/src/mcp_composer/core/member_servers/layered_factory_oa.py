import re
import json
from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.providers.openapi import MCPType, RouteMap
from fastmcp.tools import Tool
from fastmcp.utilities.openapi import (
    clean_schema_for_display,
    extract_output_schema_from_responses,
    generate_example_from_schema,
)

from mcp_composer.core.member_servers.layered_constants import (
    DEFAULT_MCP_TYPE,
    DEFAULT_PATTERN,
    DEFAULT_VALUES,
    ERROR_MESSAGES,
    FALLBACK_UNKNOWN,
    HTTP_METHODS,
    LAYERED_DISCOVERY_INSTRUCTIONS,
    OPENAPI_KEYS,
    OPERATION_KEYS,
    PARAMETER_KEYS,
    REQUEST_KEYS,
    RESPONSE_KEYS,
    SCHEMA_KEYS,
    SERVICE_KEYS,
    USAGE_MESSAGES,
)
from mcp_composer.core.member_servers.layered_discovery import (
    DEFAULT_LIMIT,
    ToolCatalogEntry,
    parse_tags_arg,
    resolve_discovery_response,
    suggest_names,
)
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()

# Auth-context helpers (optional middleware). Stubs keep forwarding testable and
# allow process-level OAuth/JWT to remain the primary gate.
AUTH_HEADER_ISV_TOKEN = "X-ISV-Token"
AUTH_HEADER_PLATFORM_COOKIE = "X-Platform-Cookie"
AUTH_HEADER_USER_INSTANCES = "X-User-Instances"
AUTH_KEY_AUTH_TOKEN = "auth_token"
AUTH_KEY_COOKIES = "cookies"
AUTH_KEY_ISV_TOKEN = "isv_token"
AUTH_KEY_USER_INSTANCES = "user_instances"
AUTH_KEY_USER_INSTANCES_FULL = "user_instances_full"
REQUEST_CONTEXT_KEY = "x-request-context"


def get_auth_context():  # type: ignore[no-redef]
    return None


AUTH_CONTEXT_AVAILABLE = True


class LayeredOpenAPIFactory(FastMCP):
    def __init__(
        self,
        openapi_spec: dict[str, Any],
        client: httpx.AsyncClient,
        server_id: str = "unknown",  # Server ID for authorization (legacy)
        product_id: str | None = None,  # NEW: Product ID for authorization matching
        custom_routes: list[RouteMap] | None = None,
        custom_routes_exclude_all: (
            list[RouteMap] | None
        ) = None,  # pylint: disable=unused-argument
        tool_descriptions: dict[str, str] | None = None,
    ):
        # Initialize the parent FastMCP class first
        super().__init__(
            name="Layered OpenAPI FastMCP",
            instructions=(
                LAYERED_DISCOVERY_INSTRUCTIONS
                + "\n\nAll tools automatically resolve OpenAPI schema references "
                "and provide enhanced metadata including examples and cleaned schemas."
            ),
        )
        LAYERED_SERVICE_ARGS_RETURNS = """
        Args:
            service: Optional exact service name (operationId) for a concise summary.
            query: Search text to rank relevant services (preferred for large catalogs).
            tags: Optional tag filter (list or comma-separated string).
            limit: Max matches to return (default 20, max 50).

        Returns:
            Discovery payload (matches / overview) or a concise service summary.
        """

        LAYERED_TYPE_ARGS_RETURNS = """
        Args:
            service: The service name (operationId)

        Returns:
            List of operations or details about a specific operation.
        """

        LAYERED_CALL_ARGS_RETURNS = """
        Args:
            service: The service name (operationId)
            request: Request data with path_params, query_params, headers, body

        Returns:
            The response from the API call.
        """

        self.openapi_spec = openapi_spec
        self.client = client
        self.server_id = server_id  # Store server_id for authorization (legacy)
        self.product_id = product_id  # Store product_id for authorization matching
        self.custom_routes = custom_routes or []
        self.service_info = self._build_service_metadata()
        self._tool_descriptions = tool_descriptions or {}

        logger.info(
            "LayeredOpenAPIFactory initialized with server_id: %s, product_id: %s",
            self.server_id,
            self.product_id,
        )

        # Create the underlying FastMCP server with custom routes
        # self._mcp_server = FastMCP.from_openapi(self.openapi_spec,
        # client=self.client, route_maps= custom_routes_exclude_all)

        get_service_desc = (
            self._safe_tool_description(
                "get_service_info",
                "Discover OpenAPI operations via query-first search "
                "(or name overview on large catalogs). Prefer get_service_info(query='...', limit=20).",
            )
            + LAYERED_SERVICE_ARGS_RETURNS
        ).strip()

        get_type_desc = (
            self._safe_tool_description(
                "get_type_info",
                "Show detailed parameter, request, and response schema information for a chosen OpenAPI service.",
            )
            + LAYERED_TYPE_ARGS_RETURNS
        ).strip()

        make_call_desc = (
            self._safe_tool_description(
                "make_tool_call",
                "Execute an HTTP request against the underlying API for a chosen OpenAPI service.",
            )
            + LAYERED_CALL_ARGS_RETURNS
        ).strip()

        # Add our custom tools with configurable descriptions
        self.add_tool(
            Tool.from_function(
                self.get_service_info,
                description=get_service_desc,
            )
        )
        self.add_tool(
            Tool.from_function(
                self.get_type_info,
                description=get_type_desc,
            )
        )
        self.add_tool(
            Tool.from_function(
                self.make_tool_call,
                description=make_call_desc,
            )
        )

    def _safe_tool_description(self, key, fallback):
        value = self._tool_descriptions.get(key, "")
        if not isinstance(value, str):
            value = ""
        return value.strip() or fallback

    def _get_instance_product_id(self, instance: dict[str, Any]) -> str | None:
        """
        Get productId from an instance. Supports full shape (subscription.productId/product_id),
        normalized shape (top-level productId/product_id), and snake_case keys.
        """
        sub = instance.get("subscription")
        if isinstance(sub, dict):
            val = sub.get("productId") or sub.get("product_id")
            if val:
                return val
        val = instance.get("productId") or instance.get("product_id")
        return val if val else None

    def _authorize_and_select_instance(
        self,
        instances: list[dict[str, Any]],
        server_id: str,
    ) -> dict[str, Any] | None:
        """
        Authorize user access by matching productId with instance productId.
        Returns the first matching active instance or None if unauthorized.

        Supports both full instance shape (subscription.productId) and normalized shape (top-level productId).
        """
        if not instances:
            logger.warning("No user instances available for authorization")
            return None

        if not self.product_id:
            logger.error(
                "productId not configured in server config. Authorization cannot proceed."
            )
            return None

        logger.info(
            "Using productId-based authorization: productId='%s'", self.product_id
        )

        matching_instances = [
            inst
            for inst in instances
            if self._get_instance_product_id(inst) == self.product_id
            and inst.get("state") == "active"
        ]

        if matching_instances:
            selected = matching_instances[0]
            subscription_name = (selected.get("subscription") or {}).get(
                "subscriptionName", FALLBACK_UNKNOWN
            )
            logger.info(
                "✓ Authorization successful: productId '%s' matched instance subscription '%s'",
                self.product_id,
                subscription_name,
            )
            logger.info(
                "  Instance: id='%s', name='%s'",
                selected.get("id"),
                selected.get("name"),
            )
            return selected

        # No match found with productId
        available_products = list(
            set(
                self._get_instance_product_id(inst) or FALLBACK_UNKNOWN
                for inst in instances
            )
        )
        logger.warning(
            "Authorization failed: productId '%s' not found in user instances. Available productIds: %s",
            self.product_id,
            available_products,
        )
        return None

    def _extract_host_from_instance(self, instance: dict[str, Any]) -> str | None:
        """
        Extract the base host URL from an instance's dashboardURL.

        Args:
            instance: Instance dictionary containing dashboardURL

        Returns:
            Base URL (e.g., "https://example.com")
            or None if not available
        """
        dashboard_url = instance.get("dashboardURL", "")
        if not dashboard_url:
            logger.warning("No dashboardURL found in instance")
            return None

        # Extract host part (everything before the query string)
        host = dashboard_url.split("?")[0].rstrip("/")

        # Extract base URL (protocol + domain, without path)
        try:
            from urllib.parse import urlparse

            parsed = urlparse(host)
            if parsed.scheme and parsed.netloc:
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                logger.debug("Extracted host from dashboardURL: %s", base_url)
                return base_url
        except Exception as e:
            logger.warning("Failed to parse dashboardURL '%s': %s", dashboard_url, e)

        return None

    def _build_instance_headers(self, instance: dict[str, Any]) -> dict[str, str]:
        """
        Build instance-specific headers from instance data.

        Args:
            instance: Instance dictionary

        Returns:
            Dict of headers to add to the request
        """
        headers: dict[str, str] = {}

        if instance_id := instance.get("id"):
            headers[REQUEST_CONTEXT_KEY] = instance_id

        logger.debug("Built instance headers: %s", list(headers.keys()))
        return headers

    def _resolve_schema_reference(self, ref: str) -> dict[str, Any]:
        """
        Resolve a schema reference to its actual definition.

        Args:
            ref: The reference string (e.g., "#/components/schemas/GetApplications")

        Returns:
            Dict containing the resolved schema definition
        """
        if not ref or not ref.startswith("#/"):
            return {}

        # Remove the leading '#/' and split by '/'
        parts = ref[2:].split("/")

        # Navigate through the OpenAPI spec to find the referenced schema
        current = self.openapi_spec
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return {}

        return current if isinstance(current, dict) else {}

    def _extract_parameter_schemas(
        self, parameters: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
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
                schema = param.get(PARAMETER_KEYS["SCHEMA"], {})
                original_ref = None

                # Handle schema references
                if schema and SCHEMA_KEYS["REF"] in schema:
                    original_ref = schema[SCHEMA_KEYS["REF"]]
                    resolved_schema = self._resolve_schema_reference(original_ref)
                    if resolved_schema:
                        schema = resolved_schema

                # Clean the schema for display
                cleaned_schema = clean_schema_for_display(schema) if schema else {}

                enhanced_param = {
                    PARAMETER_KEYS["NAME"]: param.get(PARAMETER_KEYS["NAME"]),
                    PARAMETER_KEYS["IN"]: param.get(PARAMETER_KEYS["IN"]),
                    PARAMETER_KEYS["REQUIRED"]: param.get(
                        PARAMETER_KEYS["REQUIRED"], DEFAULT_VALUES["REQUIRED"]
                    ),
                    PARAMETER_KEYS["TYPE"]: (
                        schema.get(SCHEMA_KEYS["TYPE"], DEFAULT_VALUES["UNKNOWN_TYPE"])
                        if schema
                        else DEFAULT_VALUES["UNKNOWN_TYPE"]
                    ),
                    PARAMETER_KEYS["DESCRIPTION"]: param.get(
                        PARAMETER_KEYS["DESCRIPTION"], DEFAULT_VALUES["EMPTY_STRING"]
                    ),
                    PARAMETER_KEYS["EXAMPLE"]: param.get(PARAMETER_KEYS["EXAMPLE"]),
                    "schema": cleaned_schema,
                    "original_ref": original_ref,
                }

                enhanced_params.append(enhanced_param)

        return enhanced_params

    def _extract_request_body_schema(
        self, request_body: dict[str, Any]
    ) -> dict[str, Any]:
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
        content = request_body.get(SCHEMA_KEYS["CONTENT"], {})
        json_content = content.get(SCHEMA_KEYS["APPLICATION_JSON"], {})
        schema = json_content.get(SCHEMA_KEYS["SCHEMA"], {})
        original_ref = None

        if schema:
            # Handle schema references
            if SCHEMA_KEYS["REF"] in schema:
                original_ref = schema[SCHEMA_KEYS["REF"]]
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
                        cleaned_schema[SCHEMA_KEYS["EXAMPLE"]] = example
                except Exception:
                    # Example generation is optional, continue without it
                    pass

                # Add original schema reference if it exists
                if original_ref:
                    cleaned_schema["original_ref"] = original_ref

                return cleaned_schema

        return {}

    def _extract_response_schemas(self, responses: dict[str, Any]) -> dict[str, Any]:
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
                content = response.get(SCHEMA_KEYS["CONTENT"], {})
                json_content = content.get(SCHEMA_KEYS["APPLICATION_JSON"], {})
                schema = json_content.get(SCHEMA_KEYS["SCHEMA"], {})
                original_ref = None

                # Handle schema references
                if schema and SCHEMA_KEYS["REF"] in schema:
                    original_ref = schema[SCHEMA_KEYS["REF"]]
                    resolved_schema = self._resolve_schema_reference(original_ref)
                    if resolved_schema:
                        schema = resolved_schema

                cleaned_responses[status_code] = {
                    "description": response.get("description", ""),
                    "schema": clean_schema_for_display(schema) if schema else {},
                    "original_ref": original_ref,
                }

        return cleaned_responses

    def _build_service_metadata(self) -> dict[str, dict[str, object]]:
        """
        Build service metadata from operations by parsing OpenAPI spec and applying custom routes filtering.
        Only operations that match the custom routes (TOOL) are included in service_info.
        """
        services = {}

        # Parse the OpenAPI spec paths and apply custom routes filtering
        if OPENAPI_KEYS["PATHS"] in self.openapi_spec:
            for path, path_item in self.openapi_spec[OPENAPI_KEYS["PATHS"]].items():
                for http_method, operation in path_item.items():
                    if http_method.lower() in HTTP_METHODS:
                        # Check if this operation should be included based on custom routes
                        if self._should_include_operation(http_method.upper(), path):
                            operation_id = operation.get(OPERATION_KEYS["OPERATION_ID"])
                            if operation_id:
                                services[operation_id] = {
                                    SERVICE_KEYS["NAME"]: operation_id,
                                    SERVICE_KEYS["OPERATION_ID"]: operation_id,
                                    SERVICE_KEYS["DESCRIPTION"]: operation.get(
                                        OPERATION_KEYS["DESCRIPTION"],
                                        operation.get(
                                            OPERATION_KEYS["SUMMARY"],
                                            f"API operation: {operation_id}",
                                        ),
                                    ),
                                    SERVICE_KEYS["SUMMARY"]: operation.get(
                                        OPERATION_KEYS["SUMMARY"],
                                        DEFAULT_VALUES["EMPTY_STRING"],
                                    ),
                                    SERVICE_KEYS["HTTP_METHOD"]: http_method.upper(),
                                    SERVICE_KEYS["PATH"]: path,
                                    SERVICE_KEYS[
                                        "PARAMETERS"
                                    ]: self._extract_parameter_schemas(
                                        operation.get(
                                            OPERATION_KEYS["PARAMETERS"],
                                            DEFAULT_VALUES["EMPTY_LIST"],
                                        )
                                    ),
                                    SERVICE_KEYS[
                                        "REQUEST_BODY"
                                    ]: self._extract_request_body_schema(
                                        operation.get(OPERATION_KEYS["REQUEST_BODY"])
                                    ),
                                    SERVICE_KEYS[
                                        "RESPONSES"
                                    ]: self._extract_response_schemas(
                                        operation.get(
                                            OPERATION_KEYS["RESPONSES"],
                                            DEFAULT_VALUES["EMPTY_DICT"],
                                        )
                                    ),
                                    SERVICE_KEYS["TAGS"]: operation.get(
                                        OPERATION_KEYS["TAGS"],
                                        DEFAULT_VALUES["EMPTY_LIST"],
                                    ),
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
            methods = getattr(route_rule, "methods", DEFAULT_VALUES["EMPTY_LIST"])
            pattern = getattr(route_rule, "pattern", DEFAULT_PATTERN)
            mcp_type = getattr(route_rule, "mcp_type", DEFAULT_MCP_TYPE)

            # Check if this operation matches the route rule
            if http_method in methods and self._matches_pattern(path, pattern):  # type: ignore[operator]
                operation_handled = True

                if mcp_type in (MCPType.TOOL, MCPType.RESOURCE):
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

    def _catalog_entries(self) -> list[ToolCatalogEntry]:
        """Build normalized discovery entries from OpenAPI service metadata."""
        entries: list[ToolCatalogEntry] = []
        for name, info in self.service_info.items():
            entries.append(
                ToolCatalogEntry(
                    name=name,
                    summary=str(info.get(SERVICE_KEYS["SUMMARY"]) or ""),
                    description=str(info.get(SERVICE_KEYS["DESCRIPTION"]) or ""),
                    path=str(info.get(SERVICE_KEYS["PATH"]) or ""),
                    http_method=str(info.get(SERVICE_KEYS["HTTP_METHOD"]) or ""),
                    tags=list(info.get(SERVICE_KEYS["TAGS"]) or []),
                    extra={
                        "operationId": info.get(SERVICE_KEYS["OPERATION_ID"], name)
                    },
                )
            )
        return entries

    def _not_found_suggestions(self, service: str) -> dict[str, Any]:
        return {
            RESPONSE_KEYS["ERROR"]: ERROR_MESSAGES["SERVICE_NOT_FOUND"].format(service),
            "suggestions": suggest_names(self._catalog_entries(), service, limit=10),
            "usage": USAGE_MESSAGES["GET_SERVICE_INFO"],
        }

    def get_type_info(self, service: str) -> dict[str, Any]:
        """
        Get detailed parameter information for a service.

        Args:
            service: The service name (operationId)
        """
        if service not in self.service_info:
            return self._not_found_suggestions(service)

        service_data = self.service_info[service]

        # Parameters are already enhanced with schema information
        parameters = service_data.get(
            SERVICE_KEYS["PARAMETERS"], DEFAULT_VALUES["EMPTY_LIST"]
        )

        return {
            "service": service,
            SERVICE_KEYS["OPERATION_ID"]: service_data[SERVICE_KEYS["OPERATION_ID"]],
            SERVICE_KEYS["SUMMARY"]: service_data[SERVICE_KEYS["SUMMARY"]],
            SERVICE_KEYS["DESCRIPTION"]: service_data[SERVICE_KEYS["DESCRIPTION"]],
            SERVICE_KEYS["HTTP_METHOD"]: service_data[SERVICE_KEYS["HTTP_METHOD"]],
            SERVICE_KEYS["PATH"]: service_data[SERVICE_KEYS["PATH"]],
            "parameters": parameters,
            SERVICE_KEYS["REQUEST_BODY"]: service_data[SERVICE_KEYS["REQUEST_BODY"]],
            SERVICE_KEYS["RESPONSES"]: service_data[SERVICE_KEYS["RESPONSES"]],
            SERVICE_KEYS["TAGS"]: service_data[SERVICE_KEYS["TAGS"]],
        }

    def get_service_info(
        self,
        service: str | None = None,
        query: str | None = None,
        tags: list[str] | str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """
        Discover available services (operations) with query-first ranking.

        Args:
            service: Optional exact service name (operationId) for detail mode.
            query: Search text to rank relevant services.
            tags: Optional tag filter (list or comma-separated string).
            limit: Max matches to return (default 20, max 50).
        """
        entries = self._catalog_entries()

        if service is not None:
            if service not in self.service_info:
                return self._not_found_suggestions(service)

            service_data = self.service_info[service]
            parameters = service_data.get(SERVICE_KEYS["PARAMETERS"], []) or []
            responses = service_data.get(SERVICE_KEYS["RESPONSES"], {}) or {}

            # Concise summary only — full schemas live in get_type_info.
            return {
                "service": service,
                SERVICE_KEYS["OPERATION_ID"]: service_data[SERVICE_KEYS["OPERATION_ID"]],
                SERVICE_KEYS["SUMMARY"]: service_data[SERVICE_KEYS["SUMMARY"]],
                SERVICE_KEYS["DESCRIPTION"]: service_data[SERVICE_KEYS["DESCRIPTION"]],
                SERVICE_KEYS["HTTP_METHOD"]: service_data[SERVICE_KEYS["HTTP_METHOD"]],
                SERVICE_KEYS["PATH"]: service_data[SERVICE_KEYS["PATH"]],
                SERVICE_KEYS["TAGS"]: service_data[SERVICE_KEYS["TAGS"]],
                "schema_summary": {
                    "parameters_count": len(parameters),
                    "path_params": len(
                        [
                            p
                            for p in parameters
                            if isinstance(p, dict)
                            and p.get(PARAMETER_KEYS["IN"]) == "path"
                        ]
                    ),
                    "query_params": len(
                        [
                            p
                            for p in parameters
                            if isinstance(p, dict)
                            and p.get(PARAMETER_KEYS["IN"]) == "query"
                        ]
                    ),
                    "has_request_body": bool(
                        service_data.get(SERVICE_KEYS["REQUEST_BODY"])
                    ),
                    "response_status_codes": (
                        list(responses.keys()) if isinstance(responses, dict) else []
                    ),
                },
                "next": USAGE_MESSAGES.get(
                    "GET_TYPE_INFO",
                    "Call get_type_info for full schemas.",
                ),
            }

        return resolve_discovery_response(
            entries,
            query=query,
            tags=parse_tags_arg(tags),
            limit=limit,
            total_key="total_services",
            matches_key="matches",
        )

    async def make_tool_call(
        self, service: str, request: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Execute an API call to the specified service.

        Args:
            service: The service name (operationId)
            request: Request data with path_params, query_params, headers, body
        """
        if service not in self.service_info:
            return self._not_found_suggestions(service)

        # Ensure request is a dictionary
        request_dict = request if request is not None else DEFAULT_VALUES["EMPTY_DICT"]

        service_data = self.service_info[service]
        logger.debug("DEBUG: service_data: %s", service_data)
        try:
            # Manual request execution using the httpx client
            url_path = service_data[SERVICE_KEYS["PATH"]]
            path_params = request_dict.get(  # type: ignore[attr-defined]
                REQUEST_KEYS["PATH_PARAMS"], DEFAULT_VALUES["EMPTY_DICT"]
            )
            for param_name, param_value in path_params.items():
                url_path = url_path.replace(f"{{{param_name}}}", str(param_value))  # type: ignore[attr-defined]

            # Extract request components
            http_method = service_data[SERVICE_KEYS["HTTP_METHOD"]]
            query_params = request_dict.get(  # type: ignore[attr-defined]
                REQUEST_KEYS["QUERY_PARAMS"], DEFAULT_VALUES["EMPTY_DICT"]
            )
            request_headers = request_dict.get(  # type: ignore[attr-defined]
                REQUEST_KEYS["HEADERS"], DEFAULT_VALUES["EMPTY_DICT"]
            )
            request_body = request_dict.get(REQUEST_KEYS["BODY"])  # type: ignore[attr-defined]

            # Get authentication context and build auth headers
            auth_headers = {}
            selected_instance = None
            instance_host = None

            if AUTH_CONTEXT_AVAILABLE:
                try:
                    auth_context = get_auth_context()
                    logger.debug("Auth context retrieved: %s", auth_context)
                    if auth_context:
                        # AUTHORIZATION CHECK: Get full instance data
                        instances_full = auth_context.get(
                            AUTH_KEY_USER_INSTANCES_FULL, []
                        )

                        logger.info(
                            "DEBUG: instances_full type=%s, length=%d",
                            type(instances_full).__name__,
                            len(instances_full),
                        )
                        if instances_full:
                            logger.info(
                                "DEBUG: First instance keys: %s",
                                (
                                    list(instances_full[0].keys())
                                    if instances_full
                                    else "N/A"
                                ),
                            )
                            logger.info(
                                "DEBUG: First instance subscription: %s",
                                (
                                    (instances_full[0].get("subscription") or {})
                                    if instances_full
                                    else "N/A"
                                ),
                            )

                        if not instances_full:
                            logger.warning(
                                "No user instances found in auth context for service: %s",
                                service,
                            )
                            return {
                                "error": "Unauthorized",
                                "message": "No user instances available for authorization",
                                "status_code": 401,
                                "service": service,
                                "server_id": self.server_id,
                            }

                        # AUTHORIZATION: Match product_id with instance.subscription.productId
                        logger.debug(
                            "DEBUG: Calling _authorize_and_select_instance (product_id='%s')",
                            self.product_id,
                        )
                        selected_instance = self._authorize_and_select_instance(
                            instances_full,
                            self.server_id,
                        )
                        logger.debug(
                            "DEBUG: _authorize_and_select_instance returned: %s",
                            "instance found" if selected_instance else "None",
                        )

                        if not selected_instance:
                            # No user instance had productId matching server's product_id
                            available_product_ids = list(
                                set(
                                    self._get_instance_product_id(i) or FALLBACK_UNKNOWN
                                    for i in instances_full
                                )
                            )
                            logger.error(
                                "Authorization failed for service '%s': product_id '%s' (from config) not in user instances' productIds %s",
                                service,
                                self.product_id,
                                available_product_ids,
                            )
                            return {
                                "error": "Unauthorized",
                                "message": f"Access denied: No instance with productId '{self.product_id}'. "
                                f"User instances have productIds: {', '.join(available_product_ids)}",
                                "status_code": 401,
                                "service": service,
                                "server_id": self.server_id,
                                "product_id": self.product_id,
                                "available_product_ids": available_product_ids,
                            }

                        # ROUTING: Extract host for dynamic routing
                        instance_host = self._extract_host_from_instance(
                            selected_instance
                        )
                        if instance_host:
                            logger.info(
                                "✓ Using instance-specific host: %s", instance_host
                            )

                        # HEADERS: Build instance-specific headers
                        instance_headers = self._build_instance_headers(
                            selected_instance
                        )
                        auth_headers.update(instance_headers)

                        # Debug: confirm instance_id and host resolved from auth context for this request
                        resolved_instance_id = selected_instance.get(
                            "id"
                        ) or selected_instance.get("instance_id", "")
                        resolved_product_id = (
                            self._get_instance_product_id(selected_instance) or ""
                        )
                        logger.debug(
                            "Auth context resolved for service '%s': instance_id=%s, productId=%s, host=%s",
                            service,
                            resolved_instance_id,
                            resolved_product_id,
                            instance_host or "default",
                        )
                        logger.info(
                            "✓ Authorized and routed: server_id='%s', instance='%s' (name=%s), host=%s",
                            self.server_id,
                            selected_instance.get("id"),
                            selected_instance.get("name"),
                            instance_host or "default",
                        )

                        # Check for auth_token (cookie-based authorization)
                        # If present, use it as Authorization header with "ibm-platform" prefix
                        auth_token_value = auth_context.get(AUTH_KEY_AUTH_TOKEN)
                        logger.debug("AUTH_KEY_AUTH_TOKEN value: %s", auth_token_value)
                        if auth_token_value:
                            # Format: "ibm-platform {cookie_value}"
                            auth_headers["Authorization"] = (
                                f"ibm-platform {auth_token_value}"
                            )
                            logger.info(
                                "✓ Using cookie-based authorization (ibm-platform %s) for service: %s",
                                (
                                    auth_token_value[:20] + "..."
                                    if len(auth_token_value) > 20
                                    else auth_token_value
                                ),
                                service,
                            )
                        else:
                            logger.debug(
                                "No auth_token found in context, will use OAuth2 Bearer token"
                            )

                        # Add ISV token as X-ISV-Token header
                        if auth_context.get(AUTH_KEY_ISV_TOKEN):
                            auth_headers[AUTH_HEADER_ISV_TOKEN] = auth_context[
                                AUTH_KEY_ISV_TOKEN
                            ]
                            logger.debug(
                                "Adding ISV token to request for service: %s", service
                            )

                        # Add platform cookies as X-Platform-Cookie header.
                        # Use selected instance id for x-request-context (backend expects instance id, not dashboard URL).
                        if auth_context.get(AUTH_KEY_COOKIES):
                            cookies_for_request = dict(auth_context[AUTH_KEY_COOKIES])
                            instance_id_for_context = selected_instance.get(
                                "id"
                            ) or selected_instance.get("instance_id")
                            if instance_id_for_context:
                                cookies_for_request[REQUEST_CONTEXT_KEY] = (
                                    instance_id_for_context
                                )
                            cookie_str = "; ".join(
                                f"{name}={value}"
                                for name, value in cookies_for_request.items()
                            )
                            if cookie_str:
                                auth_headers[AUTH_HEADER_PLATFORM_COOKIE] = cookie_str
                                logger.debug(
                                    "Adding platform cookies (%s=%s) for service: %s",
                                    REQUEST_CONTEXT_KEY,
                                    instance_id_for_context or "(from context)",
                                    service,
                                )

                        # Add user instances as X-User-Instances header (JSON)
                        if auth_context.get(AUTH_KEY_USER_INSTANCES):
                            auth_headers[AUTH_HEADER_USER_INSTANCES] = json.dumps(
                                auth_context[AUTH_KEY_USER_INSTANCES]
                            )
                            logger.debug(
                                "Adding user instances to request for service: %s",
                                service,
                            )
                except Exception as e:
                    logger.error(
                        "Failed to process auth context for service %s: %s", service, e
                    )
                    return {
                        "error": "Authorization Error",
                        "message": f"Failed to process authorization: {str(e)}",
                        "status_code": 500,
                        "service": service,
                    }

            # Merge request headers with auth headers (auth headers take precedence)
            final_headers = {**request_headers, **auth_headers}

            # Build full URL with instance host override
            if instance_host:
                # Use instance-specific host from authorized instance
                base_url = instance_host
                logger.info("Using instance-specific host: %s", base_url)
            else:
                # Fallback to default client base_url
                base_url = str(self.client.base_url) if self.client.base_url else ""
                if not instance_host and AUTH_CONTEXT_AVAILABLE:
                    logger.warning(
                        "No instance host found, using default: %s", base_url
                    )

            full_url = f"{base_url}{url_path}"

            # Log outgoing HTTP request details
            logger.info("=" * 80)
            logger.info("OUTGOING HTTP REQUEST TO MEMBER SERVER")
            logger.info("=" * 80)
            logger.info("Service: %s", service)
            logger.info("HTTP Method: %s", http_method)
            logger.info("Full URL: %s", full_url)

            if query_params:
                logger.info("-" * 80)
                logger.info("Query Parameters:")
                try:
                    logger.info("%s", json.dumps(query_params, indent=2))
                except:
                    logger.info("%s", query_params)

            logger.info("-" * 80)
            logger.info("Request Headers:")
            # Log client's default headers
            if (
                hasattr(self.client, "headers")
                and self.client.headers
                and hasattr(self.client.headers, "items")
            ):
                logger.info("  Default Client Headers:")
                try:
                    for header_name, header_value in self.client.headers.items():
                        # Redact sensitive headers
                        if header_name.lower() in [
                            "authorization",
                            "api-key",
                            "x-api-key",
                        ]:
                            if len(str(header_value)) > 20:
                                redacted = f"{str(header_value)[:10]}...{str(header_value)[-10:]}"
                            else:
                                redacted = "***REDACTED***"
                            logger.info("    %s: %s", header_name, redacted)
                        else:
                            logger.info("    %s: %s", header_name, header_value)
                except (TypeError, AttributeError) as e:
                    logger.debug("Could not iterate client headers: %s", e)

            # Log request-specific headers
            if request_headers:
                logger.info("  Request-Specific Headers:")
                for header_name, header_value in request_headers.items():
                    # Redact sensitive headers
                    if header_name.lower() in ["authorization", "api-key", "x-api-key"]:
                        if len(str(header_value)) > 20:
                            redacted = (
                                f"{str(header_value)[:10]}...{str(header_value)[-10:]}"
                            )
                        else:
                            redacted = "***REDACTED***"
                        logger.info("    %s: %s", header_name, redacted)
                    else:
                        logger.info("    %s: %s", header_name, header_value)

            if request_body is not None:
                logger.info("-" * 80)
                logger.info("Request Body:")
                try:
                    body_json = json.dumps(request_body, indent=2)
                    if len(body_json) > 2000:
                        logger.info("%s", body_json[:2000])
                        logger.info("... (+%d chars)", len(body_json) - 2000)
                    else:
                        logger.info("%s", body_json)
                except:
                    logger.info("%s", str(request_body)[:2000])

            logger.info("=" * 80)

            # Make the actual HTTP request with merged headers
            if auth_headers.get("Authorization"):
                logger.info("Using plain HTTP client with explicit Authorization header")
                async with httpx.AsyncClient(
                    base_url=self.client.base_url,
                    timeout=(
                        self.client.timeout if hasattr(self.client, "timeout") else 30.0
                    ),
                ) as plain_client:
                    response = await plain_client.request(
                        method=str(http_method),  # type: ignore[arg-type]
                        url=str(url_path),  # type: ignore[arg-type]
                        params=query_params,
                        headers=final_headers,
                        json=request_body,
                    )
            else:
                logger.debug("Using configured HTTP client for authentication")
                response = await self.client.request(
                    method=str(http_method),  # type: ignore[arg-type]
                    url=str(url_path),  # type: ignore[arg-type]
                    params=query_params,
                    headers=final_headers,
                    json=request_body,
                )

            # Log the actual headers that were sent (including auth headers added by httpx)
            logger.info("-" * 80)
            logger.info("ACTUAL HEADERS SENT (including httpx-added headers):")
            if (
                hasattr(response, "request")
                and hasattr(response.request, "headers")
                and hasattr(response.request.headers, "items")
            ):
                try:
                    for header_name, header_value in response.request.headers.items():
                        # Redact sensitive headers
                        if header_name.lower() in [
                            "authorization",
                            "api-key",
                            "x-api-key",
                            "client-id",
                            "client-secret",
                        ]:
                            if len(str(header_value)) > 20:
                                redacted = f"{str(header_value)[:10]}...{str(header_value)[-10:]}"
                            else:
                                redacted = "***REDACTED***"
                            logger.info("  %s: %s", header_name, redacted)
                        else:
                            logger.info("  %s: %s", header_name, header_value)
                except (TypeError, AttributeError) as e:
                    logger.debug("Could not iterate response.request.headers: %s", e)
            logger.info("-" * 80)

            # Log response details
            logger.info("=" * 80)
            logger.info("HTTP RESPONSE FROM MEMBER SERVER")
            logger.info("=" * 80)
            logger.info("Service: %s", service)
            logger.info("Status Code: %d", response.status_code)
            logger.info(
                "Status Text: %s",
                response.reason_phrase if hasattr(response, "reason_phrase") else "N/A",
            )

            logger.info("-" * 80)
            logger.info("Response Headers:")
            if hasattr(response, "headers") and hasattr(response.headers, "items"):
                try:
                    for header_name, header_value in response.headers.items():
                        logger.info("  %s: %s", header_name, header_value)
                except (TypeError, AttributeError) as e:
                    logger.debug("Could not iterate response.headers: %s", e)

            logger.info("-" * 80)
            logger.info("Response Body:")

            try:
                response_data = response.json()
                response_json = json.dumps(response_data, indent=2)
                if len(response_json) > 2000:
                    logger.info("%s", response_json[:2000])
                    logger.info("... (+%d chars)", len(response_json) - 2000)
                else:
                    logger.info("%s", response_json)
            except:
                response_data = response.text
                if len(response_data) > 2000:
                    logger.info("%s", response_data[:2000])
                    logger.info("... (+%d chars)", len(response_data) - 2000)
                else:
                    logger.info("%s", response_data)

            logger.info("=" * 80)

            return {
                RESPONSE_KEYS["SUCCESS"]: True,
                RESPONSE_KEYS["SERVICE"]: service,
                RESPONSE_KEYS["STATUS_CODE"]: response.status_code,
                RESPONSE_KEYS["DATA"]: response_data,
            }

        except Exception as e:
            logger.error("=" * 80)
            logger.error("HTTP REQUEST FAILED")
            logger.error("=" * 80)
            logger.error("Service: %s", service)
            logger.error("Error: %s", str(e))
            logger.error("Error Type: %s", type(e).__name__)
            logger.error("=" * 80)

            return {
                RESPONSE_KEYS["SUCCESS"]: False,
                RESPONSE_KEYS["SERVICE"]: service,
                RESPONSE_KEYS["ERROR"]: ERROR_MESSAGES["API_CALL_FAILED"].format(
                    str(e)
                ),
            }
