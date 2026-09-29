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

SANDBOX_PATH = os.getenv("SANDBOX_PATH", "/var/data/bot_files" if os.path.isdir("/var/data") else "/tmp/bot_files")
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "/var/data/bot_memory.db" if os.path.isdir("/var/data") else "/tmp/bot_memory.db")
PORT = int(os.getenv("PORT", "8080"))

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.6-27b").strip()
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "1200"))
GROQ_TEMPERATURE = float(os.getenv("GROQ_TEMPERATURE", "0.95"))

SERIAL_MAP_TTL_SECONDS = int(os.getenv("SERIAL_MAP_TTL_SECONDS", str(30 * 60)))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
LLM_HISTORY_MESSAGES = int(os.getenv("LLM_HISTORY_MESSAGES", "8"))
MAX_SEND_MB = int(os.getenv("MAX_SEND_MB", "48"))
SESSION_SUMMARY_EVERY = int(os.getenv("SESSION_SUMMARY_EVERY", "8"))
MEDIA_DESCRIBE_ON_DOWNLOAD = os.getenv("MEDIA_DESCRIBE_ON_DOWNLOAD", "true").lower() in ("1", "true", "yes")
MEDIA_FOLLOWUP = os.getenv("MEDIA_FOLLOWUP", "true").lower() in ("1", "true", "yes")

RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "20"))
API_RATE_LIMIT_PER_MINUTE = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "60"))
API_TIMEOUT_SECONDS = float(os.getenv("API_TIMEOUT_SECONDS", "90"))
AI_REQUEST_TIMEOUT_SECONDS = float(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "75"))
TOOL_TIMEOUT_SECONDS = float(os.getenv("TOOL_TIMEOUT_SECONDS", "30"))
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "6"))
MAX_API_MESSAGE_CHARS = int(os.getenv("MAX_API_MESSAGE_CHARS", "8000"))
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "").strip()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

CLOUDFLARE_MCP_URL = os.getenv(
    "CLOUDFLARE_MCP_URL",
    "https://cloudflare-mcp.vijender935.workers.dev/mcp",
).strip()
CLOUDFLARE_MCP_API_KEY = os.getenv("CLOUDFLARE_MCP_API_KEY", "").strip()
CLOUDFLARE_MCP_TIMEOUT_SECONDS = float(os.getenv("CLOUDFLARE_MCP_TIMEOUT_SECONDS", "30"))
CLOUDFLARE_MCP_RETRIES = int(os.getenv("CLOUDFLARE_MCP_RETRIES", "3"))
CLOUDFLARE_MCP_ENABLED = os.getenv("CLOUDFLARE_MCP_ENABLED", "true").lower() in ("1", "true", "yes")

TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "https://telegram-bot-hnzl.onrender.com").rstrip("/")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()


def validate_startup() -> None:
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if not ADMIN_API_KEY:
        missing.append("ADMIN_API_KEY")
    if missing:
        raise ConfigurationError("Missing required environment variables: " + ", ".join(missing))
    if RATE_LIMIT_PER_MINUTE < 1:
        raise ConfigurationError("RATE_LIMIT_PER_MINUTE must be at least 1")
    if API_RATE_LIMIT_PER_MINUTE < 1:
        raise ConfigurationError("API_RATE_LIMIT_PER_MINUTE must be at least 1")
    if not 0 <= GROQ_TEMPERATURE <= 2:
        raise ConfigurationError("GROQ_TEMPERATURE must be between 0 and 2")
    if GROQ_MAX_TOKENS < 256 or GROQ_MAX_TOKENS > 4096:
        raise ConfigurationError("GROQ_MAX_TOKENS must be between 256 and 4096")
    if LLM_HISTORY_MESSAGES < 0 or LLM_HISTORY_MESSAGES > MAX_HISTORY_MESSAGES:
        raise ConfigurationError("LLM_HISTORY_MESSAGES must be between 0 and MAX_HISTORY_MESSAGES")
    if CLOUDFLARE_MCP_RETRIES < 1 or CLOUDFLARE_MCP_RETRIES > 5:
        raise ConfigurationError("CLOUDFLARE_MCP_RETRIES must be between 1 and 5")
    if not TELEGRAM_WEBHOOK_URL.startswith("https://"):
        raise ConfigurationError("TELEGRAM_WEBHOOK_URL must be an HTTPS URL")
    if not TELEGRAM_WEBHOOK_SECRET:
        raise ConfigurationError("Missing required environment variable: TELEGRAM_WEBHOOK_SECRET")
    if API_TIMEOUT_SECONDS < 10 or API_TIMEOUT_SECONDS > 180:
        raise ConfigurationError("API_TIMEOUT_SECONDS must be between 10 and 180")
    if AI_REQUEST_TIMEOUT_SECONDS < 5 or AI_REQUEST_TIMEOUT_SECONDS > 180:
        raise ConfigurationError("AI_REQUEST_TIMEOUT_SECONDS must be between 5 and 180")
    if TOOL_TIMEOUT_SECONDS < 3 or TOOL_TIMEOUT_SECONDS > 120:
        raise ConfigurationError("TOOL_TIMEOUT_SECONDS must be between 3 and 120")
    if MAX_TOOL_ROUNDS < 1 or MAX_TOOL_ROUNDS > 12:
        raise ConfigurationError("MAX_TOOL_ROUNDS must be between 1 and 12")
    if MAX_API_MESSAGE_CHARS < 100 or MAX_API_MESSAGE_CHARS > 32000:
        raise ConfigurationError("MAX_API_MESSAGE_CHARS must be between 100 and 32000")
    if CLOUDFLARE_MCP_TIMEOUT_SECONDS < 3 or CLOUDFLARE_MCP_TIMEOUT_SECONDS > 120:
        raise ConfigurationError("CLOUDFLARE_MCP_TIMEOUT_SECONDS must be between 3 and 120")
    Path(MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(SANDBOX_PATH).mkdir(parents=True, exist_ok=True)
