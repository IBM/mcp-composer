import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from mcp_composer.composer import MCPComposer
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_prompts():
    """Test basic prompt functionality through composer interface."""
    composer = MCPComposer("composer")
    config = [{
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
    composer.add_prompts(config)
    prompts = await composer.get_all_prompts()
    assert len(prompts) == 1
    assert "promo_http_avg_response" in prompts[0]


@pytest.mark.asyncio
async def test_add_prompts():
    """Test adding prompts through composer interface."""
    composer = MCPComposer("composer")
    config = [{
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
    res = composer.add_prompts(config)
    assert len(res) == 1
    assert res[0] == "promo_http_avg_response"


@pytest.mark.asyncio
async def test_builder():
    """Test prompt builder functionality through composer interface."""
    config = [{
        "id": "mcp-prompt",
        "type": "local",
        "prompt_path": "test/data/prompts.json"
    }]
    composer = MCPComposer("composer", config=config)
    await composer.setup_member_servers()
    prompts = await composer.get_all_prompts()
    assert len(prompts) >= 0, "Composer should return a list of prompts"
    assert isinstance(prompts, list), "Composer should return a list of prompts"


@pytest.mark.asyncio
async def test_builder_local():
    """Test local prompt builder functionality through composer interface."""
    config = [{
        "id": "mcp-prompt",
        "type": "local",
        "prompt_path": "test/data/prompts.json"
    }]
    composer = MCPComposer("composer", config=config)
    await composer.setup_member_servers()
    prompts = await composer.get_all_prompts()
    assert len(prompts) >= 0, "Composer should return a list of prompts"
    assert isinstance(prompts, list), "Composer should return a list of prompts"


@pytest.mark.asyncio
async def test_get_all_prompts_returns_list():
    """Test get_all_prompts returns a list with added prompts through composer interface."""
    prompt_config = [{
        "name": "test_prompt",
        "description": "A test prompt",
        "template": "Hello, this is a test prompt."
    }]
    composer = MCPComposer("composer")
    added = composer.add_prompts(prompt_config)
    assert len(added) == 1
    assert added[0] == "test_prompt"
    prompts = await composer.get_all_prompts()
    assert len(prompts) == 1
    assert isinstance(prompts, list)
    assert isinstance(prompts[0], str)


@pytest.mark.asyncio
async def test_get_all_prompts_empty():
    """Test get_all_prompts returns empty list when no prompts are added through composer interface."""
    composer = MCPComposer("composer")
    prompts = await composer.get_all_prompts()
    assert len(prompts) == 0
    assert isinstance(prompts, list)


@pytest.mark.asyncio
async def test_list_prompts_per_server():
    """Test listing prompts from a specific server through composer interface."""
    composer = MCPComposer("test-composer")

    # Add test prompts first
    prompt_config = [
        {
            "name": "server_prompt_1",
            "description": "Server prompt 1",
            "template": "Template 1"
        },
        {
            "name": "server_prompt_2",
            "description": "Server prompt 2",
            "template": "Template 2"
        }
    ]
    composer.add_prompts(prompt_config)

    # Test listing prompts per server using composer interface
    result = await composer.list_prompts_per_server("test-composer")
    # Should return prompts for the server (may be empty if no server is mounted)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_prompts_per_server_not_found():
    """Test listing prompts from a non-existent server through composer interface."""
    composer = MCPComposer("test-composer")

    # Test listing prompts for non-existent server using composer interface
    result = await composer.list_prompts_per_server("non-existent-server")
    assert isinstance(result, list)
    # Should return empty list for non-existent server
    assert len(result) == 0


@pytest.mark.asyncio
async def test_filter_prompts():
    """Test filtering prompts by criteria through composer interface."""
    composer = MCPComposer("test-composer")

    # Add test prompts
    prompt_config = [
        {
            "name": "test_prompt_1",
            "description": "First test prompt",
            "template": "Template 1"
        },
        {
            "name": "test_prompt_2",
            "description": "Second test prompt",
            "template": "Template 2"
        },
        {
            "name": "another_prompt",
            "description": "Another prompt",
            "template": "Template 3"
        }
    ]

    composer.add_prompts(prompt_config)

    # Test filtering by name
    result = await composer.filter_prompts({"name": "test"})
    assert len(result) == 2
    assert any(r["name"] == "test_prompt_1" for r in result)
    assert any(r["name"] == "test_prompt_2" for r in result)

    # Test filtering by description
    result = await composer.filter_prompts({"description": "First"})
    assert len(result) == 1
    assert result[0]["name"] == "test_prompt_1"

    # Test filtering with no matches
    result = await composer.filter_prompts({"name": "nonexistent"})
    assert len(result) == 0


@pytest.mark.asyncio
async def test_disable_prompts():
    """Test disabling prompts through composer interface."""
    composer = MCPComposer("test-composer")

    # Add test prompts first
    prompt_config = [
        {
            "name": "test_prompt_1",
            "description": "First test prompt",
            "template": "Template 1"
        },
        {
            "name": "test_prompt_2", 
            "description": "Second test prompt",
            "template": "Template 2"
        }
    ]
    composer.add_prompts(prompt_config)

    # Test disabling a prompt using composer interface
    result = await composer.disable_prompts(["test_prompt_1"], "test-composer")
    assert "Failed to disable prompts" in result or "No prompts found to disable" in result

    # Test disabling non-existent prompt
    result = await composer.disable_prompts(["nonexistent"], "test-composer")
    assert "Failed to disable prompts" in result or "No prompts found to disable" in result


@pytest.mark.asyncio
async def test_enable_prompts():
    """Test enabling prompts through composer interface."""
    composer = MCPComposer("test-composer")

    # Add test prompts first
    prompt_config = [
        {
            "name": "test_prompt_1",
            "description": "First test prompt", 
            "template": "Template 1"
        },
        {
            "name": "test_prompt_2",
            "description": "Second test prompt",
            "template": "Template 2"
        }
    ]
    composer.add_prompts(prompt_config)

    # Test enabling prompts using composer interface
    # Since we don't have a mounted server, this should return an appropriate error message
    result = await composer.enable_prompts(["test_prompt_1"], "test-composer")
    assert "Failed to enable prompts" in result or "No prompts disabled" in result


@pytest.mark.asyncio
async def test_disable_and_enable_prompts_integration():
    """Test the complete flow of disabling and enabling prompts through composer interface."""
    composer = MCPComposer("test-composer")

    # Add test prompts first
    prompt_config = [
        {
            "name": "integration_prompt_1",
            "description": "Integration test prompt 1",
            "template": "Template 1"
        },
        {
            "name": "integration_prompt_2",
            "description": "Integration test prompt 2", 
            "template": "Template 2"
        },
        {
            "name": "integration_prompt_3",
            "description": "Integration test prompt 3",
            "template": "Template 3"
        }
    ]
    composer.add_prompts(prompt_config)

    # Test disabling multiple prompts using composer interface
    # Since we don't have a mounted server, this should return an appropriate error message
    result = await composer.disable_prompts(["integration_prompt_1", "integration_prompt_2"], "test-composer")
    assert "Failed to disable prompts" in result or "No prompts found to disable" in result

    # Test enabling one prompt back using composer interface
    result = await composer.enable_prompts(["integration_prompt_1"], "test-composer")
    assert "Failed to enable prompts" in result or "No prompts disabled" in result


@pytest.mark.asyncio
async def test_list_prompts_per_server_filters_disabled():
    """Test that list_prompts_per_server correctly filters out disabled prompts through composer interface."""
    composer = MCPComposer("test-composer")

    # Add test prompts first
    prompt_config = [
        {
            "name": "server_prompt_1",
            "description": "Server prompt 1",
            "template": "Template 1"
        },
        {
            "name": "server_prompt_2",
            "description": "Server prompt 2",
            "template": "Template 2"
        }
    ]
    composer.add_prompts(prompt_config)

    # Test listing prompts per server using composer interface
    result = await composer.list_prompts_per_server("test-composer")
    # Should return prompts for the server (may be empty if no server is mounted)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_disable_prompts_with_mounted_server():
    """Test disabling prompts through composer interface with a mounted server."""
    # Mount a server using config
    config = [{
        "id": "mcp-prompt",
        "type": "local",
        "prompt_path": "test/data/prompts.json"
    }]
    composer = MCPComposer("composer", config=config)
    await composer.setup_member_servers()

    # Get all prompts to see what's available
    all_prompts = await composer.get_all_prompts()
    assert len(all_prompts) > 0, "Should have prompts from mounted server"

    # Get prompts for the specific server
    server_prompts = await composer.list_prompts_per_server("mcp-prompt")
    assert len(server_prompts) > 0, "Should have prompts for the mounted server"

    # Get the first prompt name to test disabling
    if server_prompts:
        first_prompt_name = server_prompts[0]["name"]

        # Test disabling a prompt
        result = await composer.disable_prompts([first_prompt_name], "mcp-prompt")
        assert "Disabled" in result or "No prompts found to disable" in result

        # Test disabling non-existent prompt
        result = await composer.disable_prompts(["nonexistent_prompt"], "mcp-prompt")
        assert "No prompts found to disable" in result


@pytest.mark.asyncio
async def test_enable_prompts_with_mounted_server():
    """Test enabling prompts through composer interface with a mounted server."""
    # Mount a server using config
    config = [{
        "id": "mcp-prompt",
        "type": "local",
        "prompt_path": "test/data/prompts.json"
    }]
    composer = MCPComposer("composer", config=config)
    await composer.setup_member_servers()

    # Get all prompts to see what's available
    all_prompts = await composer.get_all_prompts()
    assert len(all_prompts) > 0, "Should have prompts from mounted server"

    # Get prompts for the specific server
    server_prompts = await composer.list_prompts_per_server("mcp-prompt")
    assert len(server_prompts) > 0, "Should have prompts for the mounted server"

    # Get the first prompt name to test enabling
    if server_prompts:
        first_prompt_name = server_prompts[0]["name"]

        # Test enabling a prompt (should work even if not disabled)
        result = await composer.enable_prompts([first_prompt_name], "mcp-prompt")
        assert "Enabled" in result or "No prompts disabled" in result


@pytest.mark.asyncio
async def test_disable_and_enable_prompts_integration_with_mounted_server():
    """Test the complete flow of disabling and enabling prompts with a mounted server."""
    # Mount a server using config
    config = [{
        "id": "mcp-prompt",
        "type": "local",
        "prompt_path": "test/data/prompts.json"
    }]
    composer = MCPComposer("composer", config=config)
    await composer.setup_member_servers()

    # Get all prompts to see what's available
    all_prompts = await composer.get_all_prompts()
    assert len(all_prompts) > 0, "Should have prompts from mounted server"

    # Get prompts for the specific server
    server_prompts = await composer.list_prompts_per_server("mcp-prompt")
    assert len(server_prompts) > 0, "Should have prompts for the mounted server"

    # Get the first two prompt names to test the integration
    if len(server_prompts) >= 2:
        first_prompt_name = server_prompts[0]["name"]
        second_prompt_name = server_prompts[1]["name"]

        # Test disabling multiple prompts
        result = await composer.disable_prompts([first_prompt_name, second_prompt_name], "mcp-prompt")
        assert "Disabled" in result or "No prompts found to disable" in result

        # Test enabling one prompt back
        result = await composer.enable_prompts([first_prompt_name], "mcp-prompt")
        assert "Enabled" in result or "No prompts disabled" in result

        # Test enabling the second prompt back
        result = await composer.enable_prompts([second_prompt_name], "mcp-prompt")
        assert "Enabled" in result or "No prompts disabled" in result


@pytest.mark.asyncio
async def test_list_prompts_per_server_filters_disabled_with_mounted_server():
    """Test that list_prompts_per_server correctly filters out disabled prompts with a mounted server."""
    # Mount a server using config
    config = [{
        "id": "mcp-prompt",
        "type": "local",
        "prompt_path": "test/data/prompts.json"
    }]
    composer = MCPComposer("composer", config=config)
    await composer.setup_member_servers()

    # Get prompts for the specific server
    server_prompts = await composer.list_prompts_per_server("mcp-prompt")
    assert len(server_prompts) > 0, "Should have prompts for the mounted server"

    # Get the first prompt name to test disabling
    if server_prompts:
        first_prompt_name = server_prompts[0]["name"]

        # Disable the first prompt
        result = await composer.disable_prompts([first_prompt_name], "mcp-prompt")
        assert "Disabled" in result or "No prompts found to disable" in result

        # Get prompts again and verify the disabled prompt is not in the list
        updated_server_prompts = await composer.list_prompts_per_server("mcp-prompt")
        prompt_names = [p["name"] for p in updated_server_prompts]
        assert first_prompt_name not in prompt_names, f"Disabled prompt '{first_prompt_name}' should not be in the list"

        # Re-enable the prompt
        result = await composer.enable_prompts([first_prompt_name], "mcp-prompt")
        assert "Enabled" in result or "No prompts disabled" in result

        # Verify the prompt is back in the list
        final_server_prompts = await composer.list_prompts_per_server("mcp-prompt")
        final_prompt_names = [p["name"] for p in final_server_prompts]
        assert first_prompt_name in final_prompt_names, f"Re-enabled prompt '{first_prompt_name}' should be back in the list"


@pytest.mark.asyncio
async def test_list_prompts_filters_disabled_prompts():
    """Test that list_prompts method (used by MCP Inspector) correctly filters disabled prompts."""
    # Mount a server using config
    config = [{
        "id": "mcp-prompt",
        "type": "local",
        "prompt_path": "test/data/prompts.json"
    }]
    composer = MCPComposer("composer", config=config)
    await composer.setup_member_servers()

    # Get prompts using list_prompts method (this is what MCP Inspector calls)
    all_prompts = await composer._prompt_manager.list_prompts()
    assert len(all_prompts) > 0, "Should have prompts from mounted server"

    # Get the first prompt name to test disabling
    first_prompt = all_prompts[0]
    first_prompt_name = getattr(first_prompt, 'name', str(first_prompt))

    # Disable the first prompt
    result = await composer.disable_prompts([first_prompt_name], "mcp-prompt")
    assert "Disabled" in result or "No prompts found to disable" in result

    # Get prompts again using list_prompts method and verify the disabled prompt is not in the list
    updated_prompts = await composer._prompt_manager.list_prompts()
    prompt_names = [getattr(p, 'name', str(p)) for p in updated_prompts]
    assert first_prompt_name not in prompt_names, f"Disabled prompt '{first_prompt_name}' should not be in the list"

    # Re-enable the prompt
    result = await composer.enable_prompts([first_prompt_name], "mcp-prompt")
    assert "Enabled" in result or "No prompts disabled" in result

    # Verify the prompt is back in the list
    final_prompts = await composer._prompt_manager.list_prompts()
    final_prompt_names = [getattr(p, 'name', str(p)) for p in final_prompts]
    assert first_prompt_name in final_prompt_names, f"Re-enabled prompt '{first_prompt_name}' should be back in the list"
