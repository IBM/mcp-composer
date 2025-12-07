#!/usr/bin/env python3
"""
Test script for Vision Model in Model Mesh Tool

This script helps diagnose why the vision model is not working.
It tests various aspects of the vision model configuration and usage.

Usage:
    python example/test_vision_model.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src directory to path to import mcp_composer
# This file is in modules/mcp_composer/tests/unit/
# We need to add modules/mcp_composer/src to the path
test_file = Path(__file__)
src_path = test_file.parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from mcp_composer.core.tools.model_mesh_tool import ModelMeshTool
from mcp_composer.core.tools.model_providers import ModelProviderFactory
from mcp_composer.core.utils import LoggerFactory

logger = LoggerFactory.get_logger()


async def test_ollama_connection(base_url: str = "http://localhost:11434"):
    """Test if Ollama is running and accessible."""
    print("\n" + "="*60)
    print("TEST 1: Ollama Connection")
    print("="*60)
    
    try:
        from ollama import AsyncClient
        client = AsyncClient(host=base_url)
        
        # Try to list models
        models = await client.list()
        print(f"✅ Ollama is running at {base_url}")
        print(f"✅ Found {len(models.models)} models available")
        print("\nAvailable models:")
        for model in models.models:
            print(f"  - {model.model}")
        return True, models.models
    except ImportError:
        print("❌ ollama-python library not installed")
        print("   Install with: pip install ollama")
        return False, []
    except Exception as e:
        print(f"❌ Cannot connect to Ollama at {base_url}")
        print(f"   Error: {e}")
        print("\n   Troubleshooting:")
        print("   1. Check if Ollama is running: ollama serve")
        print(f"   2. Verify URL is correct: {base_url}")
        print("   3. Check if Ollama is accessible: curl http://localhost:11434/api/tags")
        return False, []


async def test_model_availability(model_name: str, base_url: str = "http://localhost:11434"):
    """Test if a specific model is available in Ollama."""
    print("\n" + "="*60)
    print(f"TEST 2: Model Availability - {model_name}")
    print("="*60)
    
    try:
        from ollama import AsyncClient
        client = AsyncClient(host=base_url)
        
        models = await client.list()
        available_models = [model.model for model in models.models]
        
        # Check exact match
        if model_name in available_models:
            print(f"✅ Model '{model_name}' is available")
            return True
        
        # Check partial match (handles tags)
        model_base = model_name.split(":")[0]
        matching_models = [m for m in available_models if m.startswith(model_base)]
        
        if matching_models:
            print(f"⚠️  Model '{model_name}' not found exactly, but found similar:")
            for m in matching_models:
                print(f"   - {m}")
            print(f"\n   Try using one of these models instead")
            return False
        else:
            print(f"❌ Model '{model_name}' is NOT available")
            print(f"\n   To install:")
            print(f"   ollama pull {model_name}")
            print(f"\n   Common vision models:")
            print(f"   - ollama pull ibm/granite3.2-vision")
            print(f"   - ollama pull ibm/granite3.3-vision:2b")
            print(f"   - ollama pull llava")
            print(f"   - ollama pull llava:13b")
            return False
    except Exception as e:
        print(f"❌ Error checking model availability: {e}")
        return False


async def test_provider_availability():
    """Test if providers are available."""
    print("\n" + "="*60)
    print("TEST 3: Provider Availability")
    print("="*60)
    
    litellm_available = ModelProviderFactory.is_provider_available("litellm")
    ollama_available = ModelProviderFactory.is_provider_available("ollama")
    
    if litellm_available:
        print("✅ LiteLLM provider is available")
    else:
        print("❌ LiteLLM provider is NOT available")
        print("   Install with: pip install litellm")
    
    if ollama_available:
        print("✅ Ollama provider is available")
    else:
        print("❌ Ollama provider is NOT available")
        print("   Install with: pip install ollama")
    
    return litellm_available or ollama_available


async def test_model_mesh_tool_initialization(model_name: str, base_url: str = "http://localhost:11434"):
    """Test if ModelMeshTool can be initialized with vision model."""
    print("\n" + "="*60)
    print(f"TEST 4: ModelMeshTool Initialization with Vision Model")
    print("="*60)
    
    try:
        tool = ModelMeshTool({
            "name": "test_vision",
            "model_config": {
                "vision": {
                    "model": model_name,
                    "provider": "ollama",
                    "base_url": base_url
                }
            },
            "base_url": base_url,
            "default_provider": "litellm"
        })
        print(f"✅ ModelMeshTool initialized successfully")
        print(f"   Vision model configured: {model_name}")
        print(f"   Provider: ollama")
        return True, tool
    except Exception as e:
        print(f"❌ Failed to initialize ModelMeshTool: {e}")
        return False, None


async def test_vision_model_call(tool, model_name: str):
    """Test calling the vision model with a simple prompt."""
    print("\n" + "="*60)
    print("TEST 5: Vision Model Call")
    print("="*60)
    
    if not tool:
        print("❌ Cannot test - tool not initialized")
        return False
    
    # Test with a simple image description prompt
    test_prompt = "Describe this image: A sunset over mountains with a lake in the foreground"
    
    print(f"Calling vision model '{model_name}' with prompt:")
    print(f"  '{test_prompt}'")
    print()
    
    try:
        result = await tool.run({
            "task": "vision",
            "prompt": test_prompt,
            "temperature": 0.7,
            "max_tokens": 500
        })
        
        # Check result
        if hasattr(result, 'content') and result.content:
            response_text = result.content[0].text if isinstance(result.content, list) else str(result.content)
            
            # Try to parse as JSON if it's a string
            import json
            try:
                response_data = json.loads(response_text)
                status = response_data.get("status", "unknown")
                
                if status == "success":
                    print("✅ Vision model call succeeded!")
                    print(f"\nResponse: {response_data.get('response', 'No response')[:200]}...")
                    print(f"\nModel used: {response_data.get('model', 'unknown')}")
                    print(f"Provider used: {response_data.get('provider', 'unknown')}")
                    if "capability" in response_data:
                        print(f"Capability: {response_data['capability'].get('description', 'N/A')}")
                    return True
                elif status == "error":
                    print("❌ Vision model call failed!")
                    print(f"\nError: {response_data.get('error', 'Unknown error')}")
                    print(f"\nSuggestion: {response_data.get('suggestion', 'No suggestion')}")
                    return False
                else:
                    print(f"⚠️  Unexpected status: {status}")
                    print(f"Response: {response_text[:500]}")
                    return False
            except json.JSONDecodeError:
                # Not JSON, just print the response
                print("✅ Vision model call succeeded!")
                print(f"\nResponse: {response_text[:500]}...")
                return True
        else:
            print("❌ No response content received")
            print(f"Result: {result}")
            return False
            
    except Exception as e:
        print(f"❌ Error calling vision model: {e}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return False


async def test_direct_ollama_call(model_name: str, base_url: str = "http://localhost:11434"):
    """Test calling Ollama directly to verify the model works."""
    print("\n" + "="*60)
    print("TEST 6: Direct Ollama API Call")
    print("="*60)
    
    try:
        from ollama import AsyncClient
        client = AsyncClient(host=base_url)
        
        test_prompt = "Describe this image: A sunset over mountains"
        
        print(f"Calling Ollama directly with model '{model_name}'")
        print(f"Prompt: '{test_prompt}'")
        print()
        
        response = await client.chat(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": test_prompt
                }
            ],
            options={
                "temperature": 0.7,
                "num_predict": 500
            }
        )
        
        print("✅ Direct Ollama call succeeded!")
        print(f"\nResponse: {response.message.content[:200]}...")
        print(f"Model used: {getattr(response, 'model', 'unknown')}")
        return True
        
    except Exception as e:
        print(f"❌ Direct Ollama call failed: {e}")
        error_msg = str(e).lower()
        
        if "model" in error_msg and ("not found" in error_msg or "does not exist" in error_msg):
            print(f"\n   The model '{model_name}' is not available in Ollama.")
            print(f"   Install it with: ollama pull {model_name}")
        elif "connection" in error_msg or "refused" in error_msg:
            print(f"\n   Cannot connect to Ollama at {base_url}")
            print(f"   Make sure Ollama is running: ollama serve")
        else:
            print(f"\n   Unexpected error: {e}")
        
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("VISION MODEL DIAGNOSTIC TEST SUITE")
    print("="*60)
    
    # Configuration
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # Try different possible vision model names
    possible_models = [
        "ibm/granite3.3-vision:2b",  # From your config
        "ibm/granite3.2-vision",
        "granite3.2-vision:latest",
        "llava",
        "llava:13b"
    ]
    
    # Test 1: Ollama connection
    ollama_ok, available_models = await test_ollama_connection(base_url)
    
    if not ollama_ok:
        print("\n" + "="*60)
        print("❌ CRITICAL: Ollama is not accessible. Fix this first.")
        print("="*60)
        return
    
    # Determine which model to test
    model_to_test = None
    if available_models:
        # Check if any of the possible models are available
        available_model_names = [m.model for m in available_models]
        for possible in possible_models:
            model_base = possible.split(":")[0]
            for available in available_model_names:
                if available == possible or available.startswith(model_base):
                    model_to_test = available
                    print(f"\n✅ Will test with model: {model_to_test}")
                    break
            if model_to_test:
                break
        
        if not model_to_test:
            print(f"\n⚠️  None of the expected vision models are available.")
            print(f"   Available models: {', '.join(available_model_names)}")
            print(f"\n   Please pull a vision model:")
            print(f"   ollama pull ibm/granite3.3-vision:2b")
            print(f"   OR")
            print(f"   ollama pull llava")
            model_to_test = possible_models[0]  # Use first as fallback for testing
    else:
        model_to_test = possible_models[0]
    
    # Test 2: Model availability
    model_available = await test_model_availability(model_to_test, base_url)
    
    # Test 3: Provider availability
    provider_ok = await test_provider_availability()
    
    if not provider_ok:
        print("\n" + "="*60)
        print("❌ CRITICAL: No providers are available. Install at least one.")
        print("="*60)
        return
    
    # Test 4: Tool initialization
    tool_ok, tool = await test_model_mesh_tool_initialization(model_to_test, base_url)
    
    # Test 5: Vision model call via tool
    if tool_ok:
        await test_vision_model_call(tool, model_to_test)
    
    # Test 6: Direct Ollama call
    await test_direct_ollama_call(model_to_test, base_url)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Ollama Connection: {'✅' if ollama_ok else '❌'}")
    print(f"Model Available: {'✅' if model_available else '❌'}")
    print(f"Provider Available: {'✅' if provider_ok else '❌'}")
    print(f"Tool Initialization: {'✅' if tool_ok else '❌'}")
    print("\n" + "="*60)
    
    if not model_available:
        print("\n🔧 RECOMMENDED FIX:")
        print(f"   ollama pull {model_to_test}")
        print(f"   OR")
        print(f"   ollama pull ibm/granite3.2-vision")
        print(f"   OR")
        print(f"   ollama pull llava")
    elif not ollama_ok:
        print("\n🔧 RECOMMENDED FIX:")
        print("   Start Ollama: ollama serve")


if __name__ == "__main__":
    asyncio.run(main())
