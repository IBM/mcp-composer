# model_mesh_composer.py
"""
Example composer setup with ModelMeshTool.

This shows how to integrate ModelMeshTool into a composer that can be run
as an MCP server with 3 models: Guardian, Vision, and Text.

Features:
- Guardian model for content safety and moderation (Ollama provider with think=True)
- Vision model for image analysis (Ollama provider)
- Text model for text processing (LiteLLM provider)
- Graceful degradation: works even if some models are not available
"""

import asyncio
import os
from pathlib import Path

from mcp_composer import MCPComposer
from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool


async def main():
    """
    Model Mesh Composer: A specialized MCP Composer with model mesh capabilities.
    
    Configures 3 models:
    1. Guardian - Content safety and moderation
    2. Vision - Image analysis
    3. Text - Text processing and summarization
    """
    mode = os.getenv("MCP_MODE", "sse").lower()
    
    # Create composer
    composer = MCPComposer("model-mesh-composer")
    
    # Disable default composer tools (optional, depending on your needs)
    composer.disable_composer_tool()
    
    # Get the path to the example prompt config
    example_dir = Path(__file__).parent
    prompt_config_path = example_dir / "model_mesh_prompts.json"
    
    # Configure the Model Mesh Tool with 3 models
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
                "model": "ibm/granite3.2-vision",
                "provider": "ollama",
                "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            },
            # Text model with LiteLLM provider (default)
            # Note: If llama2 is not available, the tool will show a warning but continue to work
            # with other available models (guardian, vision)
            "text": {
                "model": "llama2",
                "provider": "litellm",
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
    
    # Run the composer based on mode
    if mode == "http":
        await composer.run_http_async(
            host="0.0.0.0",
            port=9000,
            log_level="debug",
            path="/mcp"
        )
    elif mode == "stdio":
        await composer.run_stdio_async()
    elif mode == "sse":
        await composer.run_sse_async(
            host="localhost",
            port=9000,
            log_level="debug"
        )
    else:
        raise ValueError(f"Unsupported MCP_MODE: {mode}")


if __name__ == "__main__":
    # Prerequisites:
    # 1. Install providers:
    #    - pip install litellm  # For LiteLLM provider (text model)
    #    - pip install ollama   # For Ollama provider (guardian, vision models)
    # 2. Ensure Ollama is running: ollama serve
    # 3. Pull required models:
    #    - ollama pull ibm/granite3.3-guardian:8b  # Guardian model
    #    - ollama pull ibm/granite3.3-vision:2b    # Vision model
    #    - ollama pull llama2                      # Text model (via LiteLLM)
    # 4. Set MCP_MODE environment variable (optional, defaults to 'sse'):
    #    export MCP_MODE=sse  # or 'http' or 'stdio'
    # 5. Set OLLAMA_BASE_URL if needed (optional, defaults to http://localhost:11434):
    #    export OLLAMA_BASE_URL=http://localhost:11434
    #
    # Note: The tool will work even if some models are not available.
    # It will show warnings and gracefully handle unavailable models.
    
    asyncio.run(main())


