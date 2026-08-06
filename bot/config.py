import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_SA_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ── Image Enhancement APIs ──
HF_TOKEN            = os.getenv("HF_TOKEN", "")          # huggingface.co — FREE
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "") # replicate.com — pay per use

# Prefer persistent paths on Render disk if available
SANDBOX_PATH = os.getenv("SANDBOX_PATH", "/var/data/bot_files" if os.path.isdir("/var/data") else "/tmp/bot_files")
MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "/var/data/bot_memory.db" if os.path.isdir("/var/data") else "/tmp/bot_memory.db")

PORT = int(os.environ.get("PORT", 8080))
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.95"))

_allow = os.getenv("ALLOWED_USER_IDS", "").strip()
ALLOWED_USER_IDS: set[int] = {
    int(x) for x in _allow.split(",") if x.strip().isdigit()
}

SERIAL_MAP_TTL_SECONDS = int(os.getenv("SERIAL_MAP_TTL_SECONDS", str(30 * 60)))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
MAX_SEND_MB = int(os.getenv("MAX_SEND_MB", "48"))

# Feature flags
MEDIA_DESCRIBE_ON_DOWNLOAD = os.getenv("MEDIA_DESCRIBE_ON_DOWNLOAD", "true").lower() in ("1", "true", "yes")
MEDIA_FOLLOWUP = os.getenv("MEDIA_FOLLOWUP", "true").lower() in ("1", "true", "yes")
SESSION_SUMMARY_EVERY = int(os.getenv("SESSION_SUMMARY_EVERY", "8"))
