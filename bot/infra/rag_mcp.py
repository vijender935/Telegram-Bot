"""Compatibility import for the current custom Cloudflare MCP client.

This module keeps the existing import path stable while ensuring the bot uses
only the user's custom Cloudflare MCP implementation.
"""
from bot.infrastructure.rag_mcp import CloudflareMCPClient

__all__ = ["CloudflareMCPClient"]
