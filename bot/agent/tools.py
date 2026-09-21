"""Runtime tool factory for structured, user-scoped agent calls."""
from __future__ import annotations

from langchain_core.tools import BaseTool, tool


def build_tools(
    memory=None,
    user_id: int | None = None,
    mcp_tools: list[BaseTool] | None = None,
) -> list[BaseTool]:
    tools: list[BaseTool] = []

    if memory is not None and user_id is not None:
        @tool
        def memory_search(query: str) -> str:
            """Search only this user's saved episodic memories and preferences."""
            search = getattr(memory, "search_user", None)
            results = search(user_id, query, limit=5) if search else []
            if not results:
                return "No matching memories."
            useful = [item for item in results if item[2] > 0]
            if not useful:
                return "No matching memories."
            return "\n".join(f"{text} (relevance={score:.0%})" for _, text, score in useful)
        tools.append(memory_search)

    # The custom Cloudflare MCP tools are discovered dynamically from the MCP server.
    if mcp_tools:
        tools.extend(mcp_tools)

    return tools
