from langchain_core.tools import tool

from bot.agent.action_registry import parse_action_tags
from bot.agent.tools import build_tools
from bot.application.drive_service import DriveService


@tool
def search_images(query: str) -> str:
    """Fake RAG image search for tests."""
    return query


def test_rag_tools_are_exposed_without_replacing_existing_tools(tmp_path):
    tools = build_tools(
        memory=None,
        drive=None,
        user_id=123,
        sandbox_path=str(tmp_path),
        mcp_tools=[search_images],
    )
    assert [tool.name for tool in tools] == ["search_images"]


def test_rag_media_action_tag_is_supported():
    clean, actions = parse_action_tags("Mil gaya [RAG_SEND_MEDIA: red dress]")
    assert clean == "Mil gaya"
    assert actions == [("RAG_SEND_MEDIA", "red dress")]


def test_drive_service_accepts_string_destination(tmp_path):
    class FakeClient:
        folder_id = "root"

        def _list_entries(self, _folder_id):
            return {}

        def semantic_download(self, _user_id, _description, dest_dir):
            assert hasattr(dest_dir, "__truediv__")
            return "not_found", "No file"

    class FakeIndex:
        def search(self, *_args, **_kwargs):
            return []

    service = DriveService(FakeClient(), FakeIndex())
    assert service.semantic_download(123, "test", str(tmp_path)) == ("not_found", "No file")
