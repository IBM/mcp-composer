# base_tool_example.py
"""
Example showing how to create a new tool using BaseMCPTool.

This is a reference implementation - not meant to be executed directly.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field

from fastmcp.tools import ToolResult

from mcp_composer.core.tools.base_tool import BaseMCPTool
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


# Step 1: Define your input model (optional, but recommended)
class MyToolInput(BaseModel):
    """Input parameters for My Tool"""

    query: str = Field(description="The query to process", min_length=1)

    max_results: int = Field(
        default=5, ge=1, le=10, description="Maximum number of results"
    )


# Step 2: Create your tool class inheriting from BaseMCPTool
class MyNewTool(BaseMCPTool):
    """
    Example tool demonstrating BaseMCPTool usage.

    This tool shows how to:
    - Inherit from BaseMCPTool
    - Use common initialization patterns
    - Leverage built-in error handling
    - Return standardized responses
    """

    def __init__(self, config: Optional[dict] = None):
        """Initialize the tool"""

        # Option A: Use Pydantic model for parameters
        parameters = MyToolInput.model_json_schema()

        # Option B: Define parameters manually
        # parameters = {
        #     "type": "object",
        #     "properties": {
        #         "query": {
        #             "type": "string",
        #             "description": "The query to process"
        #         }
        #     },
        #     "required": ["query"]
        # }

        description = """
        This is my new tool that does something useful.
        
        It demonstrates how to use BaseMCPTool for creating
        consistent, well-structured tools.
        """

        # Get tool name from config (handled by base class)
        tool_name = self._get_tool_name(config, default="my_new_tool")

        # Initialize parent class
        super().__init__(
            name=tool_name,
            description=description,
            parameters=parameters,
        )

        # Initialize any private attributes you need
        # (e.g., session management, resource managers, etc.)

        logger.info(f"MyNewTool '{tool_name}' initialized")

    async def run(self, arguments: dict[str, Any]) -> ToolResult:
        """
        Execute the tool.

        Args:
            arguments: Tool arguments

        Returns:
            ToolResult with response
        """
        try:
            # Normalize arguments (converts camelCase to snake_case)
            normalized_args = self._normalize_arguments(arguments)

            # Option A: Validate with Pydantic
            from pydantic import ValidationError

            try:
                params = MyToolInput(**normalized_args)
            except ValidationError as e:
                return self._handle_validation_error(e, arguments)

            # Option B: Manual validation
            # if "query" not in normalized_args:
            #     raise ValueError("Missing required parameter: query")

            # Your tool logic here
            query = params.query
            max_results = params.max_results

            # Process the query
            results = await self._process_query(query, max_results)

            # Create success response
            response = {
                "status": "success",
                "query": query,
                "results": results,
                "count": len(results),
            }

            return self._create_success_response(response)

        except Exception as e:
            # Handle unexpected errors (built-in method)
            return self._handle_unexpected_error(e, arguments)

    async def _process_query(self, query: str, max_results: int) -> list:
        """Your tool's business logic"""
        # Implement your tool's functionality here
        return [f"Result for: {query}"]
