from mcp import ClientSession 
from typing import Optional 
from mcp.client.streamable_http import streamablehttp_client
from beeai_framework.tools.mcp import MCPTool 
from contextlib import AsyncExitStack

class MCPClient: 

    def __init__(self): 
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        
    async def connect_to_streamable_http_server(
        self, server_url: str, headers: Optional[dict] = None
    ): 
        self._streams_context = streamablehttp_client(
            url = server_url, 
            headers = headers or {},
        )
        read_stream, write_stream, _ = await self._streams_context.__aenter__()

        self._session_context = ClientSession(read_stream, write_stream)
        self.session: ClientSession = await self._session_context.__aenter__()

        await self.session.initialize()

        
    async def cleanup(self):
        """Properly clean up the session and streams"""
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:  # pylint: disable=W0125
            await self._streams_context.__aexit__(None, None, None)

    async def call_tool(self, tool, args): 
        result = await self.session.call_tool(tool, args)
        return result
    
    async def list_mcp_tools(self): 
        response = await self.session.list_tools()
        return response

    async def list_bee_tools(self): 
        tools = await MCPTool.from_client(self.session)
        return tools 