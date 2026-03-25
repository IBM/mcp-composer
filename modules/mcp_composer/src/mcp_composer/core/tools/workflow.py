# workflow.py

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

from fastmcp.tools import Tool
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent

from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


class StoreWorkflowConfigTool(Tool):
    """
    Tool to store workflow configuration as JSON.

    This tool accepts a workflow name and JSON configuration, then stores
    the configuration in the src/mcp_composer directory under the workflow name.
    """

    def __init__(self, config: Optional[dict] = None):
        """Initialize the Store Workflow Config Tool"""

        parameters = {
            "type": "object",
            "properties": {
                "workflow_name": {
                    "type": "string",
                    "description": "The name of the workflow to store the configuration for",
                    "minLength": 1,
                    "maxLength": 255,
                    "pattern": "^[a-zA-Z0-9_-]+$",
                    "examples": [
                        "data_processing_workflow",
                        "user_onboarding_flow",
                        "report_generation",
                    ],
                },
                "config": {
                    "type": "string",
                    "description": "The JSON configuration to store for the workflow",
                    "examples": [
                        '{"steps": [{"name": "extract", "type": "api_call"}, {"name": "transform", "type": "data_processing"}]}',
                        '{"version": "1.0", "description": "User onboarding workflow", "steps": []}',
                    ],
                },
            },
            "required": ["workflow_name", "config"],
            "additionalProperties": False,
        }

        description = """Store workflow configuration as JSON.

This tool stores a JSON configuration for a workflow under the specified workflow name.
The configuration is saved in the src/mcp_composer directory and can be retrieved later
using the workflow name.

Parameters:
- workflow_name: A unique identifier for the workflow (alphanumeric, underscores, hyphens only)
- config: A valid JSON string containing the workflow configuration

The configuration will be stored as {workflow_name}.json in the src/mcp_composer directory."""

        tool_name = "store_workflow_config"
        if config and "name" in config:
            tool_name = config["name"]

        super().__init__(
            name=tool_name,
            description=description,
            parameters=parameters,
        )

        logger.info("Store Workflow Config Tool '%s' initialized", tool_name)

    async def run(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Store workflow configuration.

        Args:
            arguments: Tool arguments containing workflow_name and config

        Returns:
            ToolResult: Success or error message
        """
        try:
            workflow_name = arguments["workflow_name"]
            config_str = arguments["config"]

            # Validate JSON format
            try:
                config_json = json.loads(config_str)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON format: {str(e)}"
                logger.error(
                    "JSON validation failed for workflow '%s': %s",
                    workflow_name,
                    error_msg,
                )
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "success": False,
                                    "error": error_msg,
                                    "workflow_name": workflow_name,
                                },
                                indent=2,
                            ),
                        )
                    ]
                )

            # Get the storage directory
            storage_dir = Path(__file__).parent.parent  # src/mcp_composer
            storage_dir.mkdir(exist_ok=True)

            # Create the file path
            file_path = storage_dir / f"{workflow_name}.json"

            # Write the configuration to file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config_json, f, indent=2, ensure_ascii=False)

            logger.info(
                "Stored workflow configuration for '%s' at %s", workflow_name, file_path
            )

            return ToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": True,
                                "message": f"Workflow configuration stored successfully for '{workflow_name}'",
                                "workflow_name": workflow_name,
                                "file_path": str(file_path),
                            },
                            indent=2,
                        ),
                    )
                ]
            )

        except Exception as e:
            logger.error("Error storing workflow configuration: %s", e)
            return ToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": False,
                                "error": f"An unexpected error occurred: {str(e)}",
                                "workflow_name": arguments.get(
                                    "workflow_name", "unknown"
                                ),
                            },
                            indent=2,
                        ),
                    )
                ]
            )


class GetWorkflowConfigTool(Tool):
    """
    Tool to retrieve workflow configuration from JSON file.

    This tool accepts a workflow name and retrieves the stored JSON configuration
    from the src/mcp_composer directory.
    """

    def __init__(self, config: Optional[dict] = None):
        """Initialize the Get Workflow Config Tool"""

        parameters = {
            "type": "object",
            "properties": {
                "workflow_name": {
                    "type": "string",
                    "description": "The name of the workflow to retrieve the configuration for",
                    "minLength": 1,
                    "maxLength": 255,
                    "pattern": "^[a-zA-Z0-9_-]+$",
                    "examples": [
                        "data_processing_workflow",
                        "user_onboarding_flow",
                        "report_generation",
                    ],
                },
            },
            "required": ["workflow_name"],
            "additionalProperties": False,
        }

        description = """Retrieve and execute workflow configuration from JSON file.

This tool retrieves a previously stored JSON configuration for a workflow by its name.
Use this to:
- Execute workflows (e.g., "execute the GaurdiumService workflow")
- View workflow steps and configurations
- Access stored workflow definitions like GaurdiumService, EventBrite, or custom workflows

Common workflow names:
- GaurdiumService: IBM Guardium Data Security Center workflow for authentication and asset filtering
- EventBrite: Event booking and ticket management workflow
- Custom workflows stored via store_workflow_config

Parameters:
- workflow_name: The name of the workflow to execute or retrieve (e.g., "GaurdiumService")

When a user asks to "execute a workflow" or "run the [name] workflow", use this tool to retrieve
the workflow configuration, then follow the steps defined in the returned JSON."""

        tool_name = "get_workflow_config"
        if config and "name" in config:
            tool_name = config["name"]

        super().__init__(
            name=tool_name,
            description=description,
            parameters=parameters,
        )

        logger.info("Get Workflow Config Tool '%s' initialized", tool_name)

    async def run(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Retrieve workflow configuration.

        Args:
            arguments: Tool arguments containing workflow_name

        Returns:
            ToolResult: The stored configuration or error message
        """
        try:
            workflow_name = arguments["workflow_name"]

            # Get the storage directory
            storage_dir = Path(__file__).parent.parent  # src/mcp_composer

            # Create the file path
            file_path = storage_dir / f"{workflow_name}.json"

            # Check if file exists
            if not file_path.exists():
                error_msg = f"Workflow configuration not found for '{workflow_name}'"
                logger.warning(error_msg)
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "success": False,
                                    "error": error_msg,
                                    "workflow_name": workflow_name,
                                },
                                indent=2,
                            ),
                        )
                    ]
                )

            # Read the configuration from file
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    config_json = json.load(f)
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in stored configuration: {str(e)}"
                logger.error(
                    "JSON parsing failed for workflow '%s': %s",
                    workflow_name,
                    error_msg,
                )
                return ToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "success": False,
                                    "error": error_msg,
                                    "workflow_name": workflow_name,
                                },
                                indent=2,
                            ),
                        )
                    ]
                )

            logger.info("Retrieved workflow configuration for '%s'", workflow_name)

            return ToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": True,
                                "workflow_name": workflow_name,
                                "config": config_json,
                                "file_path": str(file_path),
                            },
                            indent=2,
                        ),
                    )
                ]
            )

        except Exception as e:
            logger.error("Error retrieving workflow configuration: %s", e)
            return ToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "success": False,
                                "error": f"An unexpected error occurred: {str(e)}",
                                "workflow_name": arguments.get(
                                    "workflow_name", "unknown"
                                ),
                            },
                            indent=2,
                        ),
                    )
                ]
            )


# Export the tools for use in the MCP server
__all__ = ["StoreWorkflowConfigTool", "GetWorkflowConfigTool"]
