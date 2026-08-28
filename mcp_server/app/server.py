from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server.app.adapters.wechat_workspace import WorkspaceAdapter
from mcp_server.app.config import get_mcp_settings
from mcp_server.app.resources.wechat import register_resources
from mcp_server.app.tools.wechat import register_tools

settings = get_mcp_settings()
adapter = WorkspaceAdapter(settings.workspace, settings.approval_secret, settings.state_path)
mcp = FastMCP("Bubu WeChat Operations", host=settings.host, port=settings.port)
register_resources(mcp, adapter)
register_tools(mcp, adapter)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
