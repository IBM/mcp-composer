"""
Test suite for multi-server HTTP routing functionality
"""

import pytest
import asyncio
import httpx
from mcp_composer.core.composer import MCPComposer


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
