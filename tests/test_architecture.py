from pathlib import Path

from bot.agent.action_registry import parse_action_tags
from bot.application.orchestration import ToolCall, ToolRegistry
from bot.infrastructure.vectorstore.semantic_index import SemanticIndex


def test_action_tags_are_whitelisted():
    clean, actions = parse_action_tags("hello [VOICE] [UNKNOWN:bad]")
    assert clean == "hello"
    assert actions == [("VOICE", None)]


def test_tool_registry_executes_structured_calls():
    registry = ToolRegistry()
    registry.register("math.add", lambda a, b: a + b)
    result = registry.execute(ToolCall("math.add", {"a": 2, "b": 3}))
    assert result.ok and result.data == 5
    assert not registry.execute(ToolCall("math.missing", {})).ok


def test_semantic_index_persists_metadata(tmp_path: Path):
    index = SemanticIndex(str(tmp_path / "vectors.db"))
    index.upsert("1", "mountain trip photo")
    index.upsert("2", "office invoice pdf")
    results = index.search("mountain photo")
    assert results[0][0] == "1"


def test_semantic_index_supports_scoped_retrieval(tmp_path: Path):
    index = SemanticIndex(str(tmp_path / "vectors.db"))
    index.upsert("memory:10:1", "user ten likes hiking")
    index.upsert("memory:20:1", "user twenty likes cooking")
    results = index.search("hiking", prefix="memory:10:")
    assert results and results[0][0] == "memory:10:1"
    assert not index.search("cooking", prefix="memory:10:")
