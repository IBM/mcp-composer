import asyncio
import json
from typing import List
import pytest
from unittest.mock import patch, MagicMock
from mcp_composer.tag.scanner.mcp_protocol import McpProtocolScanner, ToolDescriptor
from unittest.mock import MagicMock, patch, AsyncMock


@pytest.fixture
def scanner():
    return McpProtocolScanner(endpoint="http://localhost", transport="http")


@pytest.mark.asyncio
async def test_collect_http_success(scanner):
    # Patch _connect_streamable_http to return a list of ToolDescriptor
    with patch.object(
        scanner,
        "_connect_streamable_http",
        return_value=[
            ToolDescriptor(
                id="tool1",
                name="Tool 1",
                description="",
                input_schema={},
                output_schema={},
                annotations={},
                endpoint="http://localhost/mcp",
            )
        ],
    ), patch("asyncio.run", side_effect=lambda coro: coro):
        result = await scanner.collect()
        assert isinstance(result, list)
        assert result[0].id == "tool1"
        assert result[0].name == "Tool 1"
        assert result[0].endpoint == "http://localhost/mcp"


@pytest.mark.asyncio
async def test_collect_sse_success():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="sse")
    with patch.object(
        scanner,
        "_connect_sse",
        return_value=[
            ToolDescriptor(
                id="tool2",
                name="Tool 2",
                description="",
                input_schema={},
                output_schema={},
                annotations={},
                endpoint="http://localhost/sse",
            )
        ],
    ), patch("asyncio.run", side_effect=lambda coro: coro):
        result = await scanner.collect()
        assert result[0].id == "tool2"
        assert scanner.endpoint.endswith("/sse")


@pytest.mark.asyncio
async def test_collect_stdio_success():
    scanner = McpProtocolScanner(
        endpoint="http://localhost", transport="stdio", command="echo", args="hello"
    )
    with patch.object(
        scanner,
        "_connect_stdio",
        return_value=[
            ToolDescriptor(
                id="tool3",
                name="Tool 3",
                description="",
                input_schema={},
                output_schema={},
                annotations={},
                endpoint="http://localhost",
            )
        ],
    ), patch("asyncio.run", side_effect=lambda coro: coro):
        result = await scanner.collect()
        assert result[0].id == "tool3"


def test_collect_unsupported_transport():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="invalid")
    with pytest.raises(RuntimeError) as excinfo:
        scanner.collect()
    assert "Unsupported transport" in str(excinfo.value)


def test_collect_exception_handling(scanner):
    with patch.object(
        scanner, "_connect_streamable_http", side_effect=Exception("fail")
    ), patch("asyncio.run", side_effect=lambda coro: coro()):
        with pytest.raises(RuntimeError) as excinfo:
            scanner.collect()
        assert "Failed to collect tools from MCP server" in str(excinfo.value)


@pytest.mark.asyncio
async def test_connect_streamable_http_success():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    # Mock streamablehttp_client context manager and _run_session
    mock_read_stream = MagicMock()
    mock_write_stream = MagicMock()
    mock_get_session_id = MagicMock()
    mock_tools = [
        ToolDescriptor(
            id="toolX",
            name="Tool X",
            description="",
            input_schema={},
            output_schema={},
            annotations={},
            endpoint="http://localhost/mcp",
        )
    ]
    with patch(
        "mcp_composer.tag.scanner.mcp_protocol.streamablehttp_client"
    ) as mock_client, patch.object(
        scanner, "_run_session", return_value=mock_tools
    ) as mock_run_session:
        mock_cm = MagicMock()
        mock_cm.__aenter__.return_value = (
            mock_read_stream,
            mock_write_stream,
            mock_get_session_id,
        )
        mock_cm.__aexit__.return_value = False
        mock_client.return_value = mock_cm
        result = await scanner._connect_streamable_http()
        assert result == mock_tools
        mock_run_session.assert_called_once_with(mock_read_stream, mock_write_stream)


@pytest.mark.asyncio
async def test_connect_streamable_http_exception_fallback():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    # Simulate exception in context manager
    with patch(
        "mcp_composer.tag.scanner.mcp_protocol.streamablehttp_client",
        side_effect=Exception("fail"),
    ), patch.object(
        scanner, "_fallback_discovery", return_value=["fallback_tool"]
    ) as mock_fallback:
        result = await scanner._connect_streamable_http()
        assert result == ["fallback_tool"]
        mock_fallback.assert_called_once()


@pytest.mark.asyncio
async def test_connect_sse_success():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="sse")
    mock_read_stream = MagicMock()
    mock_write_stream = MagicMock()
    mock_tools = [
        ToolDescriptor(
            id="toolY",
            name="Tool Y",
            description="",
            input_schema={},
            output_schema={},
            annotations={},
            endpoint="http://localhost/sse",
        )
    ]
    with patch(
        "mcp_composer.tag.scanner.mcp_protocol.sse_client"
    ) as mock_client, patch.object(
        scanner, "_run_session", return_value=mock_tools
    ) as mock_run_session:
        mock_cm = MagicMock()
        mock_cm.__aenter__.return_value = (mock_read_stream, mock_write_stream)
        mock_cm.__aexit__.return_value = False
        mock_client.return_value = mock_cm
        result = await scanner._connect_sse()
        assert result == mock_tools
        mock_run_session.assert_called_once_with(mock_read_stream, mock_write_stream)


@pytest.mark.asyncio
async def test_connect_sse_exception_fallback():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="sse")
    with patch(
        "mcp_composer.tag.scanner.mcp_protocol.sse_client",
        side_effect=Exception("fail"),
    ), patch.object(
        scanner, "_fallback_discovery", return_value=["fallback_tool"]
    ) as mock_fallback:
        result = await scanner._connect_sse()
        assert result == ["fallback_tool"]
        mock_fallback.assert_called_once()

        @pytest.mark.asyncio
        async def test_connect_stdio_success():
            scanner = McpProtocolScanner(
                endpoint="http://localhost",
                transport="stdio",
                command="echo",
                args="hello",
            )
            mock_read_stream = MagicMock()
            mock_write_stream = MagicMock()
            mock_tools = [
                ToolDescriptor(
                    id="toolS",
                    name="Tool S",
                    description="",
                    input_schema={},
                    output_schema={},
                    annotations={},
                    endpoint="http://localhost",
                )
            ]
            with patch(
                "mcp_composer.tag.scanner.mcp_protocol.stdio_client"
            ) as mock_client, patch.object(
                scanner, "_run_session", return_value=mock_tools
            ) as mock_run_session:
                mock_cm = MagicMock()
                mock_cm.__aenter__.return_value = (mock_read_stream, mock_write_stream)
                mock_cm.__aexit__.return_value = False
                mock_client.return_value = mock_cm
                result = await scanner._connect_stdio()
                assert result == mock_tools
                mock_run_session.assert_called_once_with(
                    mock_read_stream, mock_write_stream
                )


@pytest.mark.asyncio
async def test_connect_stdio_no_command():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="stdio")
    result = await scanner._connect_stdio()
    assert result == []


@pytest.mark.asyncio
async def test_connect_stdio_exception():
    scanner = McpProtocolScanner(
        endpoint="http://localhost", transport="stdio", command="echo", args="hello"
    )
    with patch(
        "mcp_composer.tag.scanner.mcp_protocol.stdio_client",
        side_effect=Exception("fail"),
    ):
        result = await scanner._connect_stdio()
        assert result == []


def test_get_server_info_success(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    expected_info = {"name": "test-server", "version": "1.2.3"}

    # Patch httpx.get to return a mock response with status_code 200
    class MockResponse:
        status_code = 200

        def json(self):
            return expected_info

    def mock_get(url, headers=None, timeout=None):
        return MockResponse()

    monkeypatch.setattr("httpx.get", mock_get)
    result = scanner._get_server_info()
    assert result == expected_info


def test_get_server_info_all_endpoints_fail(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")

    # Patch httpx.get to always raise an exception
    def mock_get(url, headers=None, timeout=None):
        raise Exception("fail")

    monkeypatch.setattr("httpx.get", mock_get)
    # Patch _get_server_info_via_transport to return fallback info
    fallback_info = {"name": "fallback-server", "version": "0.0.1"}
    scanner._get_server_info_via_transport = lambda: fallback_info
    result = scanner._get_server_info()
    assert result == fallback_info


def test_get_server_info_partial_success(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    # First endpoint fails, second succeeds
    call_count = {"count": 0}
    expected_info = {"name": "partial-server", "version": "2.0.0"}

    class MockResponse:
        status_code = 200

        def json(self):
            return expected_info

    def mock_get(url, headers=None, timeout=None):
        call_count["count"] += 1
        if call_count["count"] == 1:
            raise Exception("fail")
        return MockResponse()

    monkeypatch.setattr("httpx.get", mock_get)
    result = scanner._get_server_info()
    assert result == expected_info


def test_get_server_info_via_transport_mock(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    expected_info = {"name": "mock-server", "version": "9.9.9"}

    # Patch the method to return the expected info
    monkeypatch.setattr(
        scanner, "_get_server_info_via_transport", lambda: expected_info
    )

    result = scanner._get_server_info_via_transport()
    assert result == expected_info


def test_get_server_info_via_transport_exception(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")

    # Simulate exception for all endpoints
    def mock_stream(method, endpoint, headers=None, json=None, timeout=None):
        raise Exception("fail")

    monkeypatch.setattr("httpx.stream", mock_stream)
    result = scanner._get_server_info_via_transport()
    assert result == {"name": "mcp-server", "version": "1.0.0", "capabilities": {}}


@pytest.mark.asyncio
async def test_run_session_success(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    mock_read_stream = MagicMock()
    mock_write_stream = MagicMock()
    mock_server_info = {"name": "test-server", "version": "1.0.0"}
    mock_tool = MagicMock()
    mock_tool.id = "toolA"
    mock_tool.name = "Tool A"
    mock_tool.description = "desc"
    mock_tool.inputSchema = {}
    mock_tool.outputSchema = {}
    mock_tool.annotations = {}

    # Patch _get_server_info to return mock_server_info
    monkeypatch.setattr(scanner, "_get_server_info", lambda: mock_server_info)
    # Patch ClientSession context manager
    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()
    mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[mock_tool]))
    mock_client_session_cm = MagicMock()
    mock_client_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_session_cm.__aexit__ = AsyncMock(return_value=None)
    with patch(
        "mcp_composer.tag.scanner.mcp_protocol.ClientSession",
        return_value=mock_client_session_cm,
    ):
        # Patch _get_tools_list to return [mock_tool]
        monkeypatch.setattr(
            scanner, "_get_tools_list", AsyncMock(return_value=[mock_tool])
        )
        # Patch _convert_to_tool_descriptor to return a ToolDescriptor
        monkeypatch.setattr(
            scanner,
            "_convert_to_tool_descriptor",
            lambda tool, info: ToolDescriptor(
                id=tool.id,
                name=tool.name,
                description=tool.description,
                input_schema=tool.inputSchema,
                output_schema=tool.outputSchema,
                annotations=tool.annotations,
                endpoint=scanner.endpoint,
            ),
        )
        result = await scanner._run_session(mock_read_stream, mock_write_stream)
        assert isinstance(result, list)
        assert result[0].id == "toolA"
        assert result[0].name == "Tool A"
        assert result[0].endpoint == "http://localhost"


@pytest.mark.asyncio
async def test_run_session_no_tools(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    mock_read_stream = MagicMock()
    mock_write_stream = MagicMock()
    mock_server_info = {"name": "test-server", "version": "1.0.0"}

    monkeypatch.setattr(scanner, "_get_server_info", lambda: mock_server_info)
    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()
    mock_client_session_cm = MagicMock()
    mock_client_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_session_cm.__aexit__ = AsyncMock(return_value=None)
    with patch(
        "mcp_composer.tag.scanner.mcp_protocol.ClientSession",
        return_value=mock_client_session_cm,
    ):
        monkeypatch.setattr(scanner, "_get_tools_list", AsyncMock(return_value=[]))
        monkeypatch.setattr(
            scanner, "_convert_to_tool_descriptor", lambda tool, info: tool
        )
        result = await scanner._run_session(mock_read_stream, mock_write_stream)
        assert result == []


@pytest.mark.asyncio
async def test_run_session_exception_in_initialize(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    mock_read_stream = MagicMock()
    mock_write_stream = MagicMock()
    mock_server_info = {"name": "test-server", "version": "1.0.0"}

    monkeypatch.setattr(scanner, "_get_server_info", lambda: mock_server_info)
    mock_session = MagicMock()
    mock_session.initialize = AsyncMock(side_effect=Exception("init fail"))
    mock_client_session_cm = MagicMock()
    mock_client_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_client_session_cm.__aexit__ = AsyncMock(return_value=None)
    with patch(
        "mcp_composer.tag.scanner.mcp_protocol.ClientSession",
        return_value=mock_client_session_cm,
    ):
        monkeypatch.setattr(scanner, "_get_tools_list", AsyncMock(return_value=[]))
        with pytest.raises(Exception) as excinfo:
            await scanner._run_session(mock_read_stream, mock_write_stream)
        assert "init fail" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_tools_list_success_first_endpoint(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    mock_tools = [{"id": "tool1"}, {"id": "tool2"}]

    class MockResponse:
        status_code = 200

        def json(self):
            return mock_tools

    def mock_get(url, headers=None, timeout=None):
        # Only the first endpoint should be called
        assert url == "http://localhost/tools/list"
        return MockResponse()

    monkeypatch.setattr("httpx.get", mock_get)
    monkeypatch.setattr(scanner, "_extract_tools_from_response", lambda data: data)
    result = await scanner._get_tools_list()
    assert result == mock_tools


@pytest.mark.asyncio
async def test_get_tools_list_all_endpoints_fail(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")

    def mock_get(url, headers=None, timeout=None):
        raise Exception("fail")

    monkeypatch.setattr("httpx.get", mock_get)
    monkeypatch.setattr(
        scanner, "_get_tools_via_session", AsyncMock(return_value=["toolX"])
    )
    result = await scanner._get_tools_list()
    assert result == ["toolX"]


@pytest.mark.asyncio
async def test_get_tools_list_extract_tools(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    mock_response_data = {"tools": [{"id": "toolZ"}]}

    class MockResponse:
        status_code = 200

        def json(self):
            return mock_response_data

    def mock_get(url, headers=None, timeout=None):
        return MockResponse()

    monkeypatch.setattr("httpx.get", mock_get)
    monkeypatch.setattr(
        scanner, "_extract_tools_from_response", lambda data: data["tools"]
    )
    result = await scanner._get_tools_list()
    assert result == [{"id": "toolZ"}]


@pytest.mark.asyncio
async def test_get_tools_via_session_success(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    mock_tools = [{"id": "tool1"}, {"id": "tool2"}]
    mock_result = MagicMock()
    mock_result.tools = mock_tools
    scanner.session = MagicMock()
    scanner.session.list_tools = AsyncMock(return_value=mock_result)
    monkeypatch.setattr(scanner, "_extract_tools_from_response", lambda data: data)
    result = await scanner._get_tools_via_session()
    assert result == mock_tools


@pytest.mark.asyncio
async def test_get_tools_via_session_no_session(capsys):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    scanner.session = None
    result = await scanner._get_tools_via_session()
    assert result == []
    captured = capsys.readouterr()
    assert "No active MCP session available." in captured.out


@pytest.mark.asyncio
async def test_get_tools_via_session_no_tools_attr(capsys):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    mock_result = MagicMock()
    delattr(mock_result, "tools")
    scanner.session = MagicMock()
    scanner.session.list_tools = AsyncMock(return_value=mock_result)
    result = await scanner._get_tools_via_session()
    assert result == []
    captured = capsys.readouterr()
    assert "No tools available" in captured.out


@pytest.mark.asyncio
async def test_get_tools_via_session_tools_empty(capsys):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    mock_result = MagicMock()
    mock_result.tools = []
    scanner.session = MagicMock()
    scanner.session.list_tools = AsyncMock(return_value=mock_result)
    result = await scanner._get_tools_via_session()
    assert result == []
    captured = capsys.readouterr()
    assert "No tools available" in captured.out


@pytest.mark.asyncio
async def test_get_tools_via_session_exception(capsys):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    scanner.session = MagicMock()
    scanner.session.list_tools = AsyncMock(side_effect=Exception("fail"))
    result = await scanner._get_tools_via_session()
    assert result == []
    captured = capsys.readouterr()
    assert "Error fetching tools via MCP session" in captured.out


def test_extract_tools_from_response_list():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    data = [{"id": "tool1"}, {"id": "tool2"}]
    result = scanner._extract_tools_from_response(data)
    assert result == data


def test_extract_tools_from_response_dict_with_tools():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    data = {"tools": [{"id": "toolA"}]}
    result = scanner._extract_tools_from_response(data)
    assert result == [{"id": "toolA"}]


def test_extract_tools_from_response_dict_with_data_list():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    data = {"data": [{"id": "toolB"}]}
    result = scanner._extract_tools_from_response(data)
    assert result == [{"id": "toolB"}]


def test_extract_tools_from_response_dict_with_result_list():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    data = {"result": [{"id": "toolC"}]}
    result = scanner._extract_tools_from_response(data)
    assert result == [{"id": "toolC"}]


def test_extract_tools_from_response_dict_with_result_tools():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    data = {"result": {"tools": [{"id": "toolD"}]}}
    result = scanner._extract_tools_from_response(data)
    assert result == [{"id": "toolD"}]


def test_extract_tools_from_response_dict_no_tools():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    data = {"foo": "bar"}
    result = scanner._extract_tools_from_response(data)
    assert result == []


def test_extract_tools_from_response_none():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    result = scanner._extract_tools_from_response(None)
    assert result == []


def test_extract_tools_from_response_unexpected_type():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")
    result = scanner._extract_tools_from_response("not a dict or list")
    assert result == []


def test_convert_to_tool_descriptor_with_dict_annotations():
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")

    class ToolMock:
        id = "tool1"
        name = "Tool One"
        description = "desc"
        inputSchema = {"type": "object"}
        outputSchema = {"type": "object"}
        annotations = {"foo": "bar"}
        vendor = "vendorX"

    server_info = {"name": "serverA", "version": "1.0.0"}
    result = scanner._convert_to_tool_descriptor(ToolMock(), server_info)
    assert isinstance(result, ToolDescriptor)
    assert result.id == "tool1"
    assert result.name == "Tool One"
    assert result.description == "desc"
    assert result.input_schema == {"type": "object"}
    assert result.output_schema == {"type": "object"}
    assert result.vendor == "vendorX"
    assert result.endpoint == "http://localhost"
    assert result.annotations["foo"] == "bar"
    assert result.annotations["mcp_protocol"] is True
    assert result.annotations["server_name"] == "serverA"
    assert result.annotations["server_version"] == "1.0.0"
    assert result.annotations["transport"] == "http"


def test_convert_to_tool_descriptor_with_ToolAnnotations(monkeypatch):
    scanner = McpProtocolScanner(endpoint="http://localhost", transport="http")

    class ToolAnnotationsMock:
        def __init__(self):
            self.foo = "bar"
            self.bar = 123

    class ToolMock:
        id = "tool2"
        name = "Tool Two"
        description = "desc2"
        inputSchema = {"type": "string"}
        outputSchema = {"type": "number"}
        annotations = ToolAnnotationsMock()
        vendor = None

    server_info = {"name": "serverB", "version": "2.0.0"}
    # Patch isinstance to treat ToolAnnotationsMock as ToolAnnotations
    monkeypatch.setattr(
        "mcp_composer.tag.scanner.mcp_protocol.ToolAnnotations", ToolAnnotationsMock
    )
    result = scanner._convert_to_tool_descriptor(ToolMock(), server_info)
    assert isinstance(result, ToolDescriptor)
    assert result.id == "tool2"
    assert result.name == "Tool Two"
    assert result.vendor == "serverB"
    assert result.annotations["foo"] == "bar"
    assert result.annotations["bar"] == 123
    assert result.annotations["mcp_protocol"] is True
    assert result.annotations["server_name"] == "serverB"
    assert result.annotations["server_version"] == "2.0.0"
    assert result.annotations["transport"] == "http"
