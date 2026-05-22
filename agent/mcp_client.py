import os
import asyncio
from typing import Dict, Any, List
from contextlib import AsyncExitStack
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

class MCPClientManager:
    def __init__(self):
        # We will keep a dictionary of active sessions
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        
    async def connect_to_server(self, server_name: str, url: str):
        """Connects to an SSE MCP server and stores the session"""
        try:
            # The SSE endpoint is typically at the root or /sse
            # fastmcp uses /sse by default
            sse_url = f"{url}/sse"
            
            # Use AsyncExitStack to manage the context managers
            transport = await self.exit_stack.enter_async_context(sse_client(sse_url))
            session = await self.exit_stack.enter_async_context(ClientSession(*transport))
            
            await session.initialize()
            self.sessions[server_name] = session
            print(f"Connected to MCP server: {server_name} at {url}")
        except Exception as e:
            print(f"Failed to connect to {server_name} at {url}: {e}")

    async def list_all_tools(self) -> List[Dict[str, Any]]:
        """Queries all connected servers for their tools"""
        all_tools = []
        for server_name, session in self.sessions.items():
            try:
                response = await session.list_tools()
                for tool in response.tools:
                    # We inject the server_name into the tool definition so we know where to route calls
                    all_tools.append({
                        "server_name": server_name,
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    })
            except Exception as e:
                print(f"Error listing tools for {server_name}: {e}")
        return all_tools

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Calls a specific tool on a specific server"""
        if server_name not in self.sessions:
            return {"error": f"Server {server_name} not connected"}
            
        session = self.sessions[server_name]
        try:
            result = await session.call_tool(tool_name, arguments)
            # result is a CallToolResult object, which contains a list of content elements
            # We assume a single JSON or Text content
            if result.content and len(result.content) > 0:
                content = result.content[0]
                if content.type == "text":
                    return content.text
                return content.model_dump()
            return {"status": "success", "message": "Tool executed, but no content returned."}
        except Exception as e:
            return {"error": str(e)}

    async def close(self):
        await self.exit_stack.aclose()

# Singleton instance to be used by the FastAPI app
mcp_manager = MCPClientManager()
