"""FastAPI app to expose MCPComposer tools as REST endpoints."""
from contextlib import asynccontextmanager
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import Field, create_model

from fastmcp.tools.tool import Tool
from mcp_composer.utils import LoggerFactory
from mcp_composer.composer import MCPComposer

logger = LoggerFactory.get_logger()

COMPOSER = MCPComposer()
TOOLS: Dict[str, Tool] = {}

def schema_type_to_py_type(field_schema: Dict[str, Any]) -> Any:
    """
    Map JSON schema types to Python types for dynamic model generation.
    """
    field_type = field_schema.get("type", "string")

    if field_type == "string":
        return str
    if field_type == "integer":
        return int
    if field_type == "boolean":
        return bool
    if field_type == "number":
        return float
    if field_type == "object":
        return Dict[str, Any]
    if field_type == "array":
        return list
    return Any

def make_tool_endpoint(tool_model, tool: Tool):
    """
    Generate an endpoint function for a given tool using its model.
    """
    async def endpoint(body: tool_model):  # pylint: disable=invalid-name
        try:
            result = await tool.run(body.model_dump())
            return {"result": result}
        except Exception as exc:
            logger.exception("Tool '%s' failed with error", tool.name)
            raise HTTPException(
                status_code=500,
                detail=str(exc)
            ) from exc

    return endpoint

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan hook to load tools and dynamically register endpoints.
    """
    tools = await COMPOSER._tool_manager.get_all_tools()  # pylint: disable=protected-access
    logger.info("Loaded composer tools: %s", list(tools.keys()))

    for tool_name, tool in tools.items():
        param_schema = tool.parameters
        fields = {}
        properties = param_schema.get("properties", {})
        required = set(param_schema.get("required", []))

        for param_name, param_def in properties.items():
            annotation = schema_type_to_py_type(param_def)
            default = ... if param_name in required else None
            description = param_def.get("description", param_def.get("title", ""))
            fields[param_name] = (annotation, Field(default, description=description))

        input_model = create_model(f"{tool_name}_Input", **fields)
        endpoint = make_tool_endpoint(input_model, tool)

        app.add_api_route(
            f"/tools/{tool_name}",
            endpoint,
            methods=["POST"],
            response_model=Dict[str, Any],
            name=f"Run {tool_name}",
            summary=tool.description or tool.name
        )

    # Register tools globally after mounting
    TOOLS.update(tools)
    yield


app = FastAPI(
    title="MCP Composer Tool API",
    description="Auto-generated REST API for all registered tools in MCP Composer.",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/", summary="Health check")
def root():
    """
    Root endpoint to verify that the API is running.
    """
    return {"message": "MCP Composer Tool API is running."}

@app.get("/tools", summary="List all available tools")
def list_tools():
    """
    Return a list of all loaded tool names.
    """
    return list(TOOLS.keys())

if __name__ == "__main__":
    uvicorn.run("mcp_composer_app.app:app", host="0.0.0.0", port=8000, reload=True)
