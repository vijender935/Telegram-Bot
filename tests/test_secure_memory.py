from bot.infra.memory import MemoryStore
from bot.application.secure_memory import SecureMemory


def test_secure_memory_vault_code(tmp_path):
    store = MemoryStore(str(tmp_path / "memory.db"))
    memory = SecureMemory(store)
    memory.set_vault_code(42, "secret123")
    assert memory.verify_vault_code(42, "secret123")
    assert not memory.verify_vault_code(42, "bad")
    memory.clear_all_for_user(42)
    assert not memory.verify_vault_code(42, "secret123")
