# base_specialised_tool.py

"""
Base class for specialized MCP Composer tools that share common patterns.

This base class provides:
- Runtime patching support for testing
- Common initialization patterns
- Standardized error handling
- JSON response formatting
- Prompt/thinking conversion utilities
- Tool filtering and mapping

This is a generic base class with NO dependencies on model providers or model mesh functionality.
Model-specific functionality should be implemented in specialized tool classes (e.g., ModelMeshTool).

Future specialized tools can inherit from this class to get these features automatically.
"""

import json
from typing import Dict, Any, Optional, List

from fastmcp.tools import Tool
from fastmcp.tools.tool import ToolResult
from mcp.types import TextContent
from pydantic import ConfigDict, ValidationError, PrivateAttr

from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


class BaseSpecializedTool(Tool):
    """
    Base class for specialized MCP Composer tools with common patterns.
    
    This is a GENERIC base class with NO dependencies on model providers or model mesh.
    It focuses on prompt/thinking conversion and tool orchestration.
    
    This class provides:
    1. Runtime patching support for testing (via __setattr__/__delattr__)
    2. Common initialization patterns with config support
    3. Standardized error handling and response formatting
    4. JSON response structure with metadata:
       - System prompt (from tool description) - included by default
       - Guardrails (customizable constraints) - included by default
       - Possible tools (filtered using composer's filter_tool functionality) - optional, only if requested
    5. Prompt/thinking conversion utilities
    6. Argument normalization (camelCase to snake_case)
    
    Usage:
        class MyTool(BaseSpecializedTool):
            def __init__(self, config: Optional[dict] = None):
                # Define your parameters and description
                parameters = {...}
                description = "..."  # This becomes the system prompt
                
                # Get tool name from config
                tool_name = self._get_tool_name(config, default="my_tool")
                
                # Initialize parent (pass config to enable composer integration)
                super().__init__(
                    name=tool_name,
                    description=description,
                    parameters=parameters,
                    config=config  # May contain 'composer' reference
                )
                
            def _get_guardrails(self) -> List[str]:
                # Override to provide custom guardrails
                return ["Custom guardrail 1", "Custom guardrail 2"]
                
            async def run(self, arguments: Dict[str, Any]) -> ToolResult:
                try:
                    # Your tool logic here
                    response = {"status": "success", ...}
                    # Extract task for tool filtering (if tool mapping is requested)
                    task = arguments.get("task") or arguments.get("mainTask")
                    # Check if tool mapping is requested (optional parameter)
                    include_tool_mapping = arguments.get("include_tool_mapping", False) or arguments.get("includeToolMapping", False)
                    # Response will include system_prompt and guardrails by default
                    # possible_tools only if include_tool_mapping=True
                    return await self._create_success_response(
                        response, 
                        include_tool_mapping=include_tool_mapping,
                        task=task if include_tool_mapping else None
                    )
                except ValidationError as e:
                    return self._handle_validation_error(e, arguments)
                except Exception as e:
                    return self._handle_unexpected_error(e, arguments)
    """

    # Pydantic model configuration (not related to AI models)
    # This allows extra fields in tool configuration
    model_config = ConfigDict(extra="allow")

    # Private attributes for composer integration
    _composer: Optional[Any] = PrivateAttr(default=None)

    def __init__(self, name: str, description: str, parameters: Dict[str, Any], config: Optional[dict] = None, **kwargs):
        """
        Initialize the base specialized tool.
        
        Args:
            name: Tool name
            description: Tool description (used as system prompt)
            parameters: Tool parameters schema
            config: Optional configuration dictionary that may contain 'composer' reference
            **kwargs: Additional arguments passed to parent Tool class
        """
        super().__init__(name=name, description=description, parameters=parameters, **kwargs)
        
        # Initialize composer reference from config if provided
        if config:
            potential_composer = None
            if isinstance(config, dict):
                potential_composer = config.get("composer")
            elif hasattr(config, "composer"):
                potential_composer = getattr(config, "composer")
            
            if potential_composer is not None:
                self._composer = potential_composer
                logger.debug(f"BaseSpecializedTool '{name}' configured with composer integration")

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Allow runtime patching of callable attributes (e.g., during testing) while
        delegating standard field assignment back to the Pydantic base implementation.
        
        This enables tools to be patched for testing without triggering Pydantic's
        attribute restrictions.
        """
        if hasattr(type(self), name) and callable(getattr(type(self), name)):
            object.__setattr__(self, name, value)
            return
        super().__setattr__(name, value)

    def __delattr__(self, name: str) -> None:
        """
        Mirror __setattr__ override so patched callables can be removed without
        triggering Pydantic's attribute restrictions.
        """
        if name in self.__dict__:
            object.__delattr__(self, name)
            return
        if hasattr(type(self), name) and callable(getattr(type(self), name)):
            # Nothing to delete: the class attribute remains intact
            return
        super().__delattr__(name)

    def _get_tool_name(self, config: Optional[dict], default: str) -> str:
        """
        Extract tool name from config with fallback to default.
        
        Args:
            config: Tool configuration dictionary
            default: Default tool name if not found in config
            
        Returns:
            Tool name string
        """
        if config and "name" in config:
            return config["name"]
        elif config and "id" in config:
            return config["id"]
        return default

    def _get_system_prompt(self) -> str:
        """
        Get the system prompt from the tool description.
        
        Returns:
            System prompt string (tool description)
        """
        return self.description or ""

    def _get_guardrails(self) -> List[str]:
        """
        Get guardrails/constraints for the tool.
        Subclasses can override this method to provide custom guardrails.
        
        Returns:
            List of guardrail strings
        """
        # Default guardrails - subclasses can override
        return [
            "Always validate input parameters before processing",
            "Handle errors gracefully and provide meaningful error messages",
            "Ensure responses are properly formatted and structured",
            "Respect rate limits and resource constraints"
        ]

    async def _get_possible_tools(self, task: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get possible/relevant tools using filter_tool functionality from composer.
        
        Args:
            task: Optional task/keyword to filter tools by. If None, returns all available tools.
            
        Returns:
            List of tool dictionaries with name and description
        """
        if not self._composer:
            logger.debug("No composer reference available, cannot filter tools")
            return []

        try:
            if task:
                # Use filter_tool_by_keyword to find relevant tools
                if hasattr(self._composer, '_tool_manager'):
                    filtered_tools = await self._composer._tool_manager.filter_tool_by_keyword(task)
                    return [
                        {
                            "name": tool.name,
                            "description": tool.description or ""
                        }
                        for tool in filtered_tools.values()
                    ]
            else:
                # Get all available tools
                if hasattr(self._composer, '_tool_manager'):
                    all_tools = self._composer._tool_manager.filter_tools(
                        await self._composer._tool_manager.get_tools()
                    )
                    return [
                        {
                            "name": tool.name,
                            "description": tool.description or ""
                        }
                        for tool in all_tools.values()
                    ]
        except Exception as e:
            logger.warning(f"Failed to get possible tools: {e}")
            return []

        return []

    async def _create_success_response(
        self, 
        response_data: Dict[str, Any],
        include_metadata: bool = True,
        include_tool_mapping: bool = False,
        task: Optional[str] = None
    ) -> ToolResult:
        """
        Create a standardized success response with JSON formatting.
        Includes system prompt, guardrails, and optionally possible tools if requested.
        
        Args:
            response_data: Dictionary containing response data
            include_metadata: Whether to include system prompt and guardrails
            include_tool_mapping: Whether to include possible tools mapping (optional, defaults to False)
            task: Optional task/keyword for filtering possible tools (only used if include_tool_mapping=True)
            
        Returns:
            ToolResult with JSON-formatted text content
        """
        if include_metadata:
            # Add system prompt and guardrails
            response_data["system_prompt"] = self._get_system_prompt()
            response_data["guardrails"] = self._get_guardrails()
        
        # Only include tool mapping if explicitly requested
        if include_tool_mapping:
            response_data["possible_tools"] = await self._get_possible_tools(task)
        
        return ToolResult(
            content=[TextContent(type="text", text=json.dumps(response_data, indent=2))]
        )

    def _create_error_response(
        self,
        error_data: Dict[str, Any],
        arguments: Dict[str, Any]
    ) -> ToolResult:
        """
        Create a standardized error response with JSON formatting.
        
        Args:
            error_data: Dictionary containing error information
            arguments: Original arguments that caused the error (for context)
            
        Returns:
            ToolResult with JSON-formatted error response
        """
        return ToolResult(
            content=[TextContent(type="text", text=json.dumps(error_data, indent=2))]
        )

    def _handle_validation_error(
        self,
        error: ValidationError,
        arguments: Dict[str, Any],
        default_task_key: str = "task"
    ) -> ToolResult:
        """
        Handle Pydantic validation errors gracefully.
        
        Args:
            error: Pydantic validation error
            arguments: Original arguments that failed validation
            default_task_key: Key to extract task/context from arguments
            
        Returns:
            ToolResult with validation error information
        """
        logger.error(f"Validation error in {self.name}: {error}")

        # Try to extract context from raw arguments (common patterns)
        context = (
            arguments.get(default_task_key) or
            arguments.get(default_task_key.capitalize()) or
            arguments.get("mainTask") or
            arguments.get("main_task") or
            arguments.get("task") or
            arguments.get("mainQuestion") or
            arguments.get("main_question") or
            arguments.get("question") or
            arguments.get("search_query") or
            arguments.get("searchQuery") or
            arguments.get("thought") or
            "Unknown"
        )

        if isinstance(context, str):
            context = context.strip()

        error_response = {
            "stage": "error",
            "status": "validation_error",
            "error": str(error),
            "validation_errors": error.errors(),
            "context": context
        }

        return self._create_error_response(error_response, arguments)

    def _handle_unexpected_error(
        self,
        error: Exception,
        arguments: Dict[str, Any],
        default_task_key: str = "task"
    ) -> ToolResult:
        """
        Handle unexpected errors gracefully.
        
        Args:
            error: Unexpected exception
            arguments: Original arguments that caused the error
            default_task_key: Key to extract task/context from arguments
            
        Returns:
            ToolResult with error information
        """
        logger.error(f"Unexpected error in {self.name}: {error}")

        # Try to extract context from raw arguments (common patterns)
        context = (
            arguments.get(default_task_key) or
            arguments.get(default_task_key.capitalize()) or
            arguments.get("mainTask") or
            arguments.get("main_task") or
            arguments.get("task") or
            arguments.get("mainQuestion") or
            arguments.get("main_question") or
            arguments.get("question") or
            arguments.get("search_query") or
            arguments.get("searchQuery") or
            arguments.get("thought") or
            "Unknown"
        )

        if isinstance(context, str):
            context = context.strip()

        error_response = {
            "stage": "error",
            "status": "failed",
            "error": str(error),
            "error_type": type(error).__name__,
            "context": context
        }

        return self._create_error_response(error_response, arguments)

    def _normalize_arguments(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize arguments by converting common camelCase to snake_case.
        
        Common conversions:
        - mainTask -> task
        - mainQuestion -> question (backward compatibility)
        - subTasks -> sub_tasks
        - subQuestions -> sub_questions (backward compatibility)
        - searchQuery -> search_query
        - sourcesCount -> sources_count
        - maxResults -> max_results
        - additionalContext -> additional_context
        - nextThoughtNeeded -> next_thought_needed
        - thoughtNumber -> thought_number
        - totalThoughts -> total_thoughts
        - isRevision -> is_revision
        - revisesThought -> revises_thought
        - branchFromThought -> branch_from_thought
        - branchId -> branch_id
        - needsMoreThoughts -> needs_more_thoughts
        - userId -> user_id
        
        Args:
            arguments: Raw arguments dictionary
            
        Returns:
            Normalized arguments dictionary
        """
        normalized = {}
        camel_to_snake = {
            "mainTask": "task",
            "mainQuestion": "question",  # backward compatibility
            "subTasks": "sub_tasks",
            "subQuestions": "sub_questions",  # backward compatibility
            "searchQuery": "search_query",
            "sourcesCount": "sources_count",
            "maxResults": "max_results",
            "additionalContext": "additional_context",
            "nextThoughtNeeded": "next_thought_needed",
            "thoughtNumber": "thought_number",
            "totalThoughts": "total_thoughts",
            "isRevision": "is_revision",
            "revisesThought": "revises_thought",
            "branchFromThought": "branch_from_thought",
            "branchId": "branch_id",
            "needsMoreThoughts": "needs_more_thoughts",
            "userId": "user_id",
        }

        for key, value in arguments.items():
            if key in camel_to_snake:
                normalized[camel_to_snake[key]] = value
            else:
                normalized[key] = value

        return normalized

