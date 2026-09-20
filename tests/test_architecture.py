from pathlib import Path

from bot.infrastructure.vectorstore.semantic_index import SemanticIndex



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
