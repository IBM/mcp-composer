import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from mcp_composer.composer import MCPComposer
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_add_resource_template():
    """Test adding a resource template."""
    composer = MCPComposer("test-composer")

    resource_config = {
        "name": "test_resource",
        "description": "A test resource",
        "template": "Resource template"
    }

    result = await composer._resource_manager.create_resource_template(resource_config)
    assert "added successfully" in result

    # Test adding without required name
    result = await composer._resource_manager.create_resource_template({})
    assert "Error: 'name' is required" in result


@pytest.mark.asyncio
async def test_create_resource():
    """Test creating an actual resource."""
    composer = MCPComposer("test-composer")

    resource_config = {
        "name": "test_resource",
        "description": "A test resource",
        "content": "Test content",
        "uri": "resource://test/resource"
    }

    result = await composer._resource_manager.create_resource(resource_config)
    assert "created successfully" in result

    # Test creating without required name
    result = await composer._resource_manager.create_resource({})
    assert "Error: 'name' is required" in result

    # Test creating with minimal config
    minimal_config = {
        "name": "minimal_resource"
    }
    result = await composer._resource_manager.create_resource(minimal_config)
    assert "created successfully" in result


@pytest.mark.asyncio
async def test_list_resource_templates():
    """Test listing resource templates."""
    composer = MCPComposer("test-composer")

    # Add a test resource template first
    resource_config = {
        "name": "test_template",
        "description": "A test resource template",
        "template": "Resource template content"
    }
    await composer._resource_manager.create_resource_template(resource_config)

    result = await composer._resource_manager.list_resource_templates()
    assert len(result) >= 1
    assert any(r.name == "test_template" for r in result)


@pytest.mark.asyncio
async def test_list_resources():
    """Test listing all resources."""
    composer = MCPComposer("test-composer")

    # Add a test resource first
    resource_config = {
        "name": "test_resource",
        "description": "A test resource",
        "content": "Test content"
    }
    await composer._resource_manager.create_resource(resource_config)

    result = await composer._resource_manager.list_resources()
    assert len(result) >= 1
    assert any(r.name == "test_resource" for r in result)


@pytest.mark.asyncio
async def test_list_resources_via_composer():
    """Test listing resources through the composer interface."""
    composer = MCPComposer("test-composer")

    # Add a test resource first
    resource_config = {
        "name": "test_resource",
        "description": "A test resource",
        "content": "Test content"
    }
    await composer.create_resource(resource_config)

    result = await composer.list_resources()
    assert len(result) >= 1
    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert any(r["name"] == "test_resource" for r in result)


@pytest.mark.asyncio
async def test_list_resource_templates_via_composer():
    """Test listing resource templates through the composer interface."""
    composer = MCPComposer("test-composer")

    # Add a test resource template first
    resource_config = {
        "name": "test_template",
        "description": "A test resource template",
        "template": "Resource template content"
    }
    await composer.create_resource_template(resource_config)

    result = await composer.list_resource_templates()
    assert len(result) >= 1
    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert any(r["name"] == "test_template" for r in result)


@pytest.mark.asyncio
async def test_remove_resource():
    """Test removing a resource by name."""
    composer = MCPComposer("test-composer")

    # Add a test resource first
    resource_config = {
        "name": "test_resource_to_remove",
        "description": "A test resource to remove",
        "content": "Test content"
    }
    await composer._resource_manager.create_resource(resource_config)

    # Test removing the resource
    result = await composer._resource_manager.remove_resource("test_resource_to_remove")
    assert "removed" in result.lower()

    # Test removing non-existent resource
    result = await composer._resource_manager.remove_resource("non_existent_resource")
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_list_resources_per_server():
    """Test listing resources from a specific server."""
    composer = MCPComposer("test-composer")

    # Mock server manager to return a mock server
    mock_server = MagicMock()
    mock_server.server = MagicMock()

    # Create proper mock resources
    mock_resource1 = MagicMock()
    mock_resource1.name = "resource1"
    mock_resource1.description = "Test resource 1"

    mock_resource2 = MagicMock()
    mock_resource2.name = "resource2"
    mock_resource2.description = "Test resource 2"

    mock_server.server.get_resource_templates = AsyncMock(return_value={
        "resource1": mock_resource1,
        "resource2": mock_resource2
    })

    composer._server_manager.has_member_server = MagicMock(return_value=True)
    composer._server_manager.get_member = MagicMock(return_value=mock_server)

    result = await composer._resource_manager.list_resources_per_server("test-server")
    assert len(result) == 2
    assert result[0]["name"] == "resource1"
    assert result[1]["name"] == "resource2"
    assert result[0]["server_id"] == "test-server"


@pytest.mark.asyncio
async def test_list_resources_per_server_not_found():
    """Test listing resources from a non-existent server."""
    composer = MCPComposer("test-composer")
    composer._server_manager.has_member_server = MagicMock(return_value=False)

    result = await composer._resource_manager.list_resources_per_server("non-existent-server")
    assert len(result) == 0


@pytest.mark.asyncio
async def test_comprehensive_filtering():
    """Test the comprehensive filtering that works with both resources and templates."""
    composer = MCPComposer("test-composer")

    # Add a test resource
    resource_config = {
        "name": "test_resource_for_filtering",
        "description": "A test resource for filtering",
        "content": "Test content",
        "tags": ["api", "test", "filtering"]
    }
    await composer._resource_manager.create_resource(resource_config)

    # Add a test template
    template_config = {
        "name": "test_template_for_filtering",
        "description": "A test template for filtering",
        "template": "Template content",
        "tags": ["api", "template", "filtering"]
    }
    await composer._resource_manager.create_resource_template(template_config)

    # Test filtering by name
    result = await composer._resource_manager.filter_resources({"name": "test"})
    assert len(result) == 2  # Should find both resource and template
    names = [item["name"] for item in result]
    assert "test_resource_for_filtering" in names
    assert "test_template_for_filtering" in names

    # Test filtering by description
    result = await composer._resource_manager.filter_resources({"description": "filtering"})
    assert len(result) == 2  # Should find both resource and template

    # Test filtering by tags
    result = await composer._resource_manager.filter_resources({"tags": ["api"]})
    assert len(result) == 2  # Should find both resource and template

    # Test filtering by type
    result = await composer._resource_manager.filter_resources({"type": "resource"})
    assert len(result) == 1  # Should find only resource
    assert result[0]["type"] == "resource"

    result = await composer._resource_manager.filter_resources({"type": "template"})
    assert len(result) == 1  # Should find only template
    assert result[0]["type"] == "template"

    # Test filtering by URI pattern
    result = await composer._resource_manager.filter_resources({"uri_pattern": "test"})
    assert len(result) >= 1  # Should find items with "test" in URI


@pytest.mark.asyncio
async def test_filter_resources():
    """Test filtering resources by criteria."""
    composer = MCPComposer("test-composer")

    # Add test resources
    resource_configs = [
        {
            "name": "test_resource_1",
            "description": "First test resource",
            "tags": ["api", "test"]
        },
        {
            "name": "test_resource_2",
            "description": "Second test resource",
            "tags": ["api", "demo"]
        },
        {
            "name": "another_resource",
            "description": "Another resource",
            "tags": ["demo", "example"]
        }
    ]

    for config in resource_configs:
        await composer._resource_manager.create_resource_template(config)

    # Test filtering by name
    result = await composer._resource_manager.filter_resources({"name": "test"})
    assert len(result) == 2

    # Test filtering by description
    result = await composer._resource_manager.filter_resources({"description": "First"})
    assert len(result) == 1

    # Test filtering with no matches
    result = await composer._resource_manager.filter_resources({"name": "nonexistent"})
    assert len(result) == 0


@pytest.mark.asyncio
async def test_filter_with_empty_criteria():
    """Test filtering with empty or None criteria."""
    composer = MCPComposer("test-composer")

    # Add a test resource
    resource_config = {
        "name": "test_resource",
        "description": "A test resource"
    }
    await composer._resource_manager.create_resource_template(resource_config)

    # Test with empty criteria
    result = await composer._resource_manager.filter_resources({})
    assert len(result) == 1

    # Test with None criteria
    result = await composer._resource_manager.filter_resources({})
    assert len(result) == 1


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in various methods."""
    composer = MCPComposer("test-composer")

    # Test error handling in remove_prompt
    # Test with a non-existent prompt
    result = await composer._prompt_manager.remove_prompt("non_existent_prompt")
    assert "not found" in result.lower()

    # Test error handling in remove_resource
    # Test with a non-existent resource
    result = await composer._resource_manager.remove_resource("non_existent_resource")
    assert "not found" in result.lower()

@pytest.mark.asyncio
async def test_resource_vs_template_distinction():
    """Test that resource templates and actual resources are handled differently."""
    composer = MCPComposer("test-composer")

    # Add a resource template
    template_config = {
        "name": "test_template",
        "description": "A test template",
        "template": "Template content"
    }
    await composer._resource_manager.create_resource_template(template_config)

    # Add an actual resource
    resource_config = {
        "name": "test_resource",
        "description": "A test resource",
        "content": "Resource content",
        "uri": "resource://test/resource"
    }
    await composer._resource_manager.create_resource(resource_config)

    # List templates
    templates = await composer._resource_manager.list_resource_templates()
    template_names = [t.name for t in templates]
    assert "test_template" in template_names

    # List resources
    resources = await composer._resource_manager.list_resources()
    resource_names = [r.name for r in resources]
    assert "test_resource" in resource_names

    # Verify they're different
    assert "test_template" in template_names
    assert "test_resource" in resource_names
