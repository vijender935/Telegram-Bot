"""Chat agent tools — intentionally minimal.
Drive operations go through intent router, not LLM tool-calling.
"""
from langchain_core.tools import tool


def build_tools() -> list:
    # Empty tools = pure chat reliability on Groq.
    # Drive is handled by domain.intent router before agent runs.
    return []
