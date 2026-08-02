# Telegram Bot v2 — Postgres + Vision + Learning

## Design
```
Telegram → Gateway → Intent Router → Domain (emotion/orchestrator)
                         ↓
              Chat chain (mood + profile + media + session)
                         ↓
     Infra: Drive / Postgres memory / Sandbox / Whisper / Vision
```

## Features
- Drive one-shot download / bare serial / random / "photo bhej"
- Voice / audio / video transcript (chunked)
- Vision describe on download + flirty follow-up
- Learned profile + session summary (Postgres)
- Mood system, file action buttons

## Render
**Start Command:** `python -m bot.main`

**Build Command (recommended):**
```bash
apt-get update && apt-get install -y ffmpeg && pip install -r requirements.txt
```

## Env
```
TELEGRAM_BOT_TOKEN=
GROQ_API_KEY=
GOOGLE_DRIVE_FOLDER_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
DATABASE_URL=                 # Render Postgres — required
ALLOWED_USER_IDS=             # optional
GROQ_VISION_MODEL=            # optional
MEDIA_DESCRIBE_ON_DOWNLOAD=true
MEDIA_FOLLOWUP=true
```

## Commands
```
/drive  /list Insta  /download 2  /mood
/profile  /forgetprofile  /clear
```
