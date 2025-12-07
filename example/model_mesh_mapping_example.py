"""
Example: Model Mesh Task-to-Model Mapping

This example demonstrates how different models are mapped to different tasks
in the ModelMeshTool, and how the routing works.
"""

import asyncio
import os
from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool


async def main():
    """
    Demonstrates task-to-model mapping in ModelMeshTool.
    """
    
    # Configure ModelMeshTool with multiple models for different tasks
    tool = ModelMeshTool({
        "name": "model_mesh",
        "model_config": {
            # Task: "vision" → Model: ibm/granite3.3-vision:2b
            "vision": {
                "model": "ibm/granite3.3-vision:2b",
                "provider": "ollama",
                "base_url": "http://localhost:11434"
            },
            
            # Task: "guardian" → Model: ibm/granite3.3-guardian:8b
            "guardian": {
                "model": "ibm/granite3.3-guardian:8b",
                "provider": "ollama",
                "base_url": "http://localhost:11434",
                "options": {
                    "think": True,
                    "temperature": 0
                }
            },
            
            # Task: "text" → Model: llama2
            "text": {
                "model": "llama2",
                "provider": "ollama",
                "base_url": "http://localhost:11434"
            }
        },
        "ollama_base_url": "http://localhost:11434"
    })
    
    print("=" * 60)
    print("Model Mesh Task-to-Model Mapping Example")
    print("=" * 60)
    print()
    
    # Show the mapping
    print("Configured Mappings:")
    print("  task: 'vision'   → model: ibm/granite3.3-vision:2b")
    print("  task: 'guardian' → model: ibm/granite3.3-guardian:8b (think=True, temp=0)")
    print("  task: 'text'     → model: llama2")
    print()
    
    # Example 1: Vision task
    print("-" * 60)
    print("Example 1: Vision Task")
    print("-" * 60)
    print("Call: tool.run({'task': 'vision', 'prompt': '...'})")
    print("→ Routes to: ibm/granite3.3-vision:2b via ollama provider")
    print()
    
    try:
        result1 = await tool.run({
            "task": "vision",
            "prompt": "Describe what you see in this image"
        })
        print(f"✓ Success! Model: ibm/granite3.3-vision:2b")
        print(f"Response preview: {result1.content[0].text[:100]}...")
    except Exception as e:
        print(f"✗ Error (expected if model not available): {e}")
    print()
    
    # Example 2: Guardian task
    print("-" * 60)
    print("Example 2: Guardian Task")
    print("-" * 60)
    print("Call: tool.run({'task': 'guardian', 'prompt': '...'})")
    print("→ Routes to: ibm/granite3.3-guardian:8b via ollama provider")
    print("→ With options: think=True, temperature=0")
    print()
    
    try:
        result2 = await tool.run({
            "task": "guardian",
            "prompt": "hello world"
        })
        print(f"✓ Success! Model: ibm/granite3.3-guardian:8b")
        print(f"Response preview: {result2.content[0].text[:100]}...")
    except Exception as e:
        print(f"✗ Error (expected if model not available): {e}")
    print()
    
    # Example 3: Text task
    print("-" * 60)
    print("Example 3: Text Task")
    print("-" * 60)
    print("Call: tool.run({'task': 'text', 'prompt': '...'})")
    print("→ Routes to: llama2 via ollama provider")
    print()
    
    try:
        result3 = await tool.run({
            "task": "text",
            "prompt": "Explain quantum computing in simple terms"
        })
        print(f"✓ Success! Model: llama2")
        print(f"Response preview: {result3.content[0].text[:100]}...")
    except Exception as e:
        print(f"✗ Error (expected if model not available): {e}")
    print()
    
    # Example 4: Case-insensitive task names
    print("-" * 60)
    print("Example 4: Case-Insensitive Task Names")
    print("-" * 60)
    print("Task names are case-insensitive:")
    print("  'vision' = 'Vision' = 'VISION'")
    print()
    
    # Example 5: Model override
    print("-" * 60)
    print("Example 5: Model Override")
    print("-" * 60)
    print("You can override the model selection at runtime:")
    print("  tool.run({'task': 'vision', 'model_override': 'llava', ...})")
    print("→ Uses 'llava' instead of configured 'ibm/granite3.3-vision:2b'")
    print()
    
    # Example 6: Invalid task
    print("-" * 60)
    print("Example 6: Invalid Task (Error Handling)")
    print("-" * 60)
    print("Call: tool.run({'task': 'invalid_task', 'prompt': '...'})")
    print("→ Raises ValueError with available tasks")
    print()
    
    try:
        await tool.run({
            "task": "invalid_task",
            "prompt": "This will fail"
        })
    except ValueError as e:
        print(f"✓ Caught expected error: {e}")
    print()
    
    print("=" * 60)
    print("Mapping Summary")
    print("=" * 60)
    print()
    print("The ModelMeshTool uses a dictionary-based mapping:")
    print()
    print("  model_config = {")
    print("      'task_name': {")
    print("          'model': 'model_name',")
    print("          'provider': 'ollama' | 'litellm',")
    print("          'options': {...}")
    print("      }")
    print("  }")
    print()
    print("When you call tool.run({'task': 'task_name', ...}):")
    print("  1. Extract task parameter: 'task_name'")
    print("  2. Lookup: model_config.get('task_name')")
    print("  3. Get model configuration")
    print("  4. Route to appropriate provider")
    print("  5. Execute model call")
    print()


if __name__ == "__main__":
    # Prerequisites:
    # 1. Install ollama-python: pip install ollama
    # 2. Ensure Ollama is running: ollama serve
    # 3. Pull required models:
    #    - ollama pull ibm/granite3.3-vision:2b
    #    - ollama pull ibm/granite3.3-guardian:8b
    #    - ollama pull llama2
    
    asyncio.run(main())
