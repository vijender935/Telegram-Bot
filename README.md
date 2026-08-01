# Telegram Bot v1 — Layered Architecture

## Design

```
Telegram → Gateway (handlers) → Intent Router → Domain
                                      ↓
                              Chat Agent (LLM only)
                                      ↓
                    Infra: Drive / Memory / Sandbox / Whisper
```

**Key rules**
- Drive commands never go through LLM tool-calling
- Serial download maps are **per-user** with 30min TTL
- Mood + chat history in SQLite
- Optional `ALLOWED_USER_IDS` allowlist

## Structure

```
bot/
├── main.py
├── config.py
├── gateway/       # Telegram I/O only
├── domain/        # intent, mood
├── agent/         # prompts + chat agent
└── infra/         # drive, memory, sandbox, transcribe
```

## Render

**Start Command:** `python -m bot.main`

## Env

```
TELEGRAM_BOT_TOKEN=
GROQ_API_KEY=
GOOGLE_DRIVE_FOLDER_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
ALLOWED_USER_IDS=          # optional, comma-separated
```

## Usage

```
/drive
/list Picture
/download 2
2 download karo
Map folder list karo
/mood
```
