"""Resource management module for MCP Composer."""

import logging
from typing import Dict, List
from fastmcp.resources import ResourceManager
from fastmcp.resources import ResourceTemplate, Resource
from fastmcp.settings import DuplicateBehavior

from pydantic import AnyUrl

logger = logging.getLogger(__name__)


class MCPResourceManager(ResourceManager):
    """Custom resource manager that works with FastMCP's internal ResourceManager."""

    def __init__(
            self,
            server_manager=None,
            duplicate_behavior: DuplicateBehavior | None = None,
            database=None
        ):
        super().__init__(duplicate_behavior)
        self._server_manager = server_manager
        self._database = database
        # self._fastmcp_resource_manager = fastmcp_resource_manager
        self._resource_templates: Dict[str, ResourceTemplate] = {}
        self._resources: Dict[str, Resource] = {}

    def unmount(self, server_id):
        """Unmount a member server"""
        # Find the matching mounted server and get its tools
        for idx, mounted_server in enumerate(self._mounted_servers):
            if mounted_server.prefix == server_id:
                del self._mounted_servers[idx]

    async def create_resource_template(self, resource_config: dict) -> str:
        """
        Add a resource template to the composer using FastMCP's built-in add_template.
        """
        try:
            if 'name' not in resource_config:
                return "Error: 'name' is required for resource configuration"

            uri_template = resource_config.get('uri_template') or resource_config.get('template') or f"resource://{resource_config['name']}"
            description = resource_config.get('description', '')
            mime_type = resource_config.get('mime_type', 'text/plain')
            parameters = resource_config.get('parameters', {})
            tags = set(resource_config.get('tags', []))
            enabled = resource_config.get('enabled', True)

            # If a function is provided, use from_function, else create a static template
            fn = resource_config.get('function')
            if fn:
                template = ResourceTemplate.from_function(
                    fn=fn,
                    uri_template=uri_template,
                    name=resource_config['name'],
                    description=description,
                    mime_type=mime_type,
                    tags=tags,
                    enabled=enabled,
                )
            else:
                # If 'template' is provided as a string, create a function that returns it
                template_content = resource_config.get('template')
                if template_content:
                    def template_fn(param: str = "default"):
                        return template_content

                    # Create a proper URI template with parameters for the function-based template
                    function_uri_template = f"resource://{resource_config['name']}/{{param}}"

                    template = ResourceTemplate.from_function(
                        fn=template_fn,
                        uri_template=function_uri_template,
                        name=resource_config['name'],
                        description=description,
                        mime_type=mime_type,
                        tags=tags,
                        enabled=enabled,
                    )
                else:
                    template = ResourceTemplate(
                        name=resource_config['name'],
                        description=description,
                        uri_template=uri_template,
                        mime_type=mime_type,
                        parameters=parameters,
                        tags=tags,
                        enabled=enabled,
                    )

            self.add_template(template)
            logger.info("Resource template %s added successfully", resource_config['name'])
            return f"Resource template '{resource_config['name']}' added successfully"
        except Exception as e:
            logger.error("Error adding resource template: %s", e)
            return f"Failed to add resource template: {str(e)}"

    async def create_resource(self, resource_config: dict) -> str:
        """
        Create a resource in the composer using FastMCP's built-in add_resource.
        """
        try:
            if 'name' not in resource_config:
                return "Error: 'name' is required for resource"

            uri = resource_config.get('uri', f"resource://{resource_config['name']}")
            description = resource_config.get('description', '')
            mime_type = resource_config.get('mime_type', 'text/plain')
            tags = set(resource_config.get('tags', []))
            enabled = resource_config.get('enabled', True)
            content = resource_config.get('content', '')

            # If a function is provided, use from_function, else create a static resource
            fn = resource_config.get('function')
            if fn:
                resource = Resource.from_function(
                    fn=fn,
                    uri=uri,
                    name=resource_config['name'],
                    description=description,
                    mime_type=mime_type,
                    tags=tags,
                    enabled=enabled,
                )
            else:
                # Create a simple resource with a static read method
                class StaticResource(Resource):
                    async def read(self) -> str:
                        return content

                resource = StaticResource(
                    name=resource_config['name'],
                    description=description,
                    uri=uri,
                    mime_type=mime_type,
                    tags=tags,
                    enabled=enabled,
                )

            self.add_resource(resource)
            logger.info("Resource %s created successfully", resource_config['name'])
            return f"Resource '{resource_config['name']}' created successfully"
        except Exception as e:
            logger.error("Error creating resource: %s", e)
            return f"Failed to create resource: {str(e)}"

    async def remove_resource(self, resource_name: str) -> str:
        """Remove a specific resource by name from composer or mounted servers."""
        try:
            # First try to remove from our own resources using FastMCP's _resources
            # Find resource by name and remove by URI
            for uri, resource in self._resources.items():
                if hasattr(resource, 'name') and resource.name == resource_name:
                    self._resources.pop(uri, None)
                    logger.info("Resource %s removed from composer successfully", resource_name)
                    return f"Resource '{resource_name}' removed from composer successfully"

            # Also check resource templates using FastMCP's _templates
            # Find template by name and remove by URI template
            for uri_template, template in self._templates.items():
                if hasattr(template, 'name') and template.name == resource_name:
                    self._templates.pop(uri_template, None)
                    logger.info("Resource template %s removed from composer successfully", resource_name)
                    return f"Resource template '{resource_name}' removed from composer successfully"

            # If not found in our resources, try to remove from mounted servers
            if self._server_manager:
                for server_id, member in self._server_manager._member_servers.items():
                    if member.server:
                        try:
                            # Check if the resource exists in this server
                            server_resources = await member.server.get_resource_templates()
                            for key, resource in server_resources.items():
                                if hasattr(resource, 'name') and resource.name == resource_name:
                                    # Try to remove from the server's resource manager
                                    if hasattr(member.server, '_resource_manager') and hasattr(member.server._resource_manager, '_templates'):
                                        member.server._resource_manager._templates.pop(key, None)
                                        logger.info("Resource %s removed from server %s successfully", resource_name, server_id)
                                        return f"Resource '{resource_name}' removed from server '{server_id}' successfully"
                        except Exception as e:
                            logger.warning("Error removing resource from server %s: %s", server_id, e)

            return f"Resource '{resource_name}' not found in composer or any mounted servers"
        except Exception as e:
            logger.error("Error removing resource %s: %s", resource_name, e)
            return f"Failed to remove resource '{resource_name}': {str(e)}"

    async def list_resources_per_server(self, server_id: str) -> List[Dict]:
        """List all resources from a specific server."""
        try:
            if not self._server_manager or not self._server_manager.has_member_server(server_id):
                return []

            # Get resources from the specific server
            server = self._server_manager.get_member(server_id)
            if server and hasattr(server, 'server') and server.server:
                resources = await server.server.get_resource_templates()
                result = []
                for key, resource in resources.items():
                    if hasattr(resource, 'name'):
                        result.append({
                            "name": resource.name,
                            "description": getattr(resource, 'description', ''),
                            "template": str(resource),
                            "server_id": server_id
                        })
                    else:
                        result.append({
                            "name": key,
                            "description": "",
                            "template": str(resource),
                            "server_id": server_id
                        })
                return result
            return []
        except Exception as e:
            logger.error("Error listing resources for server %s: %s", server_id, e)
            return []

    async def filter_resources(self, filter_criteria: dict) -> List[Dict]:
        """
        Filter both resources and templates based on criteria like name, description, tags, etc.
        """
        try:
            result = []

            # Get all resources and templates using FastMCP's built-in methods
            resources = await self.list_resources()
            templates = await self.list_resource_templates()

            # Combine resources and templates for filtering
            all_items = []

            # Add resources with type indicator
            for resource in resources:
                all_items.append({
                    "item": resource,
                    "type": "resource",
                    "name": getattr(resource, 'name', ''),
                    "description": getattr(resource, 'description', ''),
                    "uri": str(getattr(resource, 'uri', '')),
                    "tags": getattr(resource, 'tags', set())
                })

            # Add templates with type indicator
            for template in templates:
                all_items.append({
                    "item": template,
                    "type": "template",
                    "name": getattr(template, 'name', ''),
                    "description": getattr(template, 'description', ''),
                    "uri_template": str(getattr(template, 'uri_template', '')),
                    "tags": getattr(template, 'tags', set())
                })

            # Apply filters
            for item_data in all_items:
                match = True

                # Filter by name
                if 'name' in filter_criteria and filter_criteria['name']:
                    search_name = filter_criteria['name'].lower()
                    item_name = item_data['name'].lower()
                    if search_name not in item_name:
                        match = False

                # Filter by description
                if match and 'description' in filter_criteria and filter_criteria['description']:
                    search_desc = filter_criteria['description'].lower()
                    item_desc = item_data['description'].lower()
                    if search_desc not in item_desc:
                        match = False

                # Filter by tags
                if match and 'tags' in filter_criteria and filter_criteria['tags']:
                    search_tags = set(tag.lower() for tag in filter_criteria['tags'])
                    item_tags = set(tag.lower() for tag in item_data['tags'])
                    if not search_tags.intersection(item_tags):
                        match = False

                # Filter by type (resource or template)
                if match and 'type' in filter_criteria and filter_criteria['type']:
                    if filter_criteria['type'].lower() != item_data['type']:
                        match = False

                # Filter by URI pattern
                if match and 'uri_pattern' in filter_criteria and filter_criteria['uri_pattern']:
                    if item_data['type'] == 'resource':
                        uri = item_data['uri']
                    else:
                        uri = item_data['uri_template']

                    if filter_criteria['uri_pattern'].lower() not in uri.lower():
                        match = False

                if match:
                    # Create result entry
                    result_entry = {
                        "name": item_data['name'],
                        "description": item_data['description'],
                        "type": item_data['type'],
                        "source": "composer"  # Could be enhanced to track actual source
                    }

                    # Add type-specific fields
                    if item_data['type'] == 'resource':
                        result_entry["uri"] = item_data['uri']
                    else:
                        result_entry["uri_template"] = item_data['uri_template']

                    # Add tags if present
                    if item_data['tags']:
                        result_entry["tags"] = list(item_data['tags'])

                    result.append(result_entry)

            return result
        except Exception as e:
            logger.error("Error filtering resources: %s", e)
            return []
