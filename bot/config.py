import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")  # Map folder ID
GOOGLE_SA_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SANDBOX_PATH = os.getenv("SANDBOX_PATH", "/tmp/bot_files")
PORT = int(os.environ.get("PORT", 8080))
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
