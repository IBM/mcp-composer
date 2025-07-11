import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from mcp_composer.composer import MCPComposer



@pytest.mark.asyncio
async def test_prompts():
    composer = MCPComposer("composer")
    await composer.setup_member_servers()
    config = [ {
        "name": "promo_http_avg_response",
        "description": "Average response time of promo HTTP calls handled by a cluster",
        "template": "What is the average response time of promo HTTP calls handled by Kubernetes cluster {{ cluster }}?",
        "arguments": [
            {
                "name": "cluster",
                "type": "string",
                "required": "true",
                "description": "The name of the Kubernetes cluster"
            }
        ]
    }]
    await composer.add_prompts(config)
    prompts = await composer.get_prompts()
    assert isinstance(prompts, dict), "Composer should return a dictionary of prompts"

@pytest.mark.asyncio
async def test_add_prompts():
    composer = MCPComposer("composer")
    config = [ {
        "name": "promo_http_avg_response",
        "description": "Average response time of promo HTTP calls handled by a cluster",
        "template": "What is the average response time of promo HTTP calls handled by Kubernetes cluster {{ cluster }}?",
        "arguments": [
            {
                "name": "cluster",
                "type": "string",
                "required": "true",
                "description": "The name of the Kubernetes cluster"
            }
        ]
    }]
    res = await composer.add_prompts(config)     
    assert len(res) == 1, "Composer should return a dictionary of prompts"           

@pytest.mark.asyncio
async def test_builder():    
    config = [
        {
        "id": "mcp-prompt",
        "type": "local",
        "prompt_path":"/Users/mansurah/GitHub/mcp-composer/test/data/prompts.json"
        }
    ]
    composer = MCPComposer("composer")
    await composer.setup_member_servers()
    prompts = await composer.get_prompts()
    assert len(prompts) == 16, "Composer should return a dictionary of prompts"  
    assert isinstance(prompts, dict), "Composer should return a dictionary of prompts"

@pytest.mark.asyncio
async def test_builder_local():    
    config = [
        {
        "id": "mcp-prompt",
        "type": "local",
        "prompt_path":"/Users/mansurah/GitHub/mcp-composer/test/data/prompts.json"
        }
    ]
    composer = MCPComposer("composer")
    await composer.setup_member_servers()
    prompts = await composer.get_all_prompts()
    assert len(prompts) == 16, "Composer should return a dictionary of prompts"  
    assert isinstance(prompts, list), "Composer should return a dictionary of prompts"
@pytest.mark.asyncio
async def test_get_all_prompts_returns_dict():
            """Test get_all_prompts returns a dict with added prompts"""
            prompt_config = [{
                "name": "test_prompt",
                "description": "A test prompt",
                "template": "Hello, this is a test prompt."
            }]
            gw = MCPComposer("composer")
            added = await gw.add_prompts(prompt_config)
            assert "test_prompt" in added
            prompts = await gw.get_all_prompts()
            assert isinstance(prompts, list), "Should return a dictionary"
            # The prompt should be present in the dict values
            #assert (any("Hello, this is a test prompt." in str(v) for v in prompts))
@pytest.mark.asyncio
async def test_get_all_prompts_empty():
    """Test get_all_prompts returns empty dict when no prompts are added"""
    gw = MCPComposer("composer")
    prompts = await gw.get_all_prompts()
    assert isinstance(prompts, list), "Should return a dictionary"
    assert len(prompts)== 0, "Should return an empty dictionary when no prompts are added"        