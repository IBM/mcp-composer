"""
Example: Using Guardian Model with Ollama Provider

This example demonstrates how to configure and use the IBM Granite Guardian model
with the ollama-python provider, including the think=True parameter for Guardian models.
"""

import asyncio
import os
from pathlib import Path

from mcp_composer import MCPComposer
from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool


async def main():
    """
    Example: Guardian Model with Ollama Provider
    
    This shows how to:
    1. Configure a Guardian model with provider="ollama"
    2. Use think=True and temperature=0 (required for Guardian)
    3. Call the model via ollama-python library
    """
    # Create composer
    composer = MCPComposer("guardian-model-composer")
    composer.disable_composer_tool()
    
    # Configure the Model Mesh Tool with Guardian model
    model_mesh_tool = ModelMeshTool({
        "name": "model_mesh",
        "model_config": {
            "guardian": {
                "model": "ibm/granite3.3-guardian:8b",
                "provider": "ollama",  # Use ollama-python directly
                "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                "options": {
                    "think": True,      # Enable thinking mode for Guardian
                    "temperature": 0   # Required for Guardian models
                }
            }
        },
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    })
    
    # Add the tool to the composer
    composer.add_tool(model_mesh_tool)
    
    # Example 1: Basic Guardian usage
    print("Example 1: Guardian model with think=True")
    result1 = await model_mesh_tool.run({
        "task": "guardian",
        "prompt": "hello world"
    })
    print(f"Result 1: {result1.content[0].text}\n")
    
    # Example 2: Guardian with custom prompt
    print("Example 2: Guardian with custom prompt")
    result2 = await model_mesh_tool.run({
        "task": "guardian",
        "prompt": "Analyze this content for safety: 'This is a test message'"
    })
    print(f"Result 2: {result2.content[0].text}\n")
    
    # Example 3: Temperature override (though Guardian should use 0)
    print("Example 3: Temperature override (not recommended for Guardian)")
    result3 = await model_mesh_tool.run({
        "task": "guardian",
        "prompt": "hello world",
        "temperature": 0  # Explicitly set (though config already has it)
    })
    print(f"Result 3: {result3.content[0].text}\n")
    
    print("All Guardian examples completed!")
    
    # Note: The internal call is equivalent to:
    # from ollama import AsyncClient
    # 
    # client = AsyncClient(host="http://localhost:11434")
    # response = await client.chat(
    #     model="ibm/granite3.3-guardian:8b",
    #     think=True,
    #     messages=[{"role": "user", "content": "hello world"}],
    #     options={"temperature": 0}
    # )


if __name__ == "__main__":
    # Prerequisites:
    # 1. Install ollama-python: pip install ollama
    # 2. Ensure Ollama is running: ollama serve
    # 3. Pull the Guardian model:
    #    ollama pull ibm/granite3.3-guardian:8b
    # 4. Set OLLAMA_BASE_URL if needed (optional, defaults to http://localhost:11434)
    
    asyncio.run(main())
