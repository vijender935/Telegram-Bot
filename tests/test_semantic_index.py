from bot.infrastructure.vectorstore.semantic_index import SemanticIndex


def test_memory_index_round_trip(tmp_path):
    index = SemanticIndex(str(tmp_path / "memory.db"))
    index.upsert("memory:1:1", "red crop top image")
    index.upsert("memory:2:2", "blue jeans")
    results = index.search("red image", prefix="memory:1:")
    assert results
    assert results[0][0] == "memory:1:1"
