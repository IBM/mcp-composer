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
    mock_resource1.uri = "resource://test/resource1"

    mock_resource2 = MagicMock()
    mock_resource2.name = "resource2"
    mock_resource2.description = "Test resource 2"
    mock_resource2.uri = "resource://test/resource2"

    # Create proper mock templates
    mock_template1 = MagicMock()
    mock_template1.name = "template1"
    mock_template1.description = "Test template 1"
    mock_template1.uri_template = "resource://test/template1"

    mock_template2 = MagicMock()
    mock_template2.name = "template2"
    mock_template2.description = "Test template 2"
    mock_template2.uri_template = "resource://test/template2"

    # Mock both resources and templates
    mock_server.server.get_resources = AsyncMock(return_value={
        "resource1": mock_resource1,
        "resource2": mock_resource2
    })
    mock_server.server.get_resource_templates = AsyncMock(return_value={
        "template1": mock_template1,
        "template2": mock_template2
    })

    composer._server_manager.has_member_server = MagicMock(return_value=True)
    composer._server_manager.get_member = MagicMock(return_value=mock_server)

    result = await composer._resource_manager.list_resources_per_server("test-server")
    assert len(result) == 4  # Should have 2 resources + 2 templates
    assert any(r["name"] == "resource1" and r["type"] == "resource" for r in result)
    assert any(r["name"] == "resource2" and r["type"] == "resource" for r in result)
    assert any(r["name"] == "template1" and r["type"] == "template" for r in result)
    assert any(r["name"] == "template2" and r["type"] == "template" for r in result)
    assert all(r["server_id"] == "test-server" for r in result)


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


@pytest.mark.asyncio
async def test_disable_resources():
    """Test disabling resources through composer interface."""
    composer = MCPComposer("test-composer")

    # Test disabling resources when no server is mounted
    result = await composer.disable_resources(["test_resource"], "test-server")
    assert "Failed to disable resources" in result or "No resources found to disable" in result


@pytest.mark.asyncio
async def test_enable_resources():
    """Test enabling resources through composer interface."""
    composer = MCPComposer("test-composer")

    # Test enabling resources when no server is mounted
    result = await composer.enable_resources(["test_resource"], "test-server")
    assert "Failed to enable resources" in result


@pytest.mark.asyncio
async def test_disable_and_enable_resources_integration():
    """Test the full disable/enable resource flow through composer interface."""
    composer = MCPComposer("test-composer")

    # Test the full flow when no server is mounted
    result = await composer.disable_resources(["test_resource"], "test-server")
    assert "Failed to disable resources" in result or "No resources found to disable" in result

    result = await composer.enable_resources(["test_resource"], "test-server")
    assert "Failed to enable resources" in result


@pytest.mark.asyncio
async def test_disable_resources_with_mounted_server():
    """Test disabling resources on an actually mounted server."""
    composer = MCPComposer("composer")

    # Mock the server manager to simulate a mounted server
    mock_server = MagicMock()
    mock_server.health_status = "OK"
    mock_server.disabled_resources = []
    mock_server.resources_description = {}

    composer._server_manager._member_servers = {"mcp-resource": mock_server}
    composer._server_manager.has_member_server = MagicMock(return_value=True)
    composer._server_manager.check_server_exist = MagicMock()

    # Mock the resource manager to return some resources
    mock_resource = MagicMock()
    mock_resource.name = "test_resource"
    composer._resource_manager.get_resources = AsyncMock(return_value={"mcp-resource_test_resource": mock_resource})

    # Test disabling resources
    result = await composer.disable_resources(["test_resource"], "mcp-resource")
    assert "Disabled" in result or "No resources found to disable" in result

    # Verify the resource was added to disabled_resources
    assert "mcp-resource_test_resource" in mock_server.disabled_resources


@pytest.mark.asyncio
async def test_enable_resources_with_mounted_server():
    """Test enabling resources on an actually mounted server."""
    composer = MCPComposer("composer")

    # Mock the server manager to simulate a mounted server with disabled resources
    mock_server = MagicMock()
    mock_server.health_status = "OK"
    mock_server.disabled_resources = ["mcp-resource_test_resource"]
    mock_server.resources_description = {}

    composer._server_manager._member_servers = {"mcp-resource": mock_server}
    composer._server_manager.has_member_server = MagicMock(return_value=True)
    composer._server_manager.check_server_exist = MagicMock()

    # Mock the resource manager to return resources
    mock_resource = MagicMock()
    mock_resource.name = "test_resource"

    # Mock the parent class methods that enable_resources uses
    with patch.object(composer._resource_manager.__class__.__bases__[0], 'get_resources', new_callable=AsyncMock) as mock_get_resources, \
         patch.object(composer._resource_manager.__class__.__bases__[0], 'get_resource_templates', new_callable=AsyncMock) as mock_get_templates:

        mock_get_resources.return_value = {"mcp-resource_test_resource": mock_resource}
        mock_get_templates.return_value = {}

        # Test enabling resources
        result = await composer.enable_resources(["test_resource"], "mcp-resource")
        assert "Enabled" in result or "No resources disabled" in result

        # Verify the resource was removed from disabled_resources
        assert "mcp-resource_test_resource" not in mock_server.disabled_resources


@pytest.mark.asyncio
async def test_disable_and_enable_resources_integration_with_mounted_server():
    """Test the full disable/enable resource flow with an actually mounted server."""
    composer = MCPComposer("composer")

    # Mock the server manager to simulate a mounted server
    mock_server = MagicMock()
    mock_server.health_status = "OK"
    mock_server.disabled_resources = []
    mock_server.resources_description = {}

    composer._server_manager._member_servers = {"mcp-resource": mock_server}
    composer._server_manager.has_member_server = MagicMock(return_value=True)
    composer._server_manager.check_server_exist = MagicMock()

    # Mock the resource manager to return some resources and templates
    mock_resource = MagicMock()
    mock_resource.name = "test_resource"
    mock_template = MagicMock()
    mock_template.name = "test_template"

    # Mock the parent class methods that enable_resources uses
    with patch.object(composer._resource_manager.__class__.__bases__[0], 'get_resources', new_callable=AsyncMock) as mock_get_resources, \
         patch.object(composer._resource_manager.__class__.__bases__[0], 'get_resource_templates', new_callable=AsyncMock) as mock_get_templates:

        mock_get_resources.return_value = {"mcp-resource_test_resource": mock_resource}
        mock_get_templates.return_value = {"mcp-resource_test_template": mock_template}

        # Test disabling resources
        result = await composer.disable_resources(["test_resource"], "mcp-resource")
        assert "Disabled" in result or "No resources found to disable" in result

        # Verify the resource was added to disabled_resources
        assert "mcp-resource_test_resource" in mock_server.disabled_resources

        # Test disabling resource templates
        result = await composer.disable_resources(["test_template"], "mcp-resource")
        assert "Disabled" in result or "No resources found to disable" in result

        # Verify the template was added to disabled_resources
        assert "mcp-resource_test_template" in mock_server.disabled_resources

        # Test enabling resources
        result = await composer.enable_resources(["test_resource", "test_template"], "mcp-resource")
        assert "Enabled" in result or "No resources disabled" in result

        # Verify the resources were removed from disabled_resources
        assert "mcp-resource_test_resource" not in mock_server.disabled_resources
        assert "mcp-resource_test_template" not in mock_server.disabled_resources


@pytest.mark.asyncio
async def test_disable_resources_handles_both_types():
    """Test that disable_resources handles both Resources and Resource Templates."""
    composer = MCPComposer("composer")

    # Mock the server manager to simulate a mounted server
    mock_server = MagicMock()
    mock_server.health_status = "OK"
    mock_server.disabled_resources = []
    mock_server.resources_description = {}

    composer._server_manager._member_servers = {"mcp-resource": mock_server}
    composer._server_manager.has_member_server = MagicMock(return_value=True)
    composer._server_manager.check_server_exist = MagicMock()

    # Mock the resource manager to return both resources and templates
    mock_resource = MagicMock()
    mock_resource.name = "test_resource"
    mock_template = MagicMock()
    mock_template.name = "test_template"

    composer._resource_manager.get_resources = AsyncMock(return_value={"mcp-resource_test_resource": mock_resource})
    composer._resource_manager.get_resource_templates = AsyncMock(return_value={"mcp-resource_test_template": mock_template})

    # Test disabling both a resource and a template
    result = await composer.disable_resources(["test_resource", "test_template"], "mcp-resource")
    assert "Disabled" in result or "No resources found to disable" in result

    # Verify both were added to disabled_resources
    assert "mcp-resource_test_resource" in mock_server.disabled_resources
    assert "mcp-resource_test_template" in mock_server.disabled_resources
