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

HF_TOKEN = os.getenv("HF_TOKEN", "").strip()
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "").strip()

SANDBOX_PATH = os.getenv("SANDBOX_PATH", "/var/data/bot_files" if os.path.isdir("/var/data") else "/tmp/bot_files")
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "/var/data/bot_memory.db" if os.path.isdir("/var/data") else "/tmp/bot_memory.db")
PORT = int(os.getenv("PORT", "8080"))

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()
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

# User-owned custom Cloudflare MCP only.
# It exposes the ai-images-pilot Worker through R2 + D1 + Vectorize.
CLOUDFLARE_MCP_URL = os.getenv(
    "CLOUDFLARE_MCP_URL",
    "https://cloudflare-mcp.vijender935.workers.dev/mcp",
).strip()
CLOUDFLARE_MCP_API_KEY = os.getenv("CLOUDFLARE_MCP_API_KEY", "").strip()
CLOUDFLARE_MCP_TIMEOUT_SECONDS = float(os.getenv("CLOUDFLARE_MCP_TIMEOUT_SECONDS", "30"))
CLOUDFLARE_MCP_RETRIES = int(os.getenv("CLOUDFLARE_MCP_RETRIES", "3"))
CLOUDFLARE_MCP_ENABLED = os.getenv("CLOUDFLARE_MCP_ENABLED", "true").lower() in ("1", "true", "yes")

# Render-safe Telegram webhook. Polling is intentionally disabled because Render's
# zero-downtime deploys briefly run old and new instances side-by-side.
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "https://telegram-bot-hnzl.onrender.com").rstrip("/")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()


def validate_startup() -> None:
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not GROQ_API_KEY:
        missing.append("GROQ_API_KEY")
    if missing:
        raise ConfigurationError("Missing required environment variables: " + ", ".join(missing))
    if not 0 <= TEMPERATURE <= 2:
        raise ConfigurationError("TEMPERATURE must be between 0 and 2")
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
    if CLOUDFLARE_MCP_TIMEOUT_SECONDS < 3 or CLOUDFLARE_MCP_TIMEOUT_SECONDS > 120:
        raise ConfigurationError("CLOUDFLARE_MCP_TIMEOUT_SECONDS must be between 3 and 120")
    Path(MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(SANDBOX_PATH).mkdir(parents=True, exist_ok=True)
