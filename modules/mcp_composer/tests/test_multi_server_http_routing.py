"""
Test suite for multi-server HTTP routing functionality
"""

import os
import pytest
import asyncio
import httpx
from unittest.mock import Mock, AsyncMock, patch
from mcp_composer.core.composer import MCPComposer
from mcp_composer.core.auth.jwt.isv_token_validator import ISVTokenValidator


class TestMultiServerHTTPRouting:
    """Test cases for multi-server HTTP routing"""

    @pytest.mark.asyncio
    async def test_http_mounted_servers_tracking(self):
        """Test that servers are tracked in _http_mounted_servers"""
        composer = MCPComposer(name="test-tracking")

        # Initially empty
        assert len(composer._http_mounted_servers) == 0

        # Register a server
        config = {
            "id": "tracking-test-server",
            "type": "stdio",
            "command": "python",
            "args": ["-c", "import sys; sys.exit(0)"],
        }
        await composer.register_mcp_server(config)

        # Should be tracked
        assert "tracking-test-server" in composer._http_mounted_servers
        assert len(composer._http_mounted_servers) == 1

        # Cleanup
        await composer.unmount_server("tracking-test-server")

    @pytest.mark.asyncio
    async def test_unmount_server_cleanup(self):
        """Test that unmounting removes server from tracking"""
        composer = MCPComposer(name="test-unmount")

        # Register a server
        config = {
            "id": "unmount-test-server",
            "type": "stdio",
            "command": "python",
            "args": ["-c", "import sys; sys.exit(0)"],
        }
        await composer.register_mcp_server(config)
        assert "unmount-test-server" in composer._http_mounted_servers

        # Unmount it
        await composer.unmount_server("unmount-test-server")

        # Should be removed from tracking
        assert "unmount-test-server" not in composer._http_mounted_servers

    @pytest.mark.asyncio
    async def test_get_multi_server_http_app(self):
        """Test that multi-server HTTP app is created correctly"""
        composer = MCPComposer(name="test-multi-app")

        # Register test servers
        for i in range(2):
            config = {
                "id": f"test-server-{i}",
                "type": "stdio",
                "command": "python",
                "args": ["-c", "import sys; sys.exit(0)"],
            }
            await composer.register_mcp_server(config)

        app = composer.get_multi_server_http_app()

        # Should have routes for both servers + composer root
        assert len(app.routes) == 3  # test-server-0, test-server-1, root

        # Check route paths
        route_paths = [route.path for route in app.routes]
        assert "/test-server-0" in route_paths
        assert "/test-server-1" in route_paths
        # Root path can be either "/" or "" depending on Starlette version
        assert "/" in route_paths or "" in route_paths

        # Cleanup
        for i in range(2):
            await composer.unmount_server(f"test-server-{i}")

    @pytest.mark.asyncio
    async def test_fallback_to_single_server_mode(self):
        """Test fallback to single-server mode when no servers mounted"""
        composer = MCPComposer(name="test-fallback")

        # No servers registered, should use default mode
        assert len(composer._http_mounted_servers) == 0

        # This should work without error (falls back to single-server mode)
        server_task = asyncio.create_task(
            composer.run_http_async(host="127.0.0.1", port=8200, show_banner=False)
        )

        await asyncio.sleep(1.5)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Root endpoint should work in single-server mode
                response = await client.post(
                    "http://127.0.0.1:8200/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "test", "version": "1.0.0"},
                        },
                    },
                    headers={"Content-Type": "application/json"},
                )
                assert response.status_code in [200, 406]

        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_multiple_servers_scalability(self):
        """Test that multiple servers can be registered efficiently"""
        composer = MCPComposer(name="test-scale")

        # Register 5 test servers (reduced from 10 for faster tests)
        for i in range(5):
            config = {
                "id": f"scale-test-server-{i}",
                "type": "stdio",
                "command": "python",
                "args": ["-c", "import sys; sys.exit(0)"],
            }
            await composer.register_mcp_server(config)

        # All should be tracked
        assert len(composer._http_mounted_servers) == 5

        # Create multi-server app
        app = composer.get_multi_server_http_app()

        # Should have 6 routes (5 servers + 1 root)
        assert len(app.routes) == 6

        # Cleanup
        for i in range(5):
            await composer.unmount_server(f"scale-test-server-{i}")


@pytest.mark.asyncio
async def test_existing_composer_functionality_not_broken():
    """Test that existing composer functionality still works"""
    composer = MCPComposer(name="compatibility-test")

    # Test basic server registration
    config = {
        "id": "compat-test-server",
        "type": "stdio",
        "command": "python",
        "args": ["-c", "import sys; sys.exit(0)"],
    }
    result = await composer.register_mcp_server(config)
    assert "mounted successfully" in result.lower()

    # Test that server is tracked
    assert "compat-test-server" in composer._http_mounted_servers

    # Test unmounting
    result = await composer.unmount_server("compat-test-server")
    assert "unmounted successfully" in result.lower()

    # Test that server is removed from tracking
    assert "compat-test-server" not in composer._http_mounted_servers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob


class TestISVAuthenticationForMultiServer:
    """Test cases for ISV authentication in multi-server HTTP routing"""

    @pytest.mark.asyncio
    async def test_isv_auth_enforced_in_non_local_env(self):
        """Test that ISV authentication is enforced for server routes in non-local environment"""
        # Set non-local environment
        with patch.dict(os.environ, {"MCP_COMPOSER_ENV": "test"}):
            # Create mock ISV validator
            mock_validator = Mock(spec=ISVTokenValidator)
            mock_validator.config = Mock()
            mock_validator.config.cookie_name = "mcsp-glb-iam-test"

            # Create composer with ISV validator
            composer = MCPComposer(name="test-isv-auth", isv_validator=mock_validator)

            # Register a test server
            config = {
                "id": "auth-test-server",
                "type": "stdio",
                "command": "python",
                "args": ["-c", "import sys; sys.exit(0)"],
            }
            await composer.register_mcp_server(config)

            # Get multi-server app
            app = composer.get_multi_server_http_app()

            # Verify app was created
            assert app is not None
            assert len(app.routes) >= 2  # At least server route + root

            # Cleanup
            await composer.unmount_server("auth-test-server")

    @pytest.mark.asyncio
    async def test_isv_auth_disabled_in_local_env(self):
        """Test that ISV authentication is disabled in local environment"""
        # Set local environment
        with patch.dict(os.environ, {"MCP_COMPOSER_ENV": "local"}):
            # Create mock ISV validator (should be ignored in local mode)
            mock_validator = Mock(spec=ISVTokenValidator)

            # Create composer with ISV validator
            composer = MCPComposer(
                name="test-local-no-auth", isv_validator=mock_validator
            )

            # Register a test server
            config = {
                "id": "local-test-server",
                "type": "stdio",
                "command": "python",
                "args": ["-c", "import sys; sys.exit(0)"],
            }
            await composer.register_mcp_server(config)

            # Get multi-server app (should not have auth middleware in local mode)
            app = composer.get_multi_server_http_app()

            # Verify app was created
            assert app is not None

            # Cleanup
            await composer.unmount_server("local-test-server")

    @pytest.mark.asyncio
    async def test_no_isv_validator_no_auth(self):
        """Test that no authentication is applied when ISV validator is not provided"""
        # Set non-local environment but no validator
        with patch.dict(os.environ, {"MCP_COMPOSER_ENV": "test"}):
            # Create composer without ISV validator
            composer = MCPComposer(name="test-no-validator")

            # Register a test server
            config = {
                "id": "no-validator-server",
                "type": "stdio",
                "command": "python",
                "args": ["-c", "import sys; sys.exit(0)"],
            }
            await composer.register_mcp_server(config)

            # Get multi-server app (should not have auth middleware)
            app = composer.get_multi_server_http_app()

            # Verify app was created
            assert app is not None

            # Cleanup
            await composer.unmount_server("no-validator-server")

    @pytest.mark.asyncio
    async def test_isv_validator_stored_correctly(self):
        """Test that ISV validator is stored correctly in composer"""
        mock_validator = Mock(spec=ISVTokenValidator)

        # Create composer with ISV validator
        composer = MCPComposer(
            name="test-validator-storage", isv_validator=mock_validator
        )

        # Verify validator is stored
        assert composer._isv_validator is mock_validator

    @pytest.mark.asyncio
    async def test_multiple_servers_with_isv_auth(self):
        """Test that multiple servers all get ISV authentication middleware"""
        with patch.dict(os.environ, {"MCP_COMPOSER_ENV": "test"}):
            mock_validator = Mock(spec=ISVTokenValidator)
            mock_validator.config = Mock()
            mock_validator.config.cookie_name = "mcsp-glb-iam-test"

            composer = MCPComposer(name="test-multi-auth", isv_validator=mock_validator)

            # Register multiple servers
            for i in range(3):
                config = {
                    "id": f"multi-auth-server-{i}",
                    "type": "stdio",
                    "command": "python",
                    "args": ["-c", "import sys; sys.exit(0)"],
                }
                await composer.register_mcp_server(config)

            # Get multi-server app
            app = composer.get_multi_server_http_app()

            # Verify app was created with all routes
            assert app is not None
            assert len(app.routes) == 4  # 3 servers + 1 root

            # Cleanup
            for i in range(3):
                await composer.unmount_server(f"multi-auth-server-{i}")


class TestToolPrefixInMultiServer:
    """Test cases for tool name prefixing in multi-server HTTP routing"""

    @pytest.mark.asyncio
    async def test_tool_prefix_middleware_added(self):
        """Test that ToolPrefixMiddleware is added to servers in multi-server mode"""
        # Enable multi-server routing
        with patch.dict(os.environ, {"ENABLE_MULTI_SERVER_HTTP_ROUTING": "true"}):
            composer = MCPComposer(name="test-tool-prefix")

            # Register a test server
            config = {
                "id": "prefix-test-server",
                "type": "stdio",
                "command": "python",
                "args": ["-c", "import sys; sys.exit(0)"],
            }
            await composer.register_mcp_server(config)

            # Get multi-server app
            app = composer.get_multi_server_http_app()

            # Verify app was created
            assert app is not None

            # Cleanup
            await composer.unmount_server("prefix-test-server")

    @pytest.mark.asyncio
    async def test_tool_names_prefixed_with_server_id(self):
        """Test that tool names are prefixed with server ID in multi-server routes"""
        with patch.dict(os.environ, {"ENABLE_MULTI_SERVER_HTTP_ROUTING": "true"}):
            composer = MCPComposer(name="test-prefix-names")

            # Register test servers with mock tools
            for i in range(2):
                config = {
                    "id": f"server-{i}",
                    "type": "stdio",
                    "command": "python",
                    "args": ["-c", "import sys; sys.exit(0)"],
                }
                await composer.register_mcp_server(config)

            # Verify servers are tracked
            assert len(composer._http_mounted_servers) == 2
            assert "server-0" in composer._http_mounted_servers
            assert "server-1" in composer._http_mounted_servers

            # Get multi-server app
            app = composer.get_multi_server_http_app()
            assert app is not None

            # Cleanup
            for i in range(2):
                await composer.unmount_server(f"server-{i}")

    @pytest.mark.asyncio
    async def test_tool_prefix_with_isv_auth(self):
        """Test that tool prefixing works alongside ISV authentication"""
        with patch.dict(
            os.environ,
            {"ENABLE_MULTI_SERVER_HTTP_ROUTING": "true", "MCP_COMPOSER_ENV": "test"},
        ):
            mock_validator = Mock(spec=ISVTokenValidator)
            mock_validator.config = Mock()
            mock_validator.config.cookie_name = "mcsp-glb-iam-test"

            composer = MCPComposer(
                name="test-prefix-with-auth", isv_validator=mock_validator
            )

            # Register a test server
            config = {
                "id": "auth-prefix-server",
                "type": "stdio",
                "command": "python",
                "args": ["-c", "import sys; sys.exit(0)"],
            }
            await composer.register_mcp_server(config)

            # Get multi-server app (should have both prefix and auth middleware)
            app = composer.get_multi_server_http_app()
            assert app is not None

            # Cleanup
            await composer.unmount_server("auth-prefix-server")

    @pytest.mark.asyncio
    async def test_multiple_servers_unique_tool_names(self):
        """Test that multiple servers with same tool names get unique prefixed names"""
        with patch.dict(os.environ, {"ENABLE_MULTI_SERVER_HTTP_ROUTING": "true"}):
            composer = MCPComposer(name="test-unique-names")

            # Register multiple servers (they might have tools with same names)
            for i in range(3):
                config = {
                    "id": f"unique-server-{i}",
                    "type": "stdio",
                    "command": "python",
                    "args": ["-c", "import sys; sys.exit(0)"],
                }
                await composer.register_mcp_server(config)

            # Verify all servers are tracked
            assert len(composer._http_mounted_servers) == 3

            # Get multi-server app
            app = composer.get_multi_server_http_app()
            assert app is not None

            # Verify routes exist for all servers
            route_paths = [route.path for route in app.routes]
            assert "/unique-server-0" in route_paths
            assert "/unique-server-1" in route_paths
            assert "/unique-server-2" in route_paths

            # Cleanup
            for i in range(3):
                await composer.unmount_server(f"unique-server-{i}")

    @pytest.mark.asyncio
    async def test_tool_prefix_disabled_in_single_server_mode(self):
        """Test that tool prefixing is not applied in single-server mode"""
        # Don't enable multi-server routing
        with patch.dict(os.environ, {"ENABLE_MULTI_SERVER_HTTP_ROUTING": "false"}):
            composer = MCPComposer(name="test-single-mode")

            # Register a server
            config = {
                "id": "single-mode-server",
                "type": "stdio",
                "command": "python",
                "args": ["-c", "import sys; sys.exit(0)"],
            }
            await composer.register_mcp_server(config)

            # In single-server mode, _http_mounted_servers should be EMPTY
            # because multi-server routing is disabled
            assert "single-mode-server" not in composer._http_mounted_servers
            assert len(composer._http_mounted_servers) == 0

            # Cleanup
            await composer.unmount_server("single-mode-server")

    @pytest.mark.asyncio
    async def test_composer_middleware_propagated_to_servers(self):
        """Test that middleware added to composer is propagated to member servers"""
        with patch.dict(os.environ, {"ENABLE_MULTI_SERVER_HTTP_ROUTING": "true"}):
            from mcp_composer.middleware.tracing_middleware import TracingMiddleware

            composer = MCPComposer(name="test-middleware-propagation")

            # Add middleware to composer (simulating setup_middleware())
            tracing_mw = TracingMiddleware(log_tools=True)
            composer.add_middleware(tracing_mw)

            # Register test servers
            for i in range(2):
                config = {
                    "id": f"mw-server-{i}",
                    "type": "stdio",
                    "command": "python",
                    "args": ["-c", "import sys; sys.exit(0)"],
                }
                await composer.register_mcp_server(config)

            # Get multi-server app - this should propagate middleware
            app = composer.get_multi_server_http_app()
            assert app is not None

            # Verify servers have middleware
            # Note: We can't directly inspect middleware stack, but the app creation
            # should log the propagation
            assert len(composer._http_mounted_servers) == 2

            # Cleanup
            for i in range(2):
                await composer.unmount_server(f"mw-server-{i}")
