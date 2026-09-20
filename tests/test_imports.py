def test_core_imports():
    __import__("bot.config")
    __import__("bot.main")
    __import__("bot.gateway.commands")
    __import__("bot.gateway.handlers")
    __import__("bot.gateway.media")
    __import__('bot.gateway.scheduler')
    __import__('bot.infrastructure.rag_mcp')
    __import__('bot.infrastructure.vectorstore.semantic_index')
