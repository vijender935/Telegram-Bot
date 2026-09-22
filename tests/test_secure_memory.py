from bot.infrastructure.memory import MemoryStore
from bot.domain.memory.service import MemoryService
from bot.infrastructure.vectorstore.semantic_index import SemanticIndex


def test_memory_service_clears_store_and_semantic_index(tmp_path):
    db_path = str(tmp_path / "memory.db")
    store = MemoryStore(db_path)
    index = SemanticIndex(db_path)
    memory = MemoryService(store, index)

    memory.set_profile(42, {"name": "test"})
    memory.remember(42, "secret123")
    assert memory.search_user(42, "secret123")

    memory.clear_all_for_user(42)

    assert memory.get_profile(42) == {}
    assert memory.search_user(42, "secret123") == []
