def test_core_imports():
    import bot.config
    import bot.main
    import bot.gateway.commands
    import bot.gateway.handlers
    import bot.gateway.media
    import bot.gateway.scheduler
    __import__('bot.infrastructure.rag_mcp')
    __import__('bot.infrastructure.vectorstore.semantic_index')
