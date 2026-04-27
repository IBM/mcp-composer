"""Resource management module for MCP Composer."""

from __future__ import annotations
import asyncio
import logging
from typing import TYPE_CHECKING, Any
from fastmcp.resources import Resource, ResourceTemplate
import asyncio.tasks

from mcp_composer.core.member_servers.member_server import HealthStatus
from mcp_composer.core.member_servers.server_manager import ServerManager
from mcp_composer.a2a_service.a2a_mcp import get_agent_cards, get_agent_card

logger = logging.getLogger(__name__)
# pylint: disable=W0718

if TYPE_CHECKING:
    from mcp_composer.core.composer import MCPComposer


class MCPResourceManager:
    """Custom resource manager that works with FastMCP's internal ResourceManager."""

    RESOURCE_KIND = "resource"
    TEMPLATE_KIND = "template"

    def __init__(
        self,
        composer: MCPComposer,
        server_manager: ServerManager,
        database=None,
    ):
        self._composer = composer
        self._server_manager = server_manager
        self._database = database
        # Store references to parent's dicts before we shadow them
        # Access parent's _resources and _templates from instance dict before shadowing
        instance_dict = object.__getattribute__(self, "__dict__")
        self._parent_resources = instance_dict.get("_resources", {})
        self._parent_templates = instance_dict.get("_templates", {})
        # self._fastmcp_resource_manager = fastmcp_resource_manager
        self._resource_templates: dict[str, ResourceTemplate] = {}
        self._resources: dict[str, Resource] = {}
        self._storage_enabled = database is not None
        self._restore_task: asyncio.tasks.Task[None] | None = None
        self.warn_on_duplicate_resources = True

    def schedule_persisted_restore(self) -> None:
        """Schedule restoration of persisted resources/templates."""
        if not self._storage_enabled:
            return
        try:
            loop = asyncio.get_running_loop()
            self._restore_task = loop.create_task(self.restore_persisted_resources())
        except RuntimeError:
            asyncio.run(self.restore_persisted_resources())

    async def restore_persisted_resources(self) -> None:
        """Load resources/templates from storage."""
        # Add built-in resources for agent cards
        await self.create_resource(
            {
                "function": get_agent_cards,
                "uri": "resource://agent_cards/list",
                "mime_type": "application/json",
                "description": "Retrieves a list of all agent cards.",
                "name": "get_agent_cards",
            },
            persist=False,
        )

        await self.create_resource_template(
            {
                "function": get_agent_card,
                "uri_template": "agent://agent_cards/{card_name}",
                "mime_type": "application/json",
                "description": "Retrieves a specific agent card by name.",
                "name": "get_agent_card",
            },
            persist=False,
        )

        if not self._storage_enabled or not self._database:
            return
        stored = self._database.load_all_resources()
        for record in stored:
            kind = record.get("resource_type")
            name = record.get("name")
            if not name:
                continue
            if kind == self.RESOURCE_KIND:
                if any(res.name == name for res in self._resources.values()):
                    continue
                config = {
                    "name": name,
                    "description": record.get("description", ""),
                    "uri": record.get("uri"),
                    "text": record.get("text"),
                    "mime_type": record.get("mime_type"),
                    "tags": record.get("tags", []),
                    "enabled": record.get("enabled", True),
                }
                await self.create_resource(config, persist=False)
            elif kind == self.TEMPLATE_KIND:
                if any(tmpl.name == name for tmpl in self._resource_templates.values()):
                    continue
                config = {
                    "name": name,
                    "description": record.get("description", ""),
                    "uri_template": record.get("uri_template"),
                    "text": record.get("text"),
                    "mime_type": record.get("mime_type"),
                    "tags": record.get("tags", []),
                    "enabled": record.get("enabled", True),
                }
                await self.create_resource_template(config, persist=False)

    def _storage_id(self, kind: str, name: str) -> str:
        return f"{kind}:{name}"

    def _persist_record(self, record: dict) -> None:
        if self._storage_enabled and self._database:
            self._database.upsert_resource(record)

    def _remove_persisted_record(self, storage_id: str) -> None:
        if self._storage_enabled and self._database:
            self._database.delete_resource(storage_id)

    def _resource_record(
        self,
        *,
        kind: str,
        name: str,
        description: str,
        text: str,
        uri: str | None,
        mime_type: str,
        tags: set[str],
        enabled: bool,
    ) -> dict:
        record: dict[str, Any] = {
            "storage_id": self._storage_id(kind, name),
            "resource_type": kind,
            "name": name,
            "description": description,
            "text": text or "",
            "mime_type": mime_type,
            "tags": sorted(list(tags)) if tags else [],
            "enabled": enabled,
        }
        if kind == self.RESOURCE_KIND and uri is not None:
            record["uri"] = uri
        if kind == self.TEMPLATE_KIND and uri is not None:
            record["uri_template"] = uri
        return record

    def add_resource(self, resource: Resource) -> Resource:
        """Add a resource to the manager."""
        existing = self._resources.get(resource.name)
        if existing:
            if self.warn_on_duplicate_resources:
                logger.warning("Resource already exists: %s", resource.name)
            return existing
        self._composer.add_resource(resource)  # Add to FastMCP's ResourceManager
        self._resources[resource.name] = resource

        return resource

    def add_template(self, template: ResourceTemplate) -> ResourceTemplate:
        """Add a resource template to the manager."""
        existing = self._resource_templates.get(template.name)
        if existing:
            if self.warn_on_duplicate_resources:
                logger.warning("Resource template already exists: %s", template.name)
            return existing
        self._composer.add_template(template)  # Add to FastMCP's ResourceManager
        self._resource_templates[template.name] = template
        return template

    def get_resource(self, name: str) -> Resource | None:
        """Get resource by name."""
        return self._resources.get(name)

    def get_template(self, name: str) -> ResourceTemplate | None:
        """Get resource template by name."""
        return self._resource_templates.get(name)

    def _filter_disabled_resources(
        self, resources: dict[str, Resource]
    ) -> dict[str, Resource]:
        """Filter resources by performing the following actions for a member server,
        if it exists
        1. Remove disabled resources
        2. Update description
        """
        try:
            if not self._server_manager:
                return resources

            server_config = self._server_manager.list()
            if not server_config:
                return resources

            remove_set = set()
            description_updates = {}

            for member in server_config:
                if member.health_status == HealthStatus.unhealthy:
                    continue

                if member.disabled_resources:
                    remove_set.update(member.disabled_resources)
                if member.resources_description:
                    description_updates.update(member.resources_description)

            filtered_resources = {}
            for name, resource in resources.items():
                # Check if this resource should be filtered out
                should_remove = False

                # Check exact key match first
                if name in remove_set:
                    should_remove = True
                else:
                    # Check if any disabled resource matches this resource by name
                    resource_name = getattr(resource, "name", None)
                    if resource_name:
                        for disabled_resource in remove_set:
                            # Extract the resource name from the disabled resource key
                            # Format: server_id_resource_name -> resource_name
                            if "_" in disabled_resource:
                                disabled_resource_name = disabled_resource.split(
                                    "_", 1
                                )[1]
                                if (
                                    resource_name.lower()
                                    == disabled_resource_name.lower()
                                ):
                                    should_remove = True
                                    break

                if should_remove:
                    continue

                if name in description_updates:
                    resource.description = description_updates[name]
                filtered_resources[name] = resource
            return filtered_resources
        except Exception as e:
            logger.exception("Resources filtering failed: %s", e)
            raise

    def _filter_disabled_templates(
        self, templates: dict[str, ResourceTemplate]
    ) -> dict[str, ResourceTemplate]:
        """Filter resource templates by performing the following actions for a member server,
        if it exists
        1. Remove disabled resources
        2. Update description
        """
        try:
            if not self._server_manager:
                return templates

            server_config = self._server_manager.list()
            if not server_config:
                return templates

            remove_set = set()
            description_updates = {}

            for member in server_config:
                if member.health_status == HealthStatus.unhealthy:
                    continue

                if member.disabled_resources:
                    remove_set.update(member.disabled_resources)
                if member.resources_description:
                    description_updates.update(member.resources_description)

            filtered_templates = {}
            for name, template in templates.items():
                # Check if this template should be filtered out
                should_remove = False

                # Check exact key match first
                if name in remove_set:
                    should_remove = True
                else:
                    # Check if any disabled resource matches this template by name
                    template_name = getattr(template, "name", None)
                    if template_name:
                        for disabled_resource in remove_set:
                            # Extract the resource name from the disabled resource key
                            # Format: server_id_resource_name -> resource_name
                            if "_" in disabled_resource:
                                disabled_resource_name = disabled_resource.split(
                                    "_", 1
                                )[1]
                                if (
                                    template_name.lower()
                                    == disabled_resource_name.lower()
                                ):
                                    should_remove = True
                                    break

                if should_remove:
                    continue

                if name in description_updates:
                    template.description = description_updates[name]
                filtered_templates[name] = template
            return filtered_templates
        except Exception as e:
            logger.exception("Resource templates filtering failed: %s", e)
            raise

    async def get_resources(self) -> dict[str, Resource]:
        """
        Gets the complete, unfiltered inventory of all resources and applies filtering.
        """
        return self._filter_disabled_resources(self._resources)

    async def get_resource_templates(self) -> dict[str, ResourceTemplate]:
        """
        Gets the complete, unfiltered inventory of all resource templates and applies filtering.
        """
        return self._filter_disabled_templates(self._resource_templates)

    async def list_resources(self) -> list[Resource]:
        """
        Lists all resources, applying protocol filtering and our custom disabled resource filtering.
        """
        resources_dict = await self.get_resources()
        return list(resources_dict.values())

    async def list_resource_templates(self) -> list[ResourceTemplate]:
        """
        Lists all resource templates, applying protocol filtering and our custom disabled resource filtering.
        """
        templates_dict = await self.get_resource_templates()
        return list(templates_dict.values())

    async def disable_resources(self, resources: list[str], server_id: str) -> str:
        """
        Disable a resource or multiple resources from the member server.
        This method handles both Resources and Resource Templates.
        """
        if not self._server_manager:
            return "Server manager not available"

        try:
            self._server_manager.check_server_exist(server_id)

            # Get all resources and templates using the list methods
            all_resources = await self.list_resources()
            all_templates = await self.list_resource_templates()

            # Find resources to disable by matching names
            resources_to_disable = []

            for resource_name in resources:
                # Check in resources
                for resource in all_resources:
                    actual_name = getattr(resource, "name", None)
                    if actual_name and resource_name.lower() == actual_name.lower():
                        # Find the corresponding key in the resources dictionary
                        resources_dict = await self.get_resources()
                        for _, res in resources_dict.items():
                            if res == resource:
                                full_key = f"{server_id}_{resource_name}"
                                resources_to_disable.append(full_key)
                                break
                        break

                # Check in templates
                for template in all_templates:
                    actual_name = getattr(template, "name", None)
                    if actual_name and resource_name.lower() == actual_name.lower():
                        # Find the corresponding key in the templates dictionary
                        templates_dict = await self.get_resource_templates()
                        for _, temp in templates_dict.items():
                            if temp == template:
                                full_key = f"{server_id}_{resource_name}"
                                resources_to_disable.append(full_key)
                                break
                        break

            if not resources_to_disable:
                return (
                    f"No resources or resource templates found to disable: {resources}"
                )

            self._server_manager.disable_resources(resources_to_disable, server_id)
            logger.info(
                "Disabled %s resources/templates from server", resources_to_disable
            )
            return f"Disabled {resources_to_disable} resources/templates from server {server_id}"
        except Exception as e:
            logger.error("Error disabling resources: %s", e)
            return f"Failed to disable resources: {str(e)}"

    async def enable_resources(self, resources: list[str], server_id: str) -> str:
        """
        Enable a resource or multiple resources from the member server.
        This method handles both Resources and Resource Templates.
        """
        if not self._server_manager:
            return "Server manager not available"

        try:
            self._server_manager.check_server_exist(server_id)

            # Get all resources and templates (unfiltered)
            all_resources = self._resources
            all_templates = self._resource_templates

            # Find resources to enable by matching names
            resources_to_enable = []

            for resource_name in resources:
                # Check in resources
                for _, resource in all_resources.items():
                    actual_name = getattr(resource, "name", None)
                    if actual_name and resource_name.lower() == actual_name.lower():
                        full_key = f"{server_id}_{resource_name}"
                        resources_to_enable.append(full_key)
                        break

                # Check in templates
                for _, template in all_templates.items():
                    actual_name = getattr(template, "name", None)
                    if actual_name and resource_name.lower() == actual_name.lower():
                        full_key = f"{server_id}_{resource_name}"
                        resources_to_enable.append(full_key)
                        break

            if not resources_to_enable:
                return (
                    f"No resources or resource templates found to enable: {resources}"
                )

            self._server_manager.enable_resources(resources_to_enable, server_id)
            logger.info(
                "Enabled %s resources/templates from server", resources_to_enable
            )
            return f"Enabled {resources_to_enable} resources/templates from server {server_id}"
        except Exception as e:
            logger.error("Error enabling resources: %s", e)
            return f"Failed to enable resources: {str(e)}"

    async def create_resource_template(
        self, resource_config: dict, persist: bool = True
    ) -> str:
        """
        Add a resource template to the composer using FastMCP's built-in add_template.
        """
        try:
            if "name" not in resource_config:
                return "Error: 'name' is required for resource configuration"

            uri_template = (
                resource_config.get("uri_template")
                or resource_config.get("template")
                or f"resource://{resource_config['name']}"
            )
            description = resource_config.get("description", "")
            mime_type = resource_config.get("mime_type", "text/plain")
            parameters = resource_config.get("parameters", {})
            tags = set(resource_config.get("tags", []))
            enabled = resource_config.get("enabled", True)
            template_text = resource_config.get("text")
            if template_text is None:
                template_text = resource_config.get("template", "")

            # If a function is provided, use from_function, else create a static template
            fn = resource_config.get("function")
            template: ResourceTemplate | Any
            if fn:
                template = ResourceTemplate.from_function(
                    fn=fn,
                    uri_template=uri_template,
                    name=resource_config["name"],
                    description=description,
                    mime_type=mime_type,
                    tags=tags,
                )
            else:
                # If 'template' is provided as a string, create a function that returns it
                template_content = template_text
                if template_content is not None:

                    def template_fn(param: str = "default"):
                        return template_content

                    # Create a proper URI template with parameters for the function-based template
                    function_uri_template = (
                        f"resource://{resource_config['name']}/{{param}}"
                    )

                    template = ResourceTemplate.from_function(
                        fn=template_fn,
                        uri_template=function_uri_template,
                        name=resource_config["name"],
                        description=description,
                        mime_type=mime_type,
                        tags=tags,
                    )
                else:
                    template = ResourceTemplate(
                        name=resource_config["name"],
                        description=description,
                        uri_template=uri_template,
                        mime_type=mime_type,
                        parameters=parameters,
                        tags=tags,
                    )

            if template_text is not None:
                setattr(template, "_composer_text", template_text)

            self.add_template(template)
            if persist and not fn:
                record = self._resource_record(
                    kind=self.TEMPLATE_KIND,
                    name=resource_config["name"],
                    description=description,
                    text=template_text or "",
                    uri=uri_template,
                    mime_type=mime_type,
                    tags=tags,
                    enabled=enabled,
                )
                self._persist_record(record)
            logger.info(
                "Resource template %s added successfully", resource_config["name"]
            )
            return f"Resource template '{resource_config['name']}' added successfully"
        except Exception as e:
            logger.error("Error adding resource template: %s", e)
            return f"Failed to add resource template: {str(e)}"

    async def create_resource(self, resource_config: dict, persist: bool = True) -> str:
        """
        Create a resource in the composer using FastMCP's built-in add_resource.
        """
        try:
            if "name" not in resource_config:
                return "Error: 'name' is required for resource"
            if "uri" not in resource_config:
                return "Error: 'uri' is required for resource"

            uri = resource_config.get("uri", f"resource://{resource_config['name']}")
            description = resource_config.get("description", "")
            mime_type = resource_config.get("mime_type", "text/plain")
            tags = set(resource_config.get("tags", []))
            enabled = resource_config.get("enabled", True)
            content = resource_config.get("text")
            if content is None:
                content = resource_config.get("content", "")

            # If a function is provided, use from_function, else create a static resource
            fn = resource_config.get("function")
            resource: Resource | Any
            if fn:
                resource = Resource.from_function(
                    fn=fn,
                    uri=uri,
                    name=resource_config["name"],
                    description=description,
                    mime_type=mime_type,
                    tags=tags,
                )
            else:
                # Create a simple resource with a static read method
                class StaticResource(Resource):
                    def __init__(self, *, text: str, **kwargs):
                        super().__init__(**kwargs)
                        self._composer_text = text

                    async def read(self) -> str:
                        return self._composer_text

                resource = StaticResource(
                    name=resource_config["name"],
                    description=description,
                    uri=uri,
                    mime_type=mime_type,
                    tags=tags,
                    text=content,
                )

            self.add_resource(resource)
            if persist and not fn:
                record = self._resource_record(
                    kind=self.RESOURCE_KIND,
                    name=resource_config["name"],
                    description=description,
                    text=content or "",
                    uri=str(uri),
                    mime_type=mime_type,
                    tags=tags,
                    enabled=enabled,
                )
                self._persist_record(record)
            logger.info("Resource %s created successfully", resource_config["name"])
            return f"Resource '{resource_config['name']}' created successfully"
        except Exception as e:
            logger.error("Error creating resource: %s", e)
            return f"Failed to create resource: {str(e)}"

    async def delete_resources(
        self, resource_names: list[str], resource_type: str | None = None
    ) -> str:
        """Delete stored resources or templates."""
        if not resource_names:
            return "No resource names provided"

        targets = {name.lower() for name in resource_names}
        removed: list[str] = []

        # Delete from _resources dict
        if resource_type in (None, self.RESOURCE_KIND):
            for key, resource in list(self._resources.items()):
                if hasattr(resource, "name") and resource.name.lower() in targets:
                    removed.append(resource.name)
                    del self._resources[key]
                    self._remove_persisted_record(
                        self._storage_id(self.RESOURCE_KIND, resource.name)
                    )

        # Delete from _resource_templates dict
        if resource_type in (None, self.TEMPLATE_KIND):
            for key, template in list(self._resource_templates.items()):
                if hasattr(template, "name") and template.name.lower() in targets:
                    removed.append(template.name)
                    del self._resource_templates[key]
                    self._remove_persisted_record(
                        self._storage_id(self.TEMPLATE_KIND, template.name)
                    )

        if not removed:
            return "No matching resources or templates found to delete"

        return f"Deleted resources/templates: {', '.join(sorted(set(removed)))}"

    async def list_resources_per_server(
        self, server_id: str
    ) -> list[dict[str, object]]:
        """List all resources from a specific server."""
        try:
            if not self._server_manager or not self._server_manager.has_member_server(
                server_id
            ):
                return []

            # Get resources from the specific server
            server = self._server_manager.get_member(server_id)
            if server and hasattr(server, "server") and server.server:
                result = []
                try:
                    # Get resources from our internal dict that belong to this server
                    for key, resource in self._resources.items():
                        if key.startswith(f"{server_id}_"):
                            if hasattr(resource, "name"):
                                result.append(
                                    {
                                        "name": resource.name,
                                        "description": getattr(
                                            resource, "description", ""
                                        ),
                                        "uri": str(getattr(resource, "uri", "")),
                                        "type": "resource",
                                        "server_id": server_id,
                                    }
                                )
                            else:
                                result.append(
                                    {
                                        "name": key,
                                        "description": "",
                                        "uri": str(resource),
                                        "type": "resource",
                                        "server_id": server_id,
                                    }
                                )
                except Exception as e:
                    logger.warning(
                        "Error getting resources from server %s: %s", server_id, e
                    )
                try:
                    # Get templates from our internal dict that belong to this server
                    for key, template in self._resource_templates.items():
                        if key.startswith(f"{server_id}_"):
                            if hasattr(template, "name"):
                                result.append(
                                    {
                                        "name": template.name,
                                        "description": getattr(
                                            template, "description", ""
                                        ),
                                        "uri_template": str(
                                            getattr(template, "uri_template", "")
                                        ),
                                        "type": "template",
                                        "server_id": server_id,
                                    }
                                )
                            else:
                                result.append(
                                    {
                                        "name": key,
                                        "description": "",
                                        "uri_template": str(template),
                                        "type": "template",
                                        "server_id": server_id,
                                    }
                                )
                except Exception as e:
                    logger.warning(
                        "Error getting resource templates from server %s: %s",
                        server_id,
                        e,
                    )
                return result
            return []
        except Exception as e:
            logger.error("Error listing resources for server %s: %s", server_id, e)
            return []

    async def filter_resources(self, filter_criteria: dict) -> list[dict[str, object]]:
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
                # Handle both Resource objects and dict-like objects
                resource_data: dict[str, Any]
                if isinstance(resource, dict):
                    resource_data = {
                        "item": resource,
                        "type": "resource",
                        "name": resource.get("name", ""),
                        "description": resource.get("description", ""),
                        "uri": str(resource.get("uri", "")),
                        "tags": resource.get("tags", set()),
                    }
                else:
                    resource_data = {
                        "item": resource,
                        "type": "resource",
                        "name": getattr(resource, "name", ""),
                        "description": getattr(resource, "description", ""),
                        "uri": str(getattr(resource, "uri", "")),
                        "tags": getattr(resource, "tags", set()),
                    }
                all_items.append(resource_data)

            # Add templates with type indicator
            for template in templates:
                # Handle both ResourceTemplate objects and dict-like objects
                template_data: dict[str, Any]
                if isinstance(template, dict):
                    template_data = {
                        "item": template,
                        "type": "template",
                        "name": template.get("name", ""),
                        "description": template.get("description", ""),
                        "uri_template": str(template.get("uri_template", "")),
                        "tags": template.get("tags", set()),
                    }
                else:
                    template_data = {
                        "item": template,
                        "type": "template",
                        "name": getattr(template, "name", ""),
                        "description": getattr(template, "description", ""),
                        "uri_template": str(getattr(template, "uri_template", "")),
                        "tags": getattr(template, "tags", set()),
                    }
                all_items.append(template_data)

            # Apply filters
            for item_data in all_items:
                match = True

                # Filter by name
                if "name" in filter_criteria and filter_criteria["name"]:
                    search_name = filter_criteria["name"].lower()
                    item_name = str(item_data["name"]).lower()
                    if search_name not in item_name:
                        match = False

                # Filter by description
                if (
                    match
                    and "description" in filter_criteria
                    and filter_criteria["description"]
                ):
                    search_desc = filter_criteria["description"].lower()
                    item_desc = str(item_data["description"]).lower()
                    if search_desc not in item_desc:
                        match = False

                # Filter by tags
                if match and "tags" in filter_criteria and filter_criteria["tags"]:
                    search_tags = set(tag.lower() for tag in filter_criteria["tags"])
                    item_tags = set(str(tag).lower() for tag in item_data["tags"])
                    if not search_tags.intersection(item_tags):
                        match = False

                # Filter by type (resource or template)
                if match and "type" in filter_criteria and filter_criteria["type"]:
                    if filter_criteria["type"].lower() != item_data["type"]:
                        match = False

                # Filter by URI pattern
                if (
                    match
                    and "uri_pattern" in filter_criteria
                    and filter_criteria["uri_pattern"]
                ):
                    if item_data["type"] == "resource":
                        uri = item_data.get("uri", "")
                    else:
                        uri = item_data.get("uri_template", "")

                    if (
                        uri
                        and filter_criteria["uri_pattern"].lower()
                        not in str(uri).lower()
                    ):
                        match = False

                if match:
                    # Create result entry
                    result_entry = {
                        "name": item_data["name"],
                        "description": item_data["description"],
                        "type": item_data["type"],
                        "source": "composer",  # Could be enhanced to track actual source
                    }

                    # Add type-specific fields
                    if item_data["type"] == "resource":
                        result_entry["uri"] = item_data.get("uri", "")
                    else:
                        result_entry["uri_template"] = item_data.get("uri_template", "")

                    # Add tags if present
                    if item_data.get("tags"):
                        result_entry["tags"] = list(item_data["tags"])

                    result.append(result_entry)

            return result
        except Exception as e:
            logger.error("Error filtering resources: %s", e)
            return []
