def test_core_imports():
    __import__('bot.gateway.scheduler')
    __import__('bot.gateway.mcp_media')
    __import__('bot.infrastructure.rag_mcp')
    __import__('bot.infrastructure.vectorstore.semantic_index')


def test_health_check_executes_transcribe_import():
    from types import SimpleNamespace

    from bot.core.health import check_health

    config = SimpleNamespace(
        TELEGRAM_TOKEN="dummy",
        GROQ_API_KEY="dummy",
        GROQ_MODEL="dummy",
    )
    result = check_health(config, "/tmp/ci_memory.db")

    assert result["checks"]["ffmpeg"] is True
