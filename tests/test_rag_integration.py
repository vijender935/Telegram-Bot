import base64

from langchain_core.tools import tool
from bot.agent.tools import build_tools
from bot.infrastructure.rag_mcp import CloudflareMCPClient
from bot.gateway.handlers import _tool_result_text


@tool
def search_images(query: str) -> str:
    """Fake Cloudflare MCP image search for tests."""
    return query


def test_cloudflare_mcp_tools_are_exposed_without_replacing_existing_tools():
    tools = build_tools(mcp_tools=[search_images])
    assert [tool.name for tool in tools] == ["search_images"]


def test_cloudflare_mcp_extracts_wrapped_image_content():
    payload = base64.b64encode(b"fake-image").decode()
    result = type("ToolMessage", (), {"content": [{"type": "image", "data": payload, "mimeType": "image/jpeg"}]})()
    images = CloudflareMCPClient.extract_images(result)
    assert images == [(b"fake-image", "image/jpeg")]


def test_tool_result_text_strips_mcp_image_markdown():
    encoded = "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA"
    result = f"![Similar photo]({encoded})"
    assert _tool_result_text(result) == ""


def test_tool_result_text_keeps_normal_tool_text():
    result = "Similar photos retrieved successfully."
    assert _tool_result_text(result) == result
