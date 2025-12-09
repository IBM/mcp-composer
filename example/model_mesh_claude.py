#!/usr/bin/env python3
"""
Model Mesh Composer for Claude Desktop

This script sets up a Model Mesh Tool with Guardian, Vision, and Text models
for use with Claude Desktop via MCP.

Usage:
    1. Make executable: chmod +x model_mesh_claude.py
    2. Configure in Claude Desktop config file
    3. Restart Claude Desktop
"""

import asyncio
import os
from pathlib import Path

from mcp_composer import MCPComposer
from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool


async def main():
    """
    Model Mesh Composer for Claude Desktop.
    """
    # Create composer
    composer = MCPComposer("model-mesh-composer")
    
    # Disable default composer tools (optional)
    composer.disable_composer_tool()
    
    # Get the path to the example prompt config
    script_dir = Path(__file__).parent
    prompt_config_path = script_dir / "model_mesh_prompts.json"
    
    # Configure the Model Mesh Tool
    # Note: If some models are not available (e.g., llama2 not pulled), the tool will:
    # - Show warnings during initialization
    # - Continue to work with available models
    # - Return graceful error messages when unavailable models are called
    # This allows the tool to work even if not all models are installed
    model_mesh_tool = ModelMeshTool({
        "name": "model_mesh",
        "prompt_config_path": str(prompt_config_path),
        "model_config": {
            # Guardian model with Ollama provider (for think=True support)
            "guardian": {
                "model": "ibm/granite3.3-guardian:8b",
                "provider": "ollama",
                "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                "options": {
                    "think": True,
                    "temperature": 0
                }
            },
            # Vision model with Ollama provider
            "vision": {
                "model": "ibm/granite-docling",
                "provider": "ollama",
                "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            }
        },
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "default_provider": "litellm"
    })
    
    # Add the tool to the composer
    composer.add_tool(model_mesh_tool)
    
    # Setup member servers (if any)
    await composer.setup_member_servers()
    
    # Run in stdio mode for Claude Desktop
    await composer.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
