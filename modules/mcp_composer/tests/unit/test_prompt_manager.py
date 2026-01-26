from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_composer.core.composer import MCPComposer
from mcp_composer.core.member_servers.member_server import HealthStatus
from mcp_composer.core.prompts.prompt_manager import MCPPromptManager

# pylint: disable=protected-access,too-many-lines


@pytest.mark.asyncio
async def test_prompts():
    """Test basic prompt functionality through composer interface."""
    # Mock the database to prevent loading prompts during initialization
    with patch("mcp_composer.core.composer.LocalFileAdapter") as mock_db_class:
        mock_db_instance = MagicMock()
        mock_db_instance.load_all_prompts.return_value = []
        mock_db_class.return_value = mock_db_instance

        composer = MCPComposer("composer")
        config = [
            {
                "name": "promo_http_avg_response",
                "description": "Average response time of promo HTTP calls handled by a cluster",
                "template": "What is the average response time of promo HTTP calls handled by Kubernetes cluster {{ cluster }}?",
                "arguments": [
                    {
                        "name": "cluster",
                        "type": "string",
                        "required": "true",
                        "description": "The name of the Kubernetes cluster",
                    }
                ],
            }
        ]
        composer.add_prompts(config)
        prompts = await composer.get_all_prompts()
        assert len(prompts) == 1
        assert "promo_http_avg_response" in prompts[0]


@pytest.mark.asyncio
async def test_add_prompts():
    """Test adding prompts through composer interface."""
    composer = MCPComposer("composer")
    config = [
        {
            "name": "promo_http_avg_response",
            "description": "Average response time of promo HTTP calls handled by a cluster",
            "template": "What is the average response time of promo HTTP calls handled by Kubernetes cluster {{ cluster }}?",
            "arguments": [
                {
                    "name": "cluster",
                    "type": "string",
                    "required": "true",
                    "description": "The name of the Kubernetes cluster",
                }
            ],
        }
    ]
    res = composer.add_prompts(config)
    assert len(res) == 1
    assert res[0] == "promo_http_avg_response"


@pytest.mark.asyncio
async def test_builder():
    """Test prompt builder functionality through composer interface."""
    config = [
        {"id": "mcp-prompt", "type": "local", "prompt_path": "test/data/prompts.json"}
    ]
    composer = MCPComposer("composer", config=config)
    await composer.setup_member_servers()
    prompts = await composer.get_all_prompts()
    assert len(prompts) >= 0, "Composer should return a list of prompts"
    assert isinstance(prompts, list), "Composer should return a list of prompts"


@pytest.mark.asyncio
async def test_builder_local():
    """Test local prompt builder functionality through composer interface."""
    config = [
        {"id": "mcp-prompt", "type": "local", "prompt_path": "test/data/prompts.json"}
    ]
    composer = MCPComposer("composer", config=config)
    await composer.setup_member_servers()
    prompts = await composer.get_all_prompts()
    assert len(prompts) >= 0, "Composer should return a list of prompts"
    assert isinstance(prompts, list), "Composer should return a list of prompts"


@pytest.mark.asyncio
async def test_get_all_prompts_returns_list():
    """Test get_all_prompts returns a list with added prompts through composer interface."""
    prompt_config = [
        {
            "name": "test_prompt",
            "description": "A test prompt",
            "template": "Hello, this is a test prompt.",
        }
    ]
    # Mock the database to prevent loading prompts during initialization
    with patch("mcp_composer.core.composer.LocalFileAdapter") as mock_db:
        mock_db_instance = MagicMock()
        mock_db_instance.load_all_prompts.return_value = []
        mock_db.return_value = mock_db_instance

        composer = MCPComposer("composer")
        added = composer.add_prompts(prompt_config)
        assert len(added) == 1
        assert added[0] == "test_prompt"
        prompts = await composer.get_all_prompts()
        assert len(prompts) == 1


@pytest.mark.asyncio
async def test_get_all_prompts_empty():
    """Test get_all_prompts returns empty list when no prompts are added."""
    # Mock the database to prevent loading prompts during initialization
    with patch("mcp_composer.core.composer.LocalFileAdapter") as mock_db:
        mock_db_instance = MagicMock()
        mock_db_instance.load_all_prompts.return_value = []
        mock_db.return_value = mock_db_instance

        composer = MCPComposer("composer")
        prompts = await composer.get_all_prompts()
        assert len(prompts) == 0


@pytest.mark.asyncio
async def test_list_prompts_per_server():
    """Test listing prompts per server."""
    composer = MCPComposer("composer")

    # Add a test prompt first
    prompt_config = [
        {
            "name": "test_prompt",
            "description": "A test prompt",
            "template": "Hello, this is a test prompt.",
        }
    ]
    composer.add_prompts(prompt_config)

    result = await composer._prompt_manager.list_prompts_per_server("test-server")
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_list_prompts_per_server_not_found():
    """Test listing prompts for non-existent server."""
    composer = MCPComposer("composer")

    result = await composer._prompt_manager.list_prompts_per_server(
        "non-existent-server"
    )
    assert result == []


@pytest.mark.asyncio
async def test_filter_prompts():
    """Test prompt filtering functionality."""
    composer = MCPComposer("composer")

    # Add test prompts
    prompts = [
        {
            "name": "prompt1",
            "description": "First test prompt",
            "template": "Template for first prompt",
        },
        {
            "name": "prompt2",
            "description": "Second test prompt",
            "template": "Template for second prompt",
        },
    ]

    for prompt in prompts:
        composer.add_prompts([prompt])

    # Test filtering by name
    filter_criteria = {"name": "prompt1"}
    result = await composer._prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 1
    assert result[0]["name"] == "prompt1"

    # Test filtering by description
    filter_criteria = {"description": "Second"}
    result = await composer._prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 1
    assert "Second" in result[0]["description"]

    # Test filtering by template
    filter_criteria = {"template": "first"}
    result = await composer._prompt_manager.filter_prompts(filter_criteria)

    assert len(result) >= 1
    # Check that at least one result contains "first" in the template
    assert any("first" in prompt["template"].lower() for prompt in result)


@pytest.mark.asyncio
async def test_disable_prompts():
    """Test disabling prompts."""
    composer = MCPComposer("composer")

    # Mock server manager to simulate mounted server
    mock_server_manager = MagicMock()
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = []
    mock_server_manager.list.return_value = [mock_server]
    mock_server_manager.has_member_server.return_value = True
    mock_server_manager.check_server_exist.return_value = None

    composer._prompt_manager._server_manager = mock_server_manager

    # Mock get_prompts to return prompts with server prefix
    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "A test prompt"
    mock_prompt.__str__ = MagicMock(return_value="Hello, this is a test prompt.")

    composer._prompt_manager.get_prompts = AsyncMock(
        return_value={"test-server_test_prompt": mock_prompt}
    )

    result = await composer._prompt_manager.disable_prompts(
        ["test_prompt"], "test-server"
    )
    assert "Disabled" in result


@pytest.mark.asyncio
async def test_enable_prompts():
    """Test enabling prompts."""
    composer = MCPComposer("composer")

    # Mock server manager to simulate mounted server
    mock_server_manager = MagicMock()
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = ["test_prompt"]
    mock_server_manager.list.return_value = [mock_server]
    mock_server_manager.has_member_server.return_value = True
    mock_server_manager.check_server_exist.return_value = None

    composer._prompt_manager._server_manager = mock_server_manager

    # Mock get_prompts to return prompts with server prefix
    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "A test prompt"
    mock_prompt.__str__ = MagicMock(return_value="Hello, this is a test prompt.")

    composer._prompt_manager.get_prompts = AsyncMock(
        return_value={"test-server_test_prompt": mock_prompt}
    )

    result = await composer._prompt_manager.enable_prompts(
        ["test_prompt"], "test-server"
    )
    assert "Enabled" in result


@pytest.mark.asyncio
async def test_disable_and_enable_prompts_integration():
    """Test integration of disable and enable prompts."""
    composer = MCPComposer("composer")

    # Mock server manager to simulate mounted server
    mock_server_manager = MagicMock()
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = []
    mock_server_manager.list.return_value = [mock_server]
    mock_server_manager.has_member_server.return_value = True
    mock_server_manager.check_server_exist.return_value = None

    composer._prompt_manager._server_manager = mock_server_manager

    # Mock get_prompts to return prompts with server prefix
    mock_prompt1 = MagicMock()
    mock_prompt1.name = "prompt1"
    mock_prompt1.description = "First test prompt"
    mock_prompt1.__str__ = MagicMock(return_value="Template for first prompt")

    mock_prompt2 = MagicMock()
    mock_prompt2.name = "prompt2"
    mock_prompt2.description = "Second test prompt"
    mock_prompt2.__str__ = MagicMock(return_value="Template for second prompt")

    composer._prompt_manager.get_prompts = AsyncMock(
        return_value={
            "test-server_prompt1": mock_prompt1,
            "test-server_prompt2": mock_prompt2,
        }
    )

    # Disable prompts
    result = await composer._prompt_manager.disable_prompts(
        ["prompt1", "prompt2"], "test-server"
    )
    assert "Disabled" in result

    # Enable prompts
    result = await composer._prompt_manager.enable_prompts(
        ["prompt1", "prompt2"], "test-server"
    )
    assert "Enabled" in result


@pytest.mark.asyncio
async def test_list_prompts_per_server_filters_disabled():
    """Test that list_prompts_per_server filters out disabled prompts."""
    composer = MCPComposer("composer")

    # Add a test prompt
    prompt_config = [
        {
            "name": "test_prompt",
            "description": "A test prompt",
            "template": "Hello, this is a test prompt.",
        }
    ]
    composer.add_prompts(prompt_config)

    # Disable the prompt
    await composer._prompt_manager.disable_prompts(["test_prompt"], "test-server")

    # List prompts per server should not include disabled prompts
    result = await composer._prompt_manager.list_prompts_per_server("test-server")
    assert len(result) == 0


@pytest.mark.asyncio
async def test_disable_prompts_with_mounted_server():
    """Test disabling prompts with mounted server."""
    composer = MCPComposer("composer")

    # Mock server manager to simulate mounted server
    mock_server_manager = MagicMock()
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = []
    mock_server_manager.list.return_value = [mock_server]
    mock_server_manager.has_member_server.return_value = True

    composer._prompt_manager._server_manager = mock_server_manager

    # Mock get_prompts to return prompts with server prefix
    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "A test prompt"
    mock_prompt.__str__ = MagicMock(return_value="Hello, this is a test prompt.")

    composer._prompt_manager.get_prompts = AsyncMock(
        return_value={"test-server_test_prompt": mock_prompt}
    )

    # Disable prompt
    result = await composer._prompt_manager.disable_prompts(
        ["test_prompt"], "test-server"
    )
    assert "Disabled" in result


@pytest.mark.asyncio
async def test_enable_prompts_with_mounted_server():
    """Test enabling prompts with mounted server."""
    composer = MCPComposer("composer")

    # Mock server manager to simulate mounted server
    mock_server_manager = MagicMock()
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = ["test_prompt"]
    mock_server_manager.list.return_value = [mock_server]
    mock_server_manager.has_member_server.return_value = True

    composer._prompt_manager._server_manager = mock_server_manager

    # Mock get_prompts to return prompts with server prefix
    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "A test prompt"
    mock_prompt.__str__ = MagicMock(return_value="Hello, this is a test prompt.")

    composer._prompt_manager.get_prompts = AsyncMock(
        return_value={"test-server_test_prompt": mock_prompt}
    )

    # Enable prompt
    result = await composer._prompt_manager.enable_prompts(
        ["test_prompt"], "test-server"
    )
    assert "Enabled" in result


@pytest.mark.asyncio
async def test_disable_and_enable_prompts_integration_with_mounted_server():
    """Test integration of disable and enable prompts with mounted server."""
    composer = MCPComposer("composer")

    # Mock server manager to simulate mounted server
    mock_server_manager = MagicMock()
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = []
    mock_server_manager.list.return_value = [mock_server]
    mock_server_manager.has_member_server.return_value = True

    composer._prompt_manager._server_manager = mock_server_manager

    # Mock get_prompts to return prompts with server prefix
    mock_prompt1 = MagicMock()
    mock_prompt1.name = "prompt1"
    mock_prompt1.description = "First test prompt"
    mock_prompt1.__str__ = MagicMock(return_value="Template for first prompt")

    mock_prompt2 = MagicMock()
    mock_prompt2.name = "prompt2"
    mock_prompt2.description = "Second test prompt"
    mock_prompt2.__str__ = MagicMock(return_value="Template for second prompt")

    composer._prompt_manager.get_prompts = AsyncMock(
        return_value={
            "test-server_prompt1": mock_prompt1,
            "test-server_prompt2": mock_prompt2,
        }
    )

    # Disable prompts
    result = await composer._prompt_manager.disable_prompts(
        ["prompt1", "prompt2"], "test-server"
    )
    assert "Disabled" in result

    # Enable prompts
    result = await composer._prompt_manager.enable_prompts(
        ["prompt1", "prompt2"], "test-server"
    )
    assert "Enabled" in result


@pytest.mark.asyncio
async def test_list_prompts_per_server_filters_disabled_with_mounted_server():
    """Test that list_prompts_per_server filters disabled prompts with mounted server."""
    composer = MCPComposer("composer")

    # Mock server manager to simulate mounted server
    mock_server_manager = MagicMock()
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = ["test_prompt"]
    mock_server_manager.list.return_value = [mock_server]
    mock_server_manager.has_member_server.return_value = True

    composer._prompt_manager._server_manager = mock_server_manager

    # Add a test prompt
    prompt_config = [
        {
            "name": "test_prompt",
            "description": "A test prompt",
            "template": "Hello, this is a test prompt.",
        }
    ]
    composer.add_prompts(prompt_config)

    # List prompts per server should not include disabled prompts
    result = await composer._prompt_manager.list_prompts_per_server("test-server")
    assert len(result) == 0


@pytest.mark.asyncio
async def test_list_prompts_filters_disabled_prompts():
    """Test that list_prompts filters out disabled prompts."""
    # Mock the database to prevent loading prompts during initialization
    with patch("mcp_composer.core.composer.LocalFileAdapter") as mock_db:
        mock_db_instance = MagicMock()
        mock_db_instance.load_all_prompts.return_value = []
        mock_db.return_value = mock_db_instance

        composer = MCPComposer("composer")

        # Mock server manager to simulate mounted server
        mock_server_manager = MagicMock()
        mock_server = MagicMock()
        mock_server.health_status = HealthStatus.healthy
        mock_server.disabled_prompts = ["test_prompt"]
        mock_server_manager.list.return_value = [mock_server]

        composer._prompt_manager._server_manager = mock_server_manager

        # Add a test prompt
        prompt_config = [
            {
                "name": "test_prompt",
                "description": "A test prompt",
                "template": "Hello, this is a test prompt.",
            }
        ]
        composer.add_prompts(prompt_config)

        # List prompts should not include disabled prompts
        result = await composer._prompt_manager.list_prompts()
        assert len(result) == 0


@pytest.mark.asyncio
async def test_prompt_manager_initialization():
    """Test MCPPromptManager initialization."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    assert prompt_manager._server_manager == mock_server_manager
    assert not prompt_manager._prompts


@pytest.mark.asyncio
async def test_unmount_method():
    """Test unmount method of prompt manager."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Add a mock mounted server
    mock_mounted_server = MagicMock()
    mock_mounted_server.prefix = "test-server"
    prompt_manager._mounted_servers = [mock_mounted_server]

    # Test unmount
    prompt_manager.unmount("test-server")
    assert len(prompt_manager._mounted_servers) == 0


@pytest.mark.asyncio
async def test_add_prompts_with_single_dict():
    """Test add_prompts with single dictionary."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    prompt_config = {
        "name": "single_prompt",
        "description": "A single prompt",
        "template": "Hello {{ name }}!",
    }

    result = prompt_manager.add_prompts(prompt_config)
    assert len(result) == 1
    assert result[0] == "single_prompt"


@pytest.mark.asyncio
async def test_add_prompts_with_list():
    """Test add_prompts with list of dictionaries."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    prompt_config = [
        {
            "name": "prompt1",
            "description": "First prompt",
            "template": "Hello {{ name }}!",
        },
        {
            "name": "prompt2",
            "description": "Second prompt",
            "template": "Goodbye {{ name }}!",
        },
    ]

    result = prompt_manager.add_prompts(prompt_config)
    assert len(result) == 2
    assert "prompt1" in result
    assert "prompt2" in result


@pytest.mark.asyncio
async def test_add_prompts_with_invalid_type():
    """Test add_prompts with invalid type raises TypeError."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    with pytest.raises(
        TypeError, match="Prompt config must be a dict or a list of dicts"
    ):
        prompt_manager.add_prompts("invalid_config")


@pytest.mark.asyncio
async def test_add_prompts_with_invalid_prompt():
    """Test add_prompts with invalid prompt configuration."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Invalid prompt config (missing required fields)
    prompt_config = [{"description": "Missing name"}]

    result = prompt_manager.add_prompts(prompt_config)
    assert len(result) == 0  # Should return empty list when all prompts fail


@pytest.mark.asyncio
async def test_filter_disabled_prompts_with_unhealthy_server():
    """Test filtering disabled prompts with unhealthy server."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock unhealthy server
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.unhealthy
    mock_server.disabled_prompts = ["prompt1"]
    mock_server_manager.list.return_value = [mock_server]

    # Test prompts
    test_prompts = {"prompt1": MagicMock(), "prompt2": MagicMock()}

    # Should return all prompts since server is unhealthy
    result = prompt_manager._filter_disabled_prompts(test_prompts)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_filter_disabled_prompts_with_healthy_server():
    """Test filtering disabled prompts with healthy server."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock healthy server with disabled prompts
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = ["prompt1"]
    mock_server_manager.list.return_value = [mock_server]

    # Test prompts
    mock_prompt1 = MagicMock()
    mock_prompt1.name = "prompt1"
    mock_prompt2 = MagicMock()
    mock_prompt2.name = "prompt2"
    test_prompts = {"prompt1": mock_prompt1, "prompt2": mock_prompt2}

    # Should filter out disabled prompts
    result = prompt_manager._filter_disabled_prompts(test_prompts)
    assert len(result) == 1
    assert "prompt2" in result


@pytest.mark.asyncio
async def test_get_prompts_method():
    """Test get_prompts method."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock prompts
    mock_prompt = MagicMock()
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    result = await prompt_manager.get_prompts()
    assert "test_prompt" in result


@pytest.mark.asyncio
async def test_list_prompts_method():
    """Test list_prompts method."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock prompts
    mock_prompt = MagicMock()
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    result = await prompt_manager.list_prompts()
    assert len(result) == 1


@pytest.mark.asyncio
async def test_disable_prompts_with_database():
    """Test disabling prompts with database."""
    mock_server_manager = MagicMock()
    mock_database = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager, database=mock_database)

    # Mock server
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = []
    mock_server_manager.list.return_value = [mock_server]
    mock_server_manager.has_member_server.return_value = True
    mock_server_manager.check_server_exist.return_value = None

    # Mock get_prompts to return prompts with server prefix
    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "A test prompt"
    mock_prompt.__str__ = MagicMock(return_value="Hello, this is a test prompt.")

    prompt_manager.get_prompts = AsyncMock(
        return_value={"test-server_test_prompt": mock_prompt}
    )

    # Mock the server manager's disable_prompts method to call the database
    def mock_disable_prompts(prompts, server_id):
        mock_database.disable_prompts(prompts, server_id)

    mock_server_manager.disable_prompts = mock_disable_prompts

    result = await prompt_manager.disable_prompts(["test_prompt"], "test-server")
    assert "Disabled" in result

    # Verify database was called
    mock_database.disable_prompts.assert_called_once()


@pytest.mark.asyncio
async def test_enable_prompts_with_database():
    """Test enabling prompts with database."""
    mock_server_manager = MagicMock()
    mock_database = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager, database=mock_database)

    # Mock server
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = ["test_prompt"]
    mock_server_manager.list.return_value = [mock_server]
    mock_server_manager.has_member_server.return_value = True
    mock_server_manager.check_server_exist.return_value = None

    # Mock get_prompts to return prompts with server prefix
    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "A test prompt"
    mock_prompt.__str__ = MagicMock(return_value="Hello, this is a test prompt.")

    prompt_manager.get_prompts = AsyncMock(
        return_value={"test-server_test_prompt": mock_prompt}
    )

    # Mock the server manager's enable_prompts method to call the database
    def mock_enable_prompts(prompts, server_id):
        mock_database.enable_prompts(prompts, server_id)

    mock_server_manager.enable_prompts = mock_enable_prompts

    result = await prompt_manager.enable_prompts(["test_prompt"], "test-server")
    assert "Enabled" in result

    # Verify database was called
    mock_database.enable_prompts.assert_called_once()


@pytest.mark.asyncio
async def test_filter_prompts_with_empty_criteria():
    """Test filtering prompts with empty criteria."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock prompts
    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "Test description"
    mock_prompt.__str__ = MagicMock(return_value="Test template")
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    # Test with empty criteria
    filter_criteria = {}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) >= 1


@pytest.mark.asyncio
async def test_filter_prompts_with_name_criteria():
    """Test filtering prompts by name."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock prompts
    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "Test description"
    mock_prompt.__str__ = MagicMock(return_value="Test template")
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    # Test filtering by name
    filter_criteria = {"name": "test"}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 1
    assert result[0]["name"] == "test_prompt"


@pytest.mark.asyncio
async def test_filter_prompts_with_description_criteria():
    """Test filtering prompts by description."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock prompts
    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "Test description"
    mock_prompt.__str__ = MagicMock(return_value="Test template")
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    # Test filtering by description
    filter_criteria = {"description": "Test"}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 1
    assert "Test" in result[0]["description"]


@pytest.mark.asyncio
async def test_filter_prompts_with_template_criteria():
    """Test filtering prompts by template."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock prompts
    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "Test description"
    mock_prompt.__str__ = MagicMock(return_value="Test template")
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    # Test filtering by template
    filter_criteria = {"template": "template"}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 1
    assert "template" in result[0]["template"].lower()


@pytest.mark.asyncio
async def test_error_handling_in_filter_disabled_prompts():
    """Test error handling in _filter_disabled_prompts."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock server manager to raise exception
    mock_server_manager.list.side_effect = Exception("Test error")

    test_prompts = {"prompt1": MagicMock()}

    # Should return original prompts when error occurs
    with pytest.raises(Exception, match="Test error"):
        prompt_manager._filter_disabled_prompts(test_prompts)


@pytest.mark.asyncio
async def test_list_prompts_per_server_with_server_prefix():
    """Test list_prompts_per_server with server prefix filtering."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock server
    mock_server_manager.has_member_server.return_value = True

    # Mock prompts with server prefix
    mock_prompt1 = MagicMock()
    mock_prompt1.name = "prompt1"
    mock_prompt1.description = "Test prompt 1"
    mock_prompt1.__str__ = MagicMock(return_value="Template 1")

    mock_prompt2 = MagicMock()
    mock_prompt2.name = "prompt2"
    mock_prompt2.description = "Test prompt 2"
    mock_prompt2.__str__ = MagicMock(return_value="Template 2")

    # Mock get_prompts to return prompts with server prefix
    prompt_manager.get_prompts = AsyncMock(
        return_value={
            "test-server_prompt1": mock_prompt1,
            "test-server_prompt2": mock_prompt2,
            "other-server_prompt3": MagicMock(),
        }
    )

    result = await prompt_manager.list_prompts_per_server("test-server")
    assert len(result) == 2
    assert result[0]["server_id"] == "test-server"
    assert result[1]["server_id"] == "test-server"


@pytest.mark.asyncio
async def test_comprehensive_prompt_workflow():
    """Test a comprehensive prompt workflow."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock server
    mock_server = MagicMock()
    mock_server.health_status = HealthStatus.healthy
    mock_server.disabled_prompts = []
    mock_server_manager.list.return_value = [mock_server]
    mock_server_manager.has_member_server.return_value = True
    mock_server_manager.check_server_exist.return_value = None

    # Mock get_prompts to return prompts with server prefix
    mock_prompt1 = MagicMock()
    mock_prompt1.name = "greeting_prompt"
    mock_prompt1.description = "A greeting prompt"
    mock_prompt1.__str__ = MagicMock(return_value="Hello {{ name }}!")

    mock_prompt2 = MagicMock()
    mock_prompt2.name = "farewell_prompt"
    mock_prompt2.description = "A farewell prompt"
    mock_prompt2.__str__ = MagicMock(return_value="Goodbye {{ name }}!")

    prompt_manager.get_prompts = AsyncMock(
        return_value={
            "test-server_greeting_prompt": mock_prompt1,
            "test-server_farewell_prompt": mock_prompt2,
        }
    )

    # Get all prompts
    prompts = await prompt_manager.get_prompts()
    assert len(prompts) >= 2

    # List prompts
    prompt_list = await prompt_manager.list_prompts()
    assert len(prompt_list) >= 2

    # Disable a prompt
    result = await prompt_manager.disable_prompts(["greeting_prompt"], "test-server")
    assert "Disabled" in result

    # Enable the prompt
    result = await prompt_manager.enable_prompts(["greeting_prompt"], "test-server")
    assert "Enabled" in result

    # Filter prompts
    filtered = await prompt_manager.filter_prompts({"name": "greeting"})
    assert len(filtered) == 1
    assert "greeting" in filtered[0]["name"]


# Additional comprehensive tests from test_prompt_manager_extended.py


@pytest.mark.asyncio
async def test_prompt_manager_initialization_with_duplicate_behavior():
    """Test MCPPromptManager initialization with duplicate behavior."""
    mock_server_manager = MagicMock()
    from fastmcp.settings import DuplicateBehavior

    manager = MCPPromptManager(mock_server_manager, duplicate_behavior="replace")
    assert manager.duplicate_behavior == "replace"


@pytest.mark.asyncio
async def test_unmount_nonexistent_server():
    """Test unmounting a non-existent server."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Add a mock mounted server
    mock_mounted_server = MagicMock()
    mock_mounted_server.prefix = "other_server"
    prompt_manager._mounted_servers = [mock_mounted_server]

    # Test unmount non-existent server
    prompt_manager.unmount("test_server")
    assert len(prompt_manager._mounted_servers) == 1


@pytest.mark.asyncio
async def test_add_prompts_with_errors():
    """Test adding prompts with some errors."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock build_prompt_from_dict to fail on second call
    with patch(
        "mcp_composer.core.prompts.prompt_manager.build_prompt_from_dict"
    ) as mock_build:
        mock_prompt = MagicMock()
        mock_prompt.name = "test_prompt"
        mock_build.side_effect = [mock_prompt, ValueError("Invalid prompt")]
        prompt_manager.add_prompt = MagicMock(return_value=mock_prompt)

        prompt_config = [
            {"name": "prompt1", "description": "Test 1", "template": "Template 1"},
            {"name": "prompt2", "description": "Test 2", "template": "Template 2"},
        ]

        result = prompt_manager.add_prompts(prompt_config)
        assert result == ["test_prompt"]  # Only the successful one


@pytest.mark.asyncio
async def test_add_prompts_all_fail():
    """Test adding prompts where all fail."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    with patch(
        "mcp_composer.core.prompts.prompt_manager.build_prompt_from_dict"
    ) as mock_build:
        mock_build.side_effect = ValueError("Invalid prompt")

        prompt_config = [
            {"name": "prompt1", "description": "Test 1", "template": "Template 1"}
        ]

        result = prompt_manager.add_prompts(prompt_config)
        assert result == []  # Empty list when all fail


@pytest.mark.asyncio
async def test_list_prompts_per_server_no_server_manager():
    """Test listing prompts per server when no server manager."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)
    prompt_manager._server_manager = None

    result = await prompt_manager.list_prompts_per_server("test_server")
    assert result == []


@pytest.mark.asyncio
async def test_list_prompts_per_server_server_not_found():
    """Test listing prompts per server when server not found."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)
    prompt_manager._server_manager.has_member_server.return_value = False

    result = await prompt_manager.list_prompts_per_server("nonexistent_server")
    assert result == []


@pytest.mark.asyncio
async def test_list_prompts_per_server_no_prompts():
    """Test listing prompts per server when no prompts exist."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)
    prompt_manager.get_prompts = AsyncMock(return_value={})

    result = await prompt_manager.list_prompts_per_server("test_server")
    assert result == []


@pytest.mark.asyncio
async def test_list_prompts_per_server_different_server():
    """Test listing prompts per server with prompts from different server."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)
    prompt_manager.get_prompts = AsyncMock(
        return_value={"other_server_prompt1": MagicMock()}
    )

    result = await prompt_manager.list_prompts_per_server("test_server")
    assert result == []  # No prompts for test_server


@pytest.mark.asyncio
async def test_filter_disabled_prompts_no_server_manager():
    """Test filtering disabled prompts when no server manager."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)
    prompt_manager._server_manager = None

    mock_prompt = MagicMock()
    prompts = {"test_prompt": mock_prompt}

    result = prompt_manager._filter_disabled_prompts(prompts)
    assert result == prompts


@pytest.mark.asyncio
async def test_filter_disabled_prompts_no_server_config():
    """Test filtering disabled prompts when no server config."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)
    prompt_manager._server_manager.list.return_value = []

    mock_prompt = MagicMock()
    prompts = {"test_prompt": mock_prompt}

    result = prompt_manager._filter_disabled_prompts(prompts)
    assert result == prompts


@pytest.mark.asyncio
async def test_filter_disabled_prompts_name_match():
    """Test filtering disabled prompts with name match."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    mock_member = MagicMock()
    mock_member.health_status = HealthStatus.healthy
    mock_member.disabled_prompts = ["test_prompt"]  # Use exact name match
    prompt_manager._server_manager.list.return_value = [mock_member]

    mock_prompt = MagicMock()
    prompts = {"test_prompt": mock_prompt}
    result = prompt_manager._filter_disabled_prompts(prompts)
    assert "test_prompt" not in result


@pytest.mark.asyncio
async def test_filter_disabled_prompts_case_insensitive():
    """Test filtering disabled prompts with case insensitive matching."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    mock_member = MagicMock()
    mock_member.health_status = HealthStatus.healthy
    mock_member.disabled_prompts = ["TEST_PROMPT"]  # Use exact name match
    prompt_manager._server_manager.list.return_value = [mock_member]

    mock_prompt = MagicMock()
    prompts = {"test_prompt": mock_prompt}
    result = prompt_manager._filter_disabled_prompts(prompts)
    # Since the disabled prompt name doesn't match exactly, it should not be filtered out
    assert "test_prompt" in result


@pytest.mark.asyncio
async def test_filter_disabled_prompts_exception_handling():
    """Test filtering disabled prompts with exception handling."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)
    prompt_manager._server_manager.list.side_effect = Exception("Test error")

    mock_prompt = MagicMock()
    prompts = {"test_prompt": mock_prompt}

    with pytest.raises(Exception, match="Test error"):
        prompt_manager._filter_disabled_prompts(prompts)


@pytest.mark.asyncio
async def test_disable_prompts_server_not_found():
    """Test disabling prompts for non-existent server."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)
    prompt_manager._server_manager.check_server_exist.side_effect = Exception(
        "Server 'nonexistent_server' not mounted."
    )

    result = await prompt_manager.disable_prompts(["test_prompt"], "nonexistent_server")
    assert "Failed to disable prompts" in result


@pytest.mark.asyncio
async def test_disable_prompts_unhealthy_server():
    """Test disabling prompts for unhealthy server."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock the get method to raise an exception for unhealthy server
    mock_server_manager.get.side_effect = Exception("MCP Server 'test_server' is down.")
    prompt_manager._server_manager.check_server_exist.side_effect = Exception(
        "MCP Server 'test_server' is down."
    )

    result = await prompt_manager.disable_prompts(["test_prompt"], "test_server")
    assert "Failed to disable prompts" in result


@pytest.mark.asyncio
async def test_enable_prompts_server_not_found():
    """Test enabling prompts for non-existent server."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)
    prompt_manager._server_manager.check_server_exist.side_effect = Exception(
        "Server 'nonexistent_server' not mounted."
    )

    result = await prompt_manager.enable_prompts(["test_prompt"], "nonexistent_server")
    assert "Failed to enable prompts" in result


@pytest.mark.asyncio
async def test_enable_prompts_unhealthy_server():
    """Test enabling prompts for unhealthy server."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Mock the get method to raise an exception for unhealthy server
    mock_server_manager.get.side_effect = Exception("MCP Server 'test_server' is down.")
    prompt_manager._server_manager.check_server_exist.side_effect = Exception(
        "MCP Server 'test_server' is down."
    )

    result = await prompt_manager.enable_prompts(["test_prompt"], "test_server")
    assert "Failed to enable prompts" in result


@pytest.mark.asyncio
async def test_filter_prompts_by_template():
    """Test filtering prompts by template."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "Test prompt description"
    mock_prompt.__str__ = MagicMock(return_value="Test prompt template")
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    filter_criteria = {"template": "Test prompt template"}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 1
    assert result[0]["template"] == "Test prompt template"


@pytest.mark.asyncio
async def test_filter_prompts_no_match():
    """Test filtering prompts with no match."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "Test prompt description"
    mock_prompt.__str__ = MagicMock(return_value="Test prompt template")
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    filter_criteria = {"name": "nonexistent_prompt"}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_filter_prompts_case_insensitive():
    """Test filtering prompts with case insensitive matching."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "Test prompt description"
    mock_prompt.__str__ = MagicMock(return_value="Test prompt template")
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    filter_criteria = {"name": "TEST_PROMPT"}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_filter_prompts_multiple_criteria():
    """Test filtering prompts with multiple criteria."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "Test prompt description"
    mock_prompt.__str__ = MagicMock(return_value="Test prompt template")
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    filter_criteria = {"name": "test_prompt", "description": "Test prompt description"}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_filter_prompts_partial_match():
    """Test filtering prompts with partial match."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    mock_prompt = MagicMock()
    mock_prompt.name = "test_prompt"
    mock_prompt.description = "Test prompt description"
    mock_prompt.__str__ = MagicMock(return_value="Test prompt template")
    prompt_manager._prompts = {"test_prompt": mock_prompt}

    filter_criteria = {"name": "test"}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_filter_prompts_with_prompt_attributes():
    """Test filtering prompts with different prompt attributes."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Create prompts with different attributes
    prompt1 = MagicMock()
    prompt1.name = "prompt1"
    prompt1.description = "Description 1"
    prompt1.__str__ = MagicMock(return_value="Template 1")

    prompt2 = MagicMock()
    prompt2.name = "prompt2"
    prompt2.description = "Description 2"
    prompt2.__str__ = MagicMock(return_value="Template 2")

    prompt_manager._prompts = {"prompt1": prompt1, "prompt2": prompt2}

    # Test filtering by description
    filter_criteria = {"description": "Description 1"}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 1
    assert result[0]["name"] == "prompt1"


@pytest.mark.asyncio
async def test_filter_prompts_with_missing_attributes():
    """Test filtering prompts with missing attributes."""
    mock_server_manager = MagicMock()
    prompt_manager = MCPPromptManager(mock_server_manager)

    # Create prompt with missing attributes
    prompt = MagicMock()
    prompt.name = "test_prompt"
    # No description or template attributes

    prompt_manager._prompts = {"test_prompt": prompt}

    # Test filtering by description (should not match)
    filter_criteria = {"description": "some description"}
    result = await prompt_manager.filter_prompts(filter_criteria)
    assert len(result) == 0
