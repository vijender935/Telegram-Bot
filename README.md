# Telegram Bot v1 — Layered + Learning

## Design
```
Telegram → Gateway → Intent Router → Domain
                         ↓
                 Chat Agent (LLM + learned profile)
                         ↓
           Infra: Drive / Memory / Sandbox / Whisper
```

## Features
- Drive one-shot: `insta se 2 download karo` (list pehle zaroori nahi)
- Bare serial: `2` after a list
- Random file: `insta se koi bhi random`
- Voice / audio / video transcript
- File actions: Transcribe / Save / Upload Drive
- Learned profile memory (`/profile`, `/forgetprofile`)
- Mood system (`/mood`)

## Render
**Start Command:** `python -m bot.main`

**Build (video transcript):**  
`apt-get update && apt-get install -y ffmpeg && pip install -r requirements.txt`

## Env
```
TELEGRAM_BOT_TOKEN=
GROQ_API_KEY=
GOOGLE_DRIVE_FOLDER_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
ALLOWED_USER_IDS=
```

## Commands
```
/drive  /list Insta  /download 2  /mood
/profile  /forgetprofile  /clear
```
