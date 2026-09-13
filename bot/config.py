"""Validated runtime configuration.

All environment parsing lives here so the rest of the application receives typed values.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from bot.core.exceptions import ConfigurationError

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GOOGLE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip()
GOOGLE_SA_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "").strip()

SANDBOX_PATH = os.getenv("SANDBOX_PATH", "/var/data/bot_files" if os.path.isdir("/var/data") else "/tmp/bot_files")
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "/var/data/bot_memory.db" if os.path.isdir("/var/data") else "/tmp/bot_memory.db")
PORT = int(os.getenv("PORT", "8080"))

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b").strip()
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "1200"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

_allow = os.getenv("ALLOWED_USER_IDS", "").strip()
ALLOWED_USER_IDS: set[int] = {int(x) for x in _allow.split(",") if x.strip().isdigit()}

SERIAL_MAP_TTL_SECONDS = int(os.getenv("SERIAL_MAP_TTL_SECONDS", str(30 * 60)))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
LLM_HISTORY_MESSAGES = int(os.getenv("LLM_HISTORY_MESSAGES", "8"))
MAX_SEND_MB = int(os.getenv("MAX_SEND_MB", "48"))
SESSION_SUMMARY_EVERY = int(os.getenv("SESSION_SUMMARY_EVERY", "8"))
MEDIA_DESCRIBE_ON_DOWNLOAD = os.getenv("MEDIA_DESCRIBE_ON_DOWNLOAD", "true").lower() in ("1", "true", "yes")
MEDIA_FOLLOWUP = os.getenv("MEDIA_FOLLOWUP", "true").lower() in ("1", "true", "yes")

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
VAULT_MAX_ATTEMPTS = int(os.getenv("VAULT_MAX_ATTEMPTS", "5"))
VAULT_LOCKOUT_SECONDS = int(os.getenv("VAULT_LOCKOUT_SECONDS", "900"))
VAULT_SESSION_SECONDS = int(os.getenv("VAULT_SESSION_SECONDS", "900"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

RAG_MCP_URL = os.getenv(
    "RAG_MCP_URL",
    "https://vijender935--multimodal-rag-search-mcp-app.modal.run/mcp",
).strip()
RAG_MCP_API_KEY = os.getenv("RAG_MCP_API_KEY", "").strip()
RAG_MCP_TIMEOUT_SECONDS = float(os.getenv("RAG_MCP_TIMEOUT_SECONDS", "20"))
RAG_MCP_TOP_K = int(os.getenv("RAG_MCP_TOP_K", "5"))
RAG_MCP_MODE = os.getenv("RAG_MCP_MODE", "hybrid").strip().lower()
RAG_MCP_RETRIES = int(os.getenv("RAG_MCP_RETRIES", "3"))
RAG_MCP_ENABLED = os.getenv("RAG_MCP_ENABLED", "true").lower() in ("1", "true", "yes")


def validate_startup(require_drive: bool = False) -> None:
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if require_drive and (not GOOGLE_FOLDER_ID or not GOOGLE_SA_JSON):
        missing.append("GOOGLE_DRIVE_FOLDER_ID/GOOGLE_SERVICE_ACCOUNT_JSON")
    if missing:
        raise ConfigurationError("Missing required environment variables: " + ", ".join(missing))
    if not 0 <= TEMPERATURE <= 2:
        raise ConfigurationError("TEMPERATURE must be between 0 and 2")
    if GROQ_MAX_TOKENS < 256 or GROQ_MAX_TOKENS > 4096:
        raise ConfigurationError("GROQ_MAX_TOKENS must be between 256 and 4096")
    if LLM_HISTORY_MESSAGES < 0 or LLM_HISTORY_MESSAGES > MAX_HISTORY_MESSAGES:
        raise ConfigurationError("LLM_HISTORY_MESSAGES must be between 0 and MAX_HISTORY_MESSAGES")
    if RAG_MCP_MODE not in {"metadata", "visual", "hybrid"}:
        raise ConfigurationError("RAG_MCP_MODE must be metadata, visual or hybrid")
    if RAG_MCP_TOP_K < 1 or RAG_MCP_TOP_K > 30:
        raise ConfigurationError("RAG_MCP_TOP_K must be between 1 and 30")
    if RAG_MCP_RETRIES < 1 or RAG_MCP_RETRIES > 5:
        raise ConfigurationError("RAG_MCP_RETRIES must be between 1 and 5")
    Path(MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(SANDBOX_PATH).mkdir(parents=True, exist_ok=True)
