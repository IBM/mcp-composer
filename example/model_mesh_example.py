# model_mesh_example.py
"""
Example usage of the ModelMeshTool.

This example demonstrates how to:
1. Create and configure a ModelMeshTool
2. Use it with prompts from JSON configuration
3. Route tasks to different models based on task type
"""

import asyncio
import os
from pathlib import Path

from mcp_composer import MCPComposer
from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool


async def main():
    """
    Example: Model Mesh Tool usage with vision and speech models.
    """
    # Create composer
    composer = MCPComposer("model-mesh-composer")
    
    # Disable default composer tools (optional)
    composer.disable_composer_tool()
    
    # Get the path to the example prompt config
    example_dir = Path(__file__).parent
    prompt_config_path = example_dir / "model_mesh_prompts.json"
    
    # Configure the Model Mesh Tool
    model_mesh_tool = ModelMeshTool({
        "name": "model_mesh",
        "prompt_config_path": str(prompt_config_path),
        "model_config": {
            "vision": "llava",        # Vision model (e.g., llava for vision tasks)
            "speech": "whisper",      # Speech model (e.g., whisper for speech recognition)
            "text": "llama2"          # Text model (e.g., llama2 for general text tasks)
        },
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    })
    
    # Add the tool to the composer
    composer.add_tool(model_mesh_tool)
    
    # Example 1: Use a prompt from the JSON config file
    print("Example 1: Using prompt from JSON config")
    result1 = await model_mesh_tool.run({
        "task": "vision",
        "prompt_key": "vision_analysis",
        "prompt_variables": {
            "image_description": "A cat sitting on a windowsill",
            "focus_areas": "objects, colors, and spatial relationships"
        }
    })
    print(f"Result 1: {result1.content[0].text}\n")
    
    # Example 2: Use a direct prompt (without JSON config)
    print("Example 2: Using direct prompt")
    result2 = await model_mesh_tool.run({
        "task": "speech",
        "prompt": "Transcribe this audio: A conversation about the weather between two people.",
        "temperature": 0.5,
        "max_tokens": 500
    })
    print(f"Result 2: {result2.content[0].text}\n")
    
    # Example 3: Override model selection
    print("Example 3: Overriding model selection")
    result3 = await model_mesh_tool.run({
        "task": "vision",
        "prompt": "Describe this image in detail.",
        "model_override": "llava:13b"  # Use a specific model variant
    })
    print(f"Result 3: {result3.content[0].text}\n")
    
    # Example 4: Text task
    print("Example 4: Text summarization task")
    result4 = await model_mesh_tool.run({
        "task": "text",
        "prompt_key": "text_summarization",
        "prompt_variables": {
            "text": "The quick brown fox jumps over the lazy dog. This is a classic pangram used for typing practice.",
            "max_sentences": 2
        }
    })
    print(f"Result 4: {result4.content[0].text}\n")
    
    print("All examples completed successfully!")


if __name__ == "__main__":
    # Note: Make sure Ollama is running and the models are available
    # You can check with: ollama list
    # Pull models with: ollama pull llava, ollama pull whisper, ollama pull llama2
    
    asyncio.run(main())


