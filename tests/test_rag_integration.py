import base64

from langchain_core.tools import tool

from bot.agent.action_registry import parse_action_tags
from bot.agent.tools import build_tools
from bot.infrastructure.rag_mcp import CloudflareMCPClient


@tool
def search_images(query: str) -> str:
    """Fake Cloudflare MCP image search for tests."""
    return query


def test_cloudflare_mcp_tools_are_exposed_without_replacing_existing_tools():
    tools = build_tools(mcp_tools=[search_images])
    assert [tool.name for tool in tools] == ["search_images"]


def test_legacy_action_tags_are_not_required_for_normal_responses():
    clean, actions = parse_action_tags("Done [SET_EMOTION: happy]")
    assert clean == "Done [SET_EMOTION: happy]"
    assert actions == []


def test_cloudflare_mcp_extracts_wrapped_image_content():
    payload = base64.b64encode(b"fake-image").decode()
    result = type("ToolMessage", (), {"content": [{"type": "image", "data": payload, "mimeType": "image/jpeg"}]})()
    images = CloudflareMCPClient.extract_images(result)
    assert images == [(b"fake-image", "image/jpeg")]
