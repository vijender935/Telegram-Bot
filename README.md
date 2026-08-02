# Telegram Bot v2 — Smart Seductive Companion

## Design
```
Telegram → Gateway → Intent Router → Orchestrator
                         ↓
              Chat Brain (LLM + mood + profile + media + session)
                         ↓
     Infra: Drive / Memory / Vision / Sandbox / Whisper
```

## Features
- Drive one-shot: `insta se 2 download karo`
- Bare serial: `2` after a list
- Random file: `insta se koi bhi random`
- **Vision:** downloaded photos/videos auto-described; bot talks about them as if she sent them
- Voice / audio / video transcript
- Learned profile (`/profile`, `/forgetprofile`)
- Session summary + emotion tracking
- Mood system (`/mood`)

## Render
**Start Command:** `python -m bot.main`

**Build (video + vision frames):**  
`apt-get update && apt-get install -y ffmpeg && pip install -r requirements.txt`

Use a **persistent disk** and set:
```
MEMORY_DB_PATH=/var/data/bot_memory.db
SANDBOX_PATH=/var/data/bot_files
```

## Env
```
TELEGRAM_BOT_TOKEN=
GROQ_API_KEY=
GOOGLE_DRIVE_FOLDER_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
ALLOWED_USER_IDS=
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_VISION_MODEL=qwen/qwen3.6-27b
TEMPERATURE=0.95
MEDIA_DESCRIBE_ON_DOWNLOAD=true
MEDIA_FOLLOWUP=true
SESSION_SUMMARY_EVERY=8
MEMORY_DB_PATH=/var/data/bot_memory.db
SANDBOX_PATH=/var/data/bot_files
```

## Commands
```
/drive  /list Insta  /download 2  /mood
/profile  /forgetprofile  /clear
```
